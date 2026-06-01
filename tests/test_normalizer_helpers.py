"""Tests for normalizer helper functions and additional Android record types."""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from app.normalizer import (
    Normalizer,
    NormalizationError,
    AndroidPayloadNormalizer,
    _build_fingerprint,
    _compact_dict,
    _build_event,
    _device_id_from_record,
    _external_id_from_record,
    _now_ms,
)


# --- Helper function tests ---


def test_compact_dict_removes_none_values():
    """_compact_dict should remove entries with None values."""
    result = _compact_dict({"a": 1, "b": None, "c": "hello", "d": None})
    assert result == {"a": 1, "c": "hello"}


def test_compact_dict_preserves_all_non_none():
    """_compact_dict should return all entries when none are None."""
    result = _compact_dict({"a": 1, "b": 2})
    assert result == {"a": 1, "b": 2}


def test_compact_dict_empty():
    """_compact_dict should handle an empty dict."""
    assert _compact_dict({}) == {}


def test_now_ms_returns_positive_integer():
    """_now_ms should return a positive Unix timestamp in milliseconds."""
    ts = _now_ms()
    assert isinstance(ts, int)
    assert ts > 0


def test_now_ms_accuracy():
    """_now_ms should return the correct timestamp in milliseconds."""
    fixed_now = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    expected_ms = 1704067200000

    with patch("app.normalizer.datetime") as mock_datetime:
        mock_datetime.now.return_value = fixed_now
        assert _now_ms() == expected_ms


def test_device_id_from_record_snake_case():
    """_device_id_from_record should extract device_id from snake_case."""
    assert _device_id_from_record({"device_id": "watch-1"}) == "watch-1"


def test_device_id_from_record_camel_case():
    """_device_id_from_record should extract deviceId from camelCase."""
    assert _device_id_from_record({"deviceId": "pixel-watch"}) == "pixel-watch"


def test_device_id_from_record_prefers_snake_case():
    """_device_id_from_record should prefer device_id over deviceId."""
    assert _device_id_from_record({"device_id": "a", "deviceId": "b"}) == "a"


def test_device_id_from_record_none():
    """_device_id_from_record should return None when no device_id key exists."""
    assert _device_id_from_record({"value": 42}) is None


def test_external_id_from_record_snake_case():
    """_external_id_from_record should extract external_id from snake_case."""
    assert _external_id_from_record({"external_id": "ext-1"}) == "ext-1"


def test_external_id_from_record_camel_case():
    """_external_id_from_record should extract externalId from camelCase."""
    assert _external_id_from_record({"externalId": "ext-2"}) == "ext-2"


def test_external_id_from_record_none():
    """_external_id_from_record should return None when absent."""
    assert _external_id_from_record({"value": 42}) is None


def test_build_fingerprint_deterministic():
    """_build_fingerprint should produce the same hash for the same inputs."""
    kwargs = dict(
        record_type="steps",
        value_numeric=1000.0,
        unit="count",
        start_time=1710800000000,
        end_time=1710803600000,
        device_id="watch",
        external_id=None,
        metadata=None,
    )
    fp1 = _build_fingerprint(**kwargs)
    fp2 = _build_fingerprint(**kwargs)
    assert fp1 == fp2
    assert isinstance(fp1, str)
    assert len(fp1) == 64  # SHA-256 hex


def test_build_fingerprint_differs_for_different_inputs():
    """_build_fingerprint should produce different hashes for different values."""
    fp1 = _build_fingerprint(
        record_type="steps", value_numeric=1000.0, unit="count",
        start_time=1710800000000, end_time=1710803600000,
        device_id=None, external_id=None, metadata=None,
    )
    fp2 = _build_fingerprint(
        record_type="heart_rate", value_numeric=72.0, unit="bpm",
        start_time=1710800000000, end_time=1710803600000,
        device_id=None, external_id=None, metadata=None,
    )
    assert fp1 != fp2


def test_build_event_structure():
    """_build_event should produce a complete normalized event dict."""
    event = _build_event(
        raw_delivery_id="del-1",
        record_type="steps",
        value_numeric=1000.0,
        unit="count",
        start_time=1710800000000,
        end_time=1710803600000,
        captured_at=1710803600000,
        payload_hash="hash123",
        created_at=1710803600000,
        device_id="watch-1",
        external_id="ext-1",
        metadata={"source": "test"},
    )
    assert event["rawDeliveryId"] == "del-1"
    assert event["recordType"] == "steps"
    assert event["valueNumeric"] == 1000.0
    assert event["unit"] == "count"
    assert event["startTime"] == 1710800000000
    assert event["endTime"] == 1710803600000
    assert event["capturedAt"] == 1710803600000
    assert event["deviceId"] == "watch-1"
    assert event["externalId"] == "ext-1"
    assert event["payloadHash"] == "hash123"
    assert event["fingerprint"]
    assert event["metadata"] == {"source": "test"}
    assert event["createdAt"] == 1710803600000


