"""Tests for ConvexClient — the HTTP client wrapper for Convex self-hosted."""

from unittest.mock import call, patch
from app.convex_client import ConvexClient


def test_store_raw_delivery_calls_mutation():
    """store_raw_delivery delegates to mutations.js:storeRawDelivery via ConvexHttpClient."""
    client = ConvexClient(convex_url="http://127.0.0.1:3210", admin_key="key")

    with patch.object(client._client, 'mutation', return_value="delivery-123") as mock_mut:
        result = client.store_raw_delivery(
            source_ip="127.0.0.1",
            user_agent="test-agent",
            payload_json='{"test": true}',
            record_count=5,
            data_class="test",
            data_class_reason="header:x-openclaw-test-data",
        )
        assert result == "delivery-123"
        mock_mut.assert_called_once()
        call_args = mock_mut.call_args
        assert call_args[0][0] == "mutations.js:storeRawDelivery"
        assert call_args[0][1]["dataClass"] == "test"
        assert call_args[0][1]["dataClassReason"] == "header:x-openclaw-test-data"


def test_ingest_delivery_uses_single_mutation_for_small_batches():
    """Small payloads keep the single-mutation ingest path."""
    client = ConvexClient(convex_url="http://127.0.0.1:3210", admin_key="key")

    with patch.object(
        client._client,
        "mutation",
        return_value={
            "deliveryId": "delivery-123",
            "receivedRecords": 2,
            "storedRecords": 1,
            "duplicateRecords": 1,
        },
    ) as mock_mut:
        result = client.ingest_delivery(
            raw_delivery={
                "receivedAt": 1710803600000,
                "sourceIp": "127.0.0.1",
                "userAgent": "pytest",
                "payloadJson": '{"records": []}',
                "payloadHash": "hash123",
                "status": "completed",
                "recordCount": 2,
                "dataClass": "test",
                "dataClassReason": "header:x-openclaw-test-data",
            },
            events=[
                {
                    "rawDeliveryId": "delivery-123",
                    "recordType": "steps",
                    "valueNumeric": 1000.0,
                    "unit": "count",
                    "startTime": 1710800000000,
                    "endTime": 1710803600000,
                    "capturedAt": 1710803600000,
                    "payloadHash": "hash123",
                    "fingerprint": "fingerprint-123",
                    "createdAt": 1710803600000,
                }
            ],
        )

    assert result["stored_records"] == 1
    mock_mut.assert_called_once()
    assert mock_mut.call_args[0][0] == "mutations.js:ingestNormalizedDelivery"
    assert mock_mut.call_args[0][1]["rawDelivery"]["dataClass"] == "test"
    assert mock_mut.call_args[0][1]["rawDelivery"]["status"] == "completed"


