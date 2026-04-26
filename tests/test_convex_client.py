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
            },
            events=[
                {
                    "rawDeliveryId": "placeholder",
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
                    "rawDeliveryId": "placeholder",
                    "recordType": "steps",
                    "valueNumeric": 500.0,
                    "unit": "count",
                    "startTime": 1710803600000,
                    "endTime": 1710807200000,
                    "capturedAt": 1710807200000,
                    "payloadHash": "hash123",
                    "fingerprint": "fingerprint-456",
                    "createdAt": 1710807200000,
                },
                {
                    "rawDeliveryId": "placeholder",
                    "recordType": "steps",
                    "valueNumeric": 500.0,
                    "unit": "count",
                    "startTime": 1710807200000,
                    "endTime": 1710810800000,
                    "capturedAt": 1710810800000,
                    "payloadHash": "hash123",
                    "fingerprint": "fingerprint-456",
                    "createdAt": 1710810800000,
                },
            ],
        )

    assert result == {
        "delivery_id": "delivery-123",
        "received_records": 3,
        "stored_records": 2,
        "duplicate_records": 1,
    }
    assert mock_mut.call_args_list == [
        call(
            "mutations.js:storeRawDelivery",
            {
                "receivedAt": 1710803600000,
                "sourceIp": "127.0.0.1",
                "userAgent": "pytest",
                "payloadJson": '{"records": []}',
                "payloadHash": "hash123",
                "status": "in_progress",
                "recordCount": 3,
            },
        ),
        call(
            "mutations.js:ingestNormalizedEventsChunk",
            {
                "rawDeliveryId": "delivery-123",
                "events": [
                    {
                        "rawDeliveryId": "placeholder",
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
                        "rawDeliveryId": "placeholder",
                        "recordType": "steps",
                        "valueNumeric": 500.0,
                        "unit": "count",
                        "startTime": 1710803600000,
                        "endTime": 1710807200000,
                        "capturedAt": 1710807200000,
                        "payloadHash": "hash123",
                        "fingerprint": "fingerprint-456",
                        "createdAt": 1710807200000,
                    },
                ],
            },
        ),
        call(
            "mutations.js:ingestNormalizedEventsChunk",
            {
                "rawDeliveryId": "delivery-123",
                "events": [
                    {
                        "rawDeliveryId": "placeholder",
                        "recordType": "steps",
                        "valueNumeric": 500.0,
                        "unit": "count",
                        "startTime": 1710807200000,
                        "endTime": 1710810800000,
                        "capturedAt": 1710810800000,
                        "payloadHash": "hash123",
                        "fingerprint": "fingerprint-456",
                        "createdAt": 1710810800000,
                    },
                ],
            },
        ),
        call(
            "mutations.js:updateRawDeliveryStatus",
            {
                "rawDeliveryId": "delivery-123",
                "status": "completed",
            },
        ),
    ]


def test_ingest_delivery_marks_buffered_delivery_as_error_when_a_chunk_fails():
    """Buffered ingest should leave a visible error state on the raw delivery if chunk storage fails."""
    client = ConvexClient(convex_url="http://127.0.0.1:3210", admin_key="key", ingest_batch_size=1)

    with patch.object(
        client._client,
        "mutation",
        side_effect=[
            "delivery-123",
            RuntimeError("chunk failed"),
            None,
        ],
    ) as mock_mut:
        try:
            client.ingest_delivery(
                raw_delivery={
                    "receivedAt": 1710803600000,
                    "sourceIp": "127.0.0.1",
                    "userAgent": "pytest",
                    "payloadJson": '{"records": []}',
                    "payloadHash": "hash123",
                    "status": "completed",
                    "recordCount": 2,
                },
                events=[
                    {
                        "rawDeliveryId": "placeholder",
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
                        "rawDeliveryId": "placeholder",
                        "recordType": "steps",
                        "valueNumeric": 500.0,
                        "unit": "count",
                        "startTime": 1710803600000,
                        "endTime": 1710807200000,
                        "capturedAt": 1710807200000,
                        "payloadHash": "hash123",
                        "fingerprint": "fingerprint-456",
                        "createdAt": 1710807200000,
                    },
                ],
            )
        except RuntimeError as exc:
            assert str(exc) == "chunk failed"
        else:
            assert False, "ingest_delivery should re-raise the chunk failure"

    assert mock_mut.call_args_list == [
        call(
            "mutations.js:storeRawDelivery",
            {
                "receivedAt": 1710803600000,
                "sourceIp": "127.0.0.1",
                "userAgent": "pytest",
                "payloadJson": '{"records": []}',
                "payloadHash": "hash123",
                "status": "in_progress",
                "recordCount": 2,
            },
        ),
        call(
            "mutations.js:ingestNormalizedEventsChunk",
            {
                "rawDeliveryId": "delivery-123",
                "events": [
                    {
                        "rawDeliveryId": "placeholder",
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
            },
        ),
        call(
            "mutations.js:updateRawDeliveryStatus",
            {
                "rawDeliveryId": "delivery-123",
                "status": "error",
                "errorMessage": "chunk failed",
            },
        ),
    ]


def test_get_trend_success():
    """get_trend should pass arguments to queries.js:getTrend and return the dictionary."""
    client = ConvexClient(convex_url="http://127.0.0.1:3210", admin_key="key")
    mock_response = {
        "direction": "up",
        "percentChange": 10.0,
        "currentValue": 110,
        "priorValue": 100
    }

    with patch.object(client._client, "query", return_value=mock_response) as mock_query:
        result = client.get_trend("steps", from_ms=1000, to_ms=2000)

    assert result == mock_response
    mock_query.assert_called_once()
    assert mock_query.call_args[0][0] == "analytics.js:getTrend"
    assert mock_query.call_args[0][1] == {
        "recordType": "steps",
        "fromMs": 1000,
        "toMs": 2000,
    }


def test_get_trend_missing_optional():
    """get_trend should handle missing optional from_ms and to_ms arguments."""
    client = ConvexClient(convex_url="http://127.0.0.1:3210", admin_key="key")
    mock_response = {}

    with patch.object(client._client, "query", return_value=mock_response) as mock_query:
        result = client.get_trend("steps")

    assert result == mock_response
    mock_query.assert_called_once()
    assert mock_query.call_args[0][0] == "analytics.js:getTrend"
    assert mock_query.call_args[0][1] == {
        "recordType": "steps",
        "fromMs": None,
        "toMs": None,
    }


def test_get_trend_non_dict():
    """get_trend should return an empty dict if the query returns a non-dict."""
    client = ConvexClient(convex_url="http://127.0.0.1:3210", admin_key="key")

    with patch.object(client._client, "query", return_value=[]) as mock_query:
        result = client.get_trend("steps")

    assert result == {}
    mock_query.assert_called_once()


def test_get_trend_exception():
    """get_trend should wrap ConvexError in a standard Exception."""
    from convex import ConvexError
    import pytest

    client = ConvexClient(convex_url="http://127.0.0.1:3210", admin_key="key")

    with patch.object(client._client, "query", side_effect=ConvexError("test error")):
        with pytest.raises(Exception, match="Convex error: test error"):
            client.get_trend("steps")