def test_build_event_strips_none_optional_fields():
    """_build_event should omit None values from the output."""
    event = _build_event(
        raw_delivery_id="del-1",
        record_type="steps",
        value_numeric=1000.0,
        unit="count",
        start_time=1710800000000,
        end_time=1710803600000,
        captured_at=1710803600000,
        payload_hash="hash123",
        created_at=1710803600000,
        device_id=None,
        external_id=None,
        metadata=None,
    )
    assert "deviceId" not in event
    assert "externalId" not in event
    assert "metadata" not in event


# --- Android normalizer: additional record types ---


def test_android_sleep_normalization():
    """AndroidPayloadNormalizer should normalize sleep records with duration and stages."""
    payload = {
        "sleep": [
            {
                "session_end_time": "2024-03-19T07:00:00Z",
                "duration_seconds": 25200,
                "stages": [
                    {"stage": "deep", "start_time": "2024-03-19T00:00:00Z", "end_time": "2024-03-19T02:00:00Z", "duration_seconds": 7200},
                    {"stage": "light", "start_time": "2024-03-19T02:00:00Z", "end_time": "2024-03-19T07:00:00Z", "duration_seconds": 18000},
                ],
            }
        ]
    }
    normalizer = AndroidPayloadNormalizer(payload, "hash123", "delivery456")
    events = normalizer.normalize()
    assert len(events) == 1
    assert events[0]["recordType"] == "sleep"
    assert events[0]["valueNumeric"] == 25200.0
    assert events[0]["unit"] == "seconds"
    assert events[0]["metadata"]["stageCount"] == 2


def test_android_sleep_without_stages():
    """Sleep records without stages should have start_time=0."""
    payload = {
        "sleep": [
            {
                "session_end_time": "2024-03-19T07:00:00Z",
                "duration_seconds": 25200,
                "stages": [],
            }
        ]
    }
    normalizer = AndroidPayloadNormalizer(payload, "hash123", "delivery456")
    events = normalizer.normalize()
    assert len(events) == 1
    assert events[0]["startTime"] == 0  # empty stages -> start_time=0


def test_android_distance_normalization():
    """AndroidPayloadNormalizer should normalize distance records."""
    payload = {
        "distance": [{"meters": 1500.5, "start_time": "2024-03-19T08:00:00Z", "end_time": "2024-03-19T09:00:00Z"}]
    }
    normalizer = AndroidPayloadNormalizer(payload, "hash123", "delivery456")
    events = normalizer.normalize()
    assert len(events) == 1
    assert events[0]["recordType"] == "distance"
    assert events[0]["valueNumeric"] == 1500.5
    assert events[0]["unit"] == "m"


def test_android_active_calories_normalization():
    """AndroidPayloadNormalizer should normalize active_calories records."""
    payload = {
        "active_calories": [{"calories": 350.0, "start_time": "2024-03-19T08:00:00Z", "end_time": "2024-03-19T09:00:00Z"}]
    }
    normalizer = AndroidPayloadNormalizer(payload, "hash123", "delivery456")
    events = normalizer.normalize()
    assert len(events) == 1
    assert events[0]["recordType"] == "active_calories"
    assert events[0]["valueNumeric"] == 350.0
    assert events[0]["unit"] == "kcal"


def test_android_total_calories_normalization():
    """AndroidPayloadNormalizer should normalize total_calories records."""
    payload = {
        "total_calories": [{"calories": 2100.0, "start_time": "2024-03-19T00:00:00Z", "end_time": "2024-03-19T23:59:00Z"}]
    }
    normalizer = AndroidPayloadNormalizer(payload, "hash123", "delivery456")
    events = normalizer.normalize()
    assert len(events) == 1
    assert events[0]["recordType"] == "total_calories"
    assert events[0]["valueNumeric"] == 2100.0


def test_android_height_normalization():
    """AndroidPayloadNormalizer should normalize height records."""
    payload = {
        "height": [{"meters": 1.75, "time": "2024-03-19T08:00:00Z"}]
    }
    normalizer = AndroidPayloadNormalizer(payload, "hash123", "delivery456")
    events = normalizer.normalize()
    assert len(events) == 1
    assert events[0]["recordType"] == "height"
    assert events[0]["valueNumeric"] == 1.75
    assert events[0]["unit"] == "m"