def test_ingest_delivery_chunks_large_batches_behind_single_raw_delivery():
    """Large payloads should buffer events into chunked Convex writes without duplicating rawDeliveries."""
    client = ConvexClient(convex_url="http://127.0.0.1:3210", admin_key="key", ingest_batch_size=2)

    with patch.object(
        client._client,
        "mutation",
        side_effect=[
            "delivery-123",
            {
                "receivedRecords": 2,
                "storedRecords": 2,
                "duplicateRecords": 0,
            },
            {
                "receivedRecords": 1,
                "storedRecords": 0,
                "duplicateRecords": 1,
            },
            None,
        ],
    ) as mock_mut:
        result = client.ingest_delivery(
            raw_delivery={
                "receivedAt": 1710803600000,
                "sourceIp": "127.0.0.1",
                "userAgent": "pytest",
                "payloadJson": '{"records": []}',
                "payloadHash": "hash123",
                "status": "completed",
                "recordCount": 3,
                "dataClass": "test",
                "dataClassReason": "header:x-openclaw-test-data",
            },
            events=[
                {
                    "rawDeliveryId": "delivery-123",
                    "recordType": "steps",
                    "valueNumeric": 1000.0,
                    "unit": "count",
                    "startTime": 1710800000000,
                    "endTime": 1710803600000,
                    "capturedAt": 1710803600000,
                    "payloadHash": "hash123",
                    "fingerprint": "fingerprint-123",
                    "createdAt": 1710803600000,
                },
                {
                    "rawDeliveryId": "delivery-123",
                    "recordType": "steps",
                    "valueNumeric": 2000.0,
                    "unit": "count",
                    "startTime": 1710803600000,
                    "endTime": 1710807200000,
                    "capturedAt": 1710807200000,
                    "payloadHash": "hash124",
                    "fingerprint": "fingerprint-124",
                    "createdAt": 1710807200000,
                },
                {
                    "rawDeliveryId": "delivery-123",
                    "recordType": "steps",
                    "valueNumeric": 3000.0,
                    "unit": "count",
                    "startTime": 1710807200000,
                    "endTime": 1710810800000,
                    "capturedAt": 1710810800000,
                    "payloadHash": "hash125",
                    "fingerprint": "fingerprint-125",
                    "createdAt": 1710810800000,
                },
            ],
        )

    # Should have called 4 mutations: storeRawDelivery + 3 chunk writes
    assert mock_mut.call_count == 4
    assert mock_mut.call_args[0][0] == "mutations.js:ingestNormalizedDelivery"
    assert result["stored_records"] == 2
    assert result["duplicate_records"] == 1
    assert result["buffered_records"] == 3


def test_ingest_delivery_reports_error_when_no_chunks_succeed():
    """If all chunk writes fail, the delivery is marked as error."""
    client = ConvexClient(convex_url="http://127.0.0.1:3210", admin_key="key", ingest_batch_size=2)

    with patch.object(
        client._client,
        "mutation",
        side_effect=["delivery-123", None, None],
    ) as mock_mut:
        result = client.ingest_delivery(
            raw_delivery={
                "receivedAt": 1710803600000,
                "sourceIp": "127.0.0.1",
                "userAgent": "pytest",
                "payloadJson": '{"records": []}',
                "payloadHash": "hash123",
                "status": "completed",
                "recordCount": 3,
                "dataClass": "test",
                "dataClassReason": "header:x-openclaw-test-data",
            },
            events=[
                {
                    "rawDeliveryId": "delivery-123",
                    "recordType": "steps",
                    "valueNumeric": 1000.0,
                    "unit": "count",
                    "startTime": 1710800000000,
                    "endTime": 1710803600000,
                    "capturedAt": 1710803600000,
                    "payloadHash": "hash123",
                    "fingerprint": "fingerprint-123",
                    "createdAt": 1710803600000,
                },
            ],
        )

    assert result["status"] == "error"
    assert "No chunks stored" in result["error"]


def test_ingest_delivery_marks_buffered_delivery_as_error_when_a_chunk_fails():
    """If some (but not all) chunks succeed, the delivery is marked as partially-errored."""
    client = ConvexClient(convex_url="http://127.0.0.1:3210", admin_key="key", ingest_batch_size=2)

    with patch.object(
        client._client,
        "mutation",
        side_effect=[
            "delivery-123",
            {"receivedRecords": 1, "storedRecords": 1, "duplicateRecords": 0},
            None,
            {
                "receivedRecords": 1,
                "storedRecords": 0,
                "duplicateRecords": 0,
            },
        ],
    ) as mock_mut:
        result = client.ingest_delivery(
            raw_delivery={
                "receivedAt": 1710803600000,
                "sourceIp": "127.0.0.1",
                "userAgent": "pytest",
                "payloadJson": '{"records": []}',
                "payloadHash": "hash123",
                "status": "completed",
                "recordCount": 3,
                "dataClass": "test",
                "dataClassReason": "header:x-openclaw-test-data",
            },
            events=[
                {
                    "rawDeliveryId": "delivery-123",
                    "recordType": "steps",
                    "valueNumeric": 1000.0,
                    "unit": "count",
                    "startTime": 1710800000000,
                    "endTime": 1710803600000,
                    "capturedAt": 1710803600000,
                    "payloadHash": "hash123",
                    "fingerprint": "fingerprint-123",
                    "createdAt": 1710803600000,
                },
                {
                    "rawDeliveryId": "delivery-123",
                    "recordType": "steps",
                    "valueNumeric": 2000.0,
                    "unit": "count",
                    "startTime": 1710803600000,
                    "endTime": 1710807200000,
                    "capturedAt": 1710807200000,
                    "payloadHash": "hash124",
                    "fingerprint": "fingerprint-124",
                    "createdAt": 1710807200000,
                },
                {
                    "rawDeliveryId": "delivery-123",
                    "recordType": "steps",
                    "valueNumeric": 3000.0,
                    "unit": "count",
                    "startTime": 1710807200000,
                    "endTime": 1710810800000,
                    "capturedAt": 1710810800000,
                    "payloadHash": "hash125",
                    "fingerprint": "fingerprint-125",
                    "createdAt": 1710810800000,
                },
            ],
        )

    assert result["stored_records"] == 1
    assert result["status"] == "completed"
    assert mock_mut.call_count == 4


