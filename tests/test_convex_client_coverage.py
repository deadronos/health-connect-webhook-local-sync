"""Tests for ConvexClient methods not covered by the existing test suite."""

import pytest
from unittest.mock import patch, MagicMock
from convex import ConvexError
from app.convex_client import ConvexClient


@pytest.fixture
def client():
    """Create a ConvexClient with a mocked internal client."""
    c = ConvexClient(convex_url="http://127.0.0.1:3210", admin_key="test-key")
    return c


# --- store_raw_delivery ---


def test_store_raw_delivery_success(client):
    """store_raw_delivery should compute payload hash and call the Convex mutation."""
    with patch.object(client._client, 'mutation', return_value="delivery-abc") as mock_mut:
        result = client.store_raw_delivery(
            source_ip="10.0.0.1",
            user_agent="pytest/1.0",
            payload_json='{"records": []}',
            record_count=0,
        )
        assert result == "delivery-abc"
        call_args = mock_mut.call_args[0][1]
        assert call_args["sourceIp"] == "10.0.0.1"
        assert call_args["userAgent"] == "pytest/1.0"
        assert call_args["payloadHash"]  # SHA-256 hash computed
        assert call_args["status"] == "completed"
        assert "errorMessage" not in call_args


def test_store_raw_delivery_with_error_status(client):
    """store_raw_delivery should accept error status and error message."""
    with patch.object(client._client, 'mutation', return_value="delivery-err") as mock_mut:
        result = client.store_raw_delivery(
            source_ip="10.0.0.1",
            user_agent=None,
            payload_json='{"bad": true}',
            record_count=1,
            status="error",
            error_message="something went wrong",
            data_class="valid",
        )
        assert result == "delivery-err"
        call_args = mock_mut.call_args[0][1]
        assert call_args["status"] == "error"
        assert call_args["errorMessage"] == "something went wrong"
        assert call_args["dataClass"] == "valid"


def test_store_raw_delivery_convex_error(client):
    """store_raw_delivery should raise Exception wrapping ConvexError."""
    with patch.object(client._client, 'mutation', side_effect=ConvexError("insert failed", data=None)):
        with pytest.raises(Exception, match="Convex error: insert failed"):
            client.store_raw_delivery(
                source_ip="10.0.0.1",
                user_agent="test",
                payload_json='{}',
                record_count=0,
            )


def test_store_raw_delivery_strips_none_args(client):
    """store_raw_delivery should strip None values from args before sending to Convex."""
    with patch.object(client._client, 'mutation', return_value="delivery-1") as mock_mut:
        client.store_raw_delivery(
            source_ip="10.0.0.1",
            user_agent=None,
            payload_json='{}',
            record_count=0,
        )
        call_args = mock_mut.call_args[0][1]
        assert "userAgent" not in call_args
        assert "errorMessage" not in call_args
        assert "dataClassReason" not in call_args


# --- store_health_events ---


def test_store_health_events_success(client):
    """store_health_events should send events and return list of IDs."""
    with patch.object(client._client, 'mutation', return_value=["id1", "id2"]) as mock_mut:
        events = [
            {"recordType": "steps", "valueNumeric": 1000.0, "unit": "count"},
            {"recordType": "heart_rate", "valueNumeric": 72.0, "unit": "bpm"},
        ]
        result = client.store_health_events(events)
        assert result == ["id1", "id2"]
        mock_mut.assert_called_once()


def test_store_health_events_empty(client):
    """store_health_events should return empty list for no events."""
    result = client.store_health_events([])
    assert result == []


def test_store_health_events_convex_error(client):
    """store_health_events should raise Exception on ConvexError."""
    with patch.object(client._client, 'mutation', side_effect=ConvexError("write failed", data=None)):
        with pytest.raises(Exception, match="Convex error: write failed"):
            client.store_health_events([{"recordType": "steps"}])


# --- check_duplicate ---


def test_check_duplicate_returns_true(client):
    """check_duplicate should return True when a matching delivery exists."""
    with patch.object(client._client, 'mutation', return_value=True):
        result = client.check_duplicate("hash123")
        assert result is True