def test_android_oxygen_saturation_normalization():
    """AndroidPayloadNormalizer should normalize oxygen_saturation records."""
    payload = {
        "oxygen_saturation": [{"percentage": 98.0, "time": "2024-03-19T10:00:00Z"}]
    }
    normalizer = AndroidPayloadNormalizer(payload, "hash123", "delivery456")
    events = normalizer.normalize()
    assert len(events) == 1
    assert events[0]["recordType"] == "oxygen_saturation"
    assert events[0]["valueNumeric"] == 98.0
    assert events[0]["unit"] == "%"


def test_android_resting_heart_rate_normalization():
    """AndroidPayloadNormalizer should normalize resting_heart_rate records."""
    payload = {
        "resting_heart_rate": [{"bpm": 62, "time": "2024-03-19T06:00:00Z"}]
    }
    normalizer = AndroidPayloadNormalizer(payload, "hash123", "delivery456")
    events = normalizer.normalize()
    assert len(events) == 1
    assert events[0]["recordType"] == "resting_heart_rate"
    assert events[0]["valueNumeric"] == 62.0
    assert events[0]["unit"] == "bpm"


def test_android_bmr_normalization():
    """AndroidPayloadNormalizer should normalize basal_metabolic_rate records."""
    payload = {
        "basal_metabolic_rate": [{"watts": 85.0, "time": "2024-03-19T06:00:00Z"}]
    }
    normalizer = AndroidPayloadNormalizer(payload, "hash123", "delivery456")
    events = normalizer.normalize()
    assert len(events) == 1
    assert events[0]["recordType"] == "basal_metabolic_rate"
    assert events[0]["valueNumeric"] == 85.0
    assert events[0]["unit"] == "W"


def test_android_body_fat_normalization():
    """AndroidPayloadNormalizer should normalize body_fat records."""
    payload = {
        "body_fat": [{"percentage": 22.5, "time": "2024-03-19T08:00:00Z"}]
    }
    normalizer = AndroidPayloadNormalizer(payload, "hash123", "delivery456")
    events = normalizer.normalize()
    assert len(events) == 1
    assert events[0]["recordType"] == "body_fat"
    assert events[0]["valueNumeric"] == 22.5
    assert events[0]["unit"] == "%"


def test_android_lean_body_mass_normalization():
    """AndroidPayloadNormalizer should normalize lean_body_mass records."""
    payload = {
        "lean_body_mass": [{"kilograms": 60.0, "time": "2024-03-19T08:00:00Z"}]
    }
    normalizer = AndroidPayloadNormalizer(payload, "hash123", "delivery456")
    events = normalizer.normalize()
    assert len(events) == 1
    assert events[0]["recordType"] == "lean_body_mass"
    assert events[0]["valueNumeric"] == 60.0
    assert events[0]["unit"] == "kg"


def test_android_vo2_max_normalization():
    """AndroidPayloadNormalizer should normalize vo2_max records."""
    payload = {
        "vo2_max": [{"ml_per_kg_per_min": 42.5, "time": "2024-03-19T10:00:00Z"}]
    }
    normalizer = AndroidPayloadNormalizer(payload, "hash123", "delivery456")
    events = normalizer.normalize()
    assert len(events) == 1
    assert events[0]["recordType"] == "vo2_max"
    assert events[0]["valueNumeric"] == 42.5
    assert events[0]["unit"] == "ml/kg/min"


def test_android_nutrition_normalization():
    """AndroidPayloadNormalizer should normalize nutrition records with macros in metadata."""
    payload = {
        "nutrition": [
            {
                "calories": 500.0,
                "protein_grams": 30.0,
                "carbs_grams": 50.0,
                "fat_grams": 15.0,
                "start_time": "2024-03-19T12:00:00Z",
                "end_time": "2024-03-19T12:30:00Z",
            }
        ]
    }
    normalizer = AndroidPayloadNormalizer(payload, "hash123", "delivery456")
    events = normalizer.normalize()
    assert len(events) == 1
    assert events[0]["recordType"] == "nutrition"
    assert events[0]["valueNumeric"] == 500.0
    assert events[0]["unit"] == "kcal"
    assert events[0]["metadata"]["proteinGrams"] == 30.0
    assert events[0]["metadata"]["carbsGrams"] == 50.0
    assert events[0]["metadata"]["fatGrams"] == 15.0