def test_get_analytics_overview_success():
    """get_analytics_overview successfully fetches and returns data."""
    client = ConvexClient(convex_url="http://127.0.0.1:3210", admin_key="key")

    with patch.object(client._client, 'query', return_value=[{"metric": "value"}]) as mock_query:
        result = client.get_analytics_overview(
            from_ms=1000,
            to_ms=2000,
            record_types=["type1"],
            device_id="dev1",
        )
        assert result == [{"metric": "value"}]
        mock_query.assert_called_once()
        call_args = mock_query.call_args
        assert call_args[0][0] == "analytics.js:getOverview"
        assert call_args[0][1] == {
            "fromMs": 1000,
            "toMs": 2000,
            "recordTypes": ["type1"],
            "deviceId": "dev1"
        }


def test_get_analytics_overview_empty_result():
    """get_analytics_overview returns empty list if result is None or not a list."""
    client = ConvexClient(convex_url="http://127.0.0.1:3210", admin_key="key")

    with patch.object(client._client, 'query', return_value=None):
        result = client.get_analytics_overview()
        assert result == []


def test_get_analytics_overview_handles_convex_error():
    """get_analytics_overview raises Exception on ConvexError."""
    from convex import ConvexError
    import pytest

    client = ConvexClient(convex_url="http://127.0.0.1:3210", admin_key="key")

    with patch.object(client._client, 'query', side_effect=ConvexError("test error", {"message": "test error"})):
        with pytest.raises(Exception) as excinfo:
            client.get_analytics_overview()
        assert "Convex error: test error" in str(excinfo.value)


def test_check_db_health_success():
    """check_db_health returns the dict response on success."""
    client = ConvexClient(convex_url="http://127.0.0.1:3210", admin_key="key")
    with patch.object(client._client, 'query', return_value={"ok": True, "db": "healthy"}) as mock_query:
        result = client.check_db_health()
        assert result == {"ok": True, "db": "healthy"}
        mock_query.assert_called_once_with("queries.js:checkDbHealth", {})


def test_check_db_health_non_dict_response():
    """check_db_health returns an empty dict if the response is not a dict."""
    client = ConvexClient(convex_url="http://127.0.0.1:3210", admin_key="key")
    with patch.object(client._client, 'query', return_value=["not", "a", "dict"]) as mock_query:
        result = client.check_db_health()
        assert result == {}
        mock_query.assert_called_once_with("queries.js:checkDbHealth", {})


def test_check_db_health_convex_error():
    """check_db_health raises an Exception if ConvexError occurs."""
    from convex import ConvexError
    import pytest

    client = ConvexClient(convex_url="http://127.0.0.1:3210", admin_key="key")
    with patch.object(client._client, 'query', side_effect=ConvexError("db is down", "db is down")) as mock_query:
        with pytest.raises(Exception) as exc_info:
            client.check_db_health()
        assert "Convex error: db is down" in str(exc_info.value)
        mock_query.assert_called_once_with("queries.js:checkDbHealth", {})