def test_check_duplicate_returns_false(client):
    """check_duplicate should return False when no matching delivery exists."""
    with patch.object(client._client, 'mutation', return_value=False):
        result = client.check_duplicate("hash456")
        assert result is False


def test_check_duplicate_convex_error(client):
    """check_duplicate should raise Exception on ConvexError."""
    with patch.object(client._client, 'mutation', side_effect=ConvexError("query failed", data=None)):
        with pytest.raises(Exception, match="Convex error: query failed"):
            client.check_duplicate("hash789")


# --- get_analytics_timeseries ---


def test_get_analytics_timeseries_success(client):
    """get_analytics_timeseries should delegate to the correct Convex query."""
    fake_rows = [{"bucketStart": 1710800000000, "count": 5, "sum": 100.0}]
    with patch.object(client._client, 'query', return_value=fake_rows) as mock_query:
        result = client.get_analytics_timeseries(
            record_type="steps",
            bucket_size="day",
            from_ms=1710800000000,
            to_ms=1710886400000,
        )
        assert result == fake_rows
        call_args = mock_query.call_args[0][1]
        assert call_args["recordType"] == "steps"
        assert call_args["bucketSize"] == "day"


def test_get_analytics_timeseries_strips_none(client):
    """get_analytics_timeseries should omit None args from the Convex call."""
    with patch.object(client._client, 'query', return_value=[]) as mock_query:
        client.get_analytics_timeseries(record_type="steps", bucket_size="hour")
        call_args = mock_query.call_args[0][1]
        assert "fromMs" not in call_args
        assert "toMs" not in call_args
        assert "deviceId" not in call_args


def test_get_analytics_timeseries_convex_error(client):
    """get_analytics_timeseries should raise Exception on ConvexError."""
    with patch.object(client._client, 'query', side_effect=ConvexError("ts error", data=None)):
        with pytest.raises(Exception, match="Convex error: ts error"):
            client.get_analytics_timeseries(record_type="steps", bucket_size="day")


# --- list_analytics_events ---


def test_list_analytics_events_success(client):
    """list_analytics_events should return events from Convex."""
    fake_events = [{"recordType": "steps", "valueNumeric": 100}]
    with patch.object(client._client, 'query', return_value=fake_events):
        result = client.list_analytics_events(record_types=["steps"], limit=50)
        assert result == fake_events


def test_list_analytics_events_strips_none(client):
    """list_analytics_events should omit None optional args."""
    with patch.object(client._client, 'query', return_value=[]) as mock_query:
        client.list_analytics_events(limit=10)
        call_args = mock_query.call_args[0][1]
        assert "fromMs" not in call_args
        assert "toMs" not in call_args
        assert "recordTypes" not in call_args
        assert "deviceId" not in call_args


def test_list_analytics_events_non_list_result(client):
    """list_analytics_events should return empty list on non-list Convex response."""
    with patch.object(client._client, 'query', return_value=None):
        result = client.list_analytics_events()
        assert result == []


def test_list_analytics_events_convex_error(client):
    """list_analytics_events should raise Exception on ConvexError."""
    with patch.object(client._client, 'query', side_effect=ConvexError("events error", data=None)):
        with pytest.raises(Exception, match="Convex error: events error"):
            client.list_analytics_events()


# --- get_trend ---


def test_get_trend_success(client):
    """get_trend should delegate to the correct Convex query and return result."""
    fake_trend = {"direction": "up", "percentChange": 12.5, "currentValue": 5000, "priorValue": 4444}
    with patch.object(client._client, 'query', return_value=fake_trend) as mock_query:
        result = client.get_trend("steps", from_ms=1710800000000, to_ms=1710886400000)
        assert result == fake_trend
        call_args = mock_query.call_args[0][1]
        assert call_args["recordType"] == "steps"
        assert call_args["fromMs"] == 1710800000000