def test_android_nutrition_without_optional_macros():
    """Nutrition records with no calories should default to 0.0 value."""
    payload = {
        "nutrition": [
            {
                "start_time": "2024-03-19T12:00:00Z",
                "end_time": "2024-03-19T12:30:00Z",
                "protein_grams": 25.0,
            }
        ]
    }
    normalizer = AndroidPayloadNormalizer(payload, "hash123", "delivery456")
    events = normalizer.normalize()
    assert len(events) == 1
    assert events[0]["valueNumeric"] == 0.0
    assert events[0]["metadata"]["proteinGrams"] == 25.0


def test_android_heart_rate_variability_normalization():
    """AndroidPayloadNormalizer should normalize HRV records."""
    payload = {
        "heart_rate_variability": [{"rmssd_millis": 45.2, "time": "2024-03-19T06:00:00Z"}]
    }
    normalizer = AndroidPayloadNormalizer(payload, "hash123", "delivery456")
    events = normalizer.normalize()
    assert len(events) == 1
    assert events[0]["recordType"] == "heart_rate_variability"
    assert events[0]["valueNumeric"] == 45.2
    assert events[0]["unit"] == "ms"


def test_android_device_id_propagation():
    """Android normalizer should propagate device_id from records."""
    payload = {
        "steps": [{"count": 100, "start_time": "2024-01-01T00:00:00Z", "end_time": "2024-01-01T01:00:00Z", "device_id": "pixel-watch"}]
    }
    normalizer = AndroidPayloadNormalizer(payload, "hash123", "delivery456")
    event = normalizer.normalize()[0]
    assert event["deviceId"] == "pixel-watch"


def test_android_external_id_propagation():
    """Android normalizer should propagate externalId from records."""
    payload = {
        "steps": [{"count": 100, "start_time": "2024-01-01T00:00:00Z", "end_time": "2024-01-01T01:00:00Z", "externalId": "ext-abc"}]
    }
    normalizer = AndroidPayloadNormalizer(payload, "hash123", "delivery456")
    event = normalizer.normalize()[0]
    assert event["externalId"] == "ext-abc"


def test_android_instant_event_sets_equal_start_end_captured():
    """Instant event types (heart_rate, weight, etc.) should have start_time == end_time == captured_at."""
    payload = {
        "heart_rate": [{"bpm": 72, "time": "2024-03-19T10:00:00Z"}]
    }
    normalizer = AndroidPayloadNormalizer(payload, "hash123", "delivery456")
    event = normalizer.normalize()[0]
    assert event["startTime"] == event["endTime"] == event["capturedAt"]


def test_android_empty_payload_produces_no_events():
    """An empty Android payload should produce an empty list of events."""
    normalizer = AndroidPayloadNormalizer({}, "hash123", "delivery456")
    events = normalizer.normalize()
    assert events == []


def test_android_metadata_merges_existing_metadata():
    """Record-level metadata dict should be merged with auto-generated metadata."""
    payload = {
        "exercise": [
            {
                "type": "cycling",
                "start_time": "2024-03-19T08:00:00Z",
                "end_time": "2024-03-19T09:00:00Z",
                "duration_seconds": 3600,
                "metadata": {"source": "garmin", "notes": "outdoor"},
            }
        ]
    }
    normalizer = AndroidPayloadNormalizer(payload, "hash123", "delivery456")
    event = normalizer.normalize()[0]
    assert event["metadata"]["exerciseType"] == "cycling"
    assert event["metadata"]["source"] == "garmin"
    assert event["metadata"]["notes"] == "outdoor"


def test_normalizer_flat_record_preserves_metadata():
    """Flat normalizer should preserve optional metadata dict on records."""
    payload = {
        "records": [
            {
                "record_type": "steps",
                "value": 500,
                "unit": "count",
                "start_time_ms": 1710800000000,
                "end_time_ms": 1710803600000,
                "metadata": {"source": "fitbit"},
            }
        ]
    }
    normalizer = Normalizer(payload, "hash123", "delivery456")
    event = normalizer.normalize()[0]
    assert event["metadata"] == {"source": "fitbit"}


def test_normalizer_flat_record_omits_metadata_when_absent():
    """Flat normalizer should not include metadata key when no metadata is provided."""
    payload = {
        "records": [
            {
                "record_type": "steps",
                "value": 500,
                "unit": "count",
                "start_time_ms": 1710800000000,
                "end_time_ms": 1710803600000,
            }
        ]
    }
    normalizer = Normalizer(payload, "hash123", "delivery456")
    event = normalizer.normalize()[0]
    assert "metadata" not in event