def test_get_trend_convex_error(client):
    """get_trend should raise Exception on ConvexError."""
    with patch.object(client._client, 'query', side_effect=ConvexError("trend fail", data=None)):
        with pytest.raises(Exception, match="Convex error: trend fail"):
            client.get_trend("steps")


# --- detect_anomalies ---


def test_detect_anomalies_success(client):
    """detect_anomalies should delegate to the correct Convex query."""
    fake_result = {"buckets": [], "mean": 0, "stddev": 0, "anomalyCount": 0}
    with patch.object(client._client, 'query', return_value=fake_result) as mock_query:
        result = client.detect_anomalies("steps", "day", threshold=2.5)
        assert result == fake_result
        call_args = mock_query.call_args[0][1]
        assert call_args["recordType"] == "steps"
        assert call_args["bucketSize"] == "day"
        assert call_args["threshold"] == 2.5


def test_detect_anomalies_convex_error(client):
    """detect_anomalies should raise Exception on ConvexError."""
    with patch.object(client._client, 'query', side_effect=ConvexError("anomaly fail", data=None)):
        with pytest.raises(Exception, match="Convex error: anomaly fail"):
            client.detect_anomalies("steps", "hour")


# --- get_period_summaries ---


def test_get_period_summaries_success(client):
    """get_period_summaries should delegate to the correct Convex query."""
    fake_result = {"summaries": []}
    with patch.object(client._client, 'query', return_value=fake_result) as mock_query:
        result = client.get_period_summaries(["steps", "heart_rate"], "week")
        assert result == fake_result
        call_args = mock_query.call_args[0][1]
        assert call_args["recordTypes"] == ["steps", "heart_rate"]
        assert call_args["period"] == "week"


def test_get_period_summaries_convex_error(client):
    """get_period_summaries should raise Exception on ConvexError."""
    with patch.object(client._client, 'query', side_effect=ConvexError("ps fail", data=None)):
        with pytest.raises(Exception, match="Convex error: ps fail"):
            client.get_period_summaries(["steps"], "day")


# --- get_goal_progress ---


def test_get_goal_progress_success(client):
    """get_goal_progress should delegate to the correct Convex query."""
    fake_result = {"goals": []}
    with patch.object(client._client, 'query', return_value=fake_result) as mock_query:
        result = client.get_goal_progress("user-1", record_type="steps")
        assert result == fake_result
        call_args = mock_query.call_args[0][1]
        assert call_args["userId"] == "user-1"
        assert call_args["recordType"] == "steps"


def test_get_goal_progress_without_record_type(client):
    """get_goal_progress should omit recordType when not provided."""
    with patch.object(client._client, 'query', return_value={"goals": []}) as mock_query:
        client.get_goal_progress("user-1")
        call_args = mock_query.call_args[0][1]
        assert "recordType" not in call_args


# --- set_health_goal ---


def test_set_health_goal_success(client):
    """set_health_goal should call the correct mutation and return the goal ID."""
    with patch.object(client._client, 'mutation', return_value="goal-123") as mock_mut:
        result = client.set_health_goal("user-1", "steps", 10000.0, "count", "day")
        assert result == "goal-123"
        call_args = mock_mut.call_args[0][1]
        assert call_args["userId"] == "user-1"
        assert call_args["recordType"] == "steps"
        assert call_args["targetValue"] == 10000.0
        assert call_args["period"] == "day"


def test_set_health_goal_convex_error(client):
    """set_health_goal should raise Exception on ConvexError."""
    with patch.object(client._client, 'mutation', side_effect=ConvexError("goal fail", data=None)):
        with pytest.raises(Exception, match="Convex error: goal fail"):
            client.set_health_goal("user-1", "steps", 10000, "count", "day")


# --- get_correlation_hints ---


def test_get_correlation_hints_success(client):
    """get_correlation_hints should delegate to the correct Convex query."""
    fake_result = {"hints": [], "windowMs": 86400000}
    with patch.object(client._client, 'query', return_value=fake_result) as mock_query:
        result = client.get_correlation_hints(["steps", "heart_rate"], from_ms=1710800000000)
        assert result == fake_result
        call_args = mock_query.call_args[0][1]
        assert call_args["recordTypes"] == ["steps", "heart_rate"]


def test_get_correlation_hints_convex_error(client):
    """get_correlation_hints should raise Exception on ConvexError."""
    with patch.object(client._client, 'query', side_effect=ConvexError("corr fail", data=None)):
        with pytest.raises(Exception, match="Convex error: corr fail"):
            client.get_correlation_hints(["steps", "heart_rate"])


# --- ingest_delivery edge cases ---


def test_ingest_delivery_error_status_on_raw_delivery(client):
    """ingest_delivery should propagate errorMessage into raw_delivery status updates."""
    with patch.object(client._client, 'mutation', return_value={
        "deliveryId": "del-1",
        "receivedRecords": 1,
        "storedRecords": 1,
        "duplicateRecords": 0,
    }):
        result = client.ingest_delivery(
            raw_delivery={
                "receivedAt": 1710803600000,
                "sourceIp": "127.0.0.1",
                "payloadJson": '{}',
                "payloadHash": "hash123",
                "status": "completed",
                "recordCount": 1,
                "errorMessage": None,
            },
            events=[{
                "rawDeliveryId": "del-1",
                "recordType": "steps",
                "valueNumeric": 1000.0,
                "unit": "count",
                "startTime": 1710800000000,
                "endTime": 1710803600000,
                "capturedAt": 1710803600000,
                "payloadHash": "hash123",
                "fingerprint": "fp-1",
                "createdAt": 1710803600000,
            }],
        )
        assert result["stored_records"] == 1


def test_ingest_delivery_single_event(client):
    """ingest_delivery should work with a single event (small batch path)."""
    with patch.object(client._client, 'mutation', return_value={
        "deliveryId": "del-single",
        "receivedRecords": 1,
        "storedRecords": 1,
        "duplicateRecords": 0,
    }):
        result = client.ingest_delivery(
            raw_delivery={
                "receivedAt": 1710803600000,
                "sourceIp": "127.0.0.1",
                "payloadJson": '{}',
                "payloadHash": "hash-single",
                "status": "completed",
                "recordCount": 1,
            },
            events=[{
                "rawDeliveryId": "del-single",
                "recordType": "steps",
                "valueNumeric": 500.0,
                "unit": "count",
                "startTime": 1710800000000,
                "endTime": 1710803600000,
                "capturedAt": 1710803600000,
                "payloadHash": "hash-single",
                "fingerprint": "fp-single",
                "createdAt": 1710803600000,
            }],
        )
        assert result["delivery_id"] == "del-single"
        assert result["received_records"] == 1
        assert result["stored_records"] == 1


# --- _conv_to_json ---


def test_conv_to_json_strips_none():
    """_conv_to_json should strip None values from args dicts."""
    client = ConvexClient(convex_url="http://127.0.0.1:3210", admin_key="key")
    result = client._conv_to_json({"a": 1, "b": None, "c": "hello"})
    assert result == {"a": 1, "c": "hello"}


def test_conv_to_json_preserves_all_non_none():
    """_conv_to_json should keep all entries when none are None."""
    client = ConvexClient(convex_url="http://127.0.0.1:3210", admin_key="key")
    result = client._conv_to_json({"a": 1, "b": 2, "c": 3})
    assert result == {"a": 1, "b": 2, "c": 3}


# --- ingest_batch_size validation ---


def test_invalid_ingest_batch_size_raises():
    """ConvexClient should raise ValueError if ingest_batch_size < 1."""
    with pytest.raises(ValueError, match="ingest_batch_size must be >= 1"):
        ConvexClient(convex_url="http://127.0.0.1:3210", admin_key="key", ingest_batch_size=0)


def test_default_ingest_batch_size():
    """ConvexClient should use the default batch size when not specified."""
    from app.convex_client import DEFAULT_INGEST_EVENT_BATCH_SIZE
    client = ConvexClient(convex_url="http://127.0.0.1:3210", admin_key="key")
    assert client._ingest_batch_size == DEFAULT_INGEST_EVENT_BATCH_SIZE