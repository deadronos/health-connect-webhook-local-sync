"""Tests for the Normalizer class which handles generic webhook format normalization."""

import pytest
from app.normalizer import Normalizer, NormalizationError


def test_normalize_steps():
    """Normalizer.normalize() should produce a correct event for steps records."""
    payload = {
        "records": [
            {
                "record_type": "steps",
                "value": 8421,
                "unit": "count",
                "start_time_ms": 1713446400000,
                "end_time_ms": 1713489296000,
                "captured_at_ms": 1713489302000,
            }
        ]
    }
    normalizer = Normalizer(payload=payload, payload_hash="abc123", delivery_id="del-1")
    events = normalizer.normalize()
    assert len(events) == 1
    assert events[0]["recordType"] == "steps"
    assert events[0]["valueNumeric"] == 8421.0
    assert events[0]["unit"] == "count"


def test_flat_record_preserves_device_id_and_fingerprint():
    """device_id should be carried through to the normalized event, and fingerprint must be a non-empty string."""
    payload = {
        "records": [
            {
                "record_type": "steps",
                "value": 1000,
                "unit": "count",
                "start_time_ms": 1710800000000,
                "end_time_ms": 1710803600000,
                "device_id": "pixel-watch",
            }
        ]
    }
    normalizer = Normalizer(payload, "hash123", "delivery456")
    event = normalizer.normalize()[0]

    assert event["deviceId"] == "pixel-watch"
    assert isinstance(event["fingerprint"], str)
    assert event["fingerprint"]


def test_normalize_heart_rate():
    """Normalizer should correctly handle heart_rate records with bpm unit."""
    payload = {
        "records": [
            {
                "record_type": "heart_rate",
                "value": 72,
                "unit": "bpm",
                "start_time_ms": 1713446400000,
                "end_time_ms": 1713489296000,
                "captured_at_ms": 1713489302000,
            }
        ]
    }
    normalizer = Normalizer(payload=payload, payload_hash="abc123", delivery_id="del-1")
    events = normalizer.normalize()
    assert len(events) == 1
    assert events[0]["recordType"] == "heart_rate"
    assert events[0]["valueNumeric"] == 72.0
    assert events[0]["unit"] == "bpm"


def test_normalize_weight():
    """Normalizer should correctly handle weight records in kg."""
    payload = {
        "records": [
            {
                "record_type": "weight",
                "value": 72.5,
                "unit": "kg",
                "start_time_ms": 1713446400000,
                "end_time_ms": 1713489296000,
                "captured_at_ms": 1713489302000,
            }
        ]
    }
    normalizer = Normalizer(payload=payload, payload_hash="abc123", delivery_id="del-1")
    events = normalizer.normalize()
    assert len(events) == 1
    assert events[0]["recordType"] == "weight"
    assert events[0]["valueNumeric"] == 72.5


def test_normalize_unsupported_type_raises():
    """Normalizer.normalize() should raise NormalizationError for unsupported record types."""
    payload = {
        "records": [
            {
                "record_type": "blood_oxygen",
                "value": 98,
                "unit": "%",
                "start_time_ms": 1713446400000,
                "end_time_ms": 1713489296000,
            }
        ]
    }
    normalizer = Normalizer(payload=payload, payload_hash="abc123", delivery_id="del-1")
    with pytest.raises(NormalizationError, match="unsupported record type"):
        normalizer.normalize()


def test_normalize_mixed():
    """Normalizer should correctly handle payloads containing multiple record types."""
    payload = {
        "records": [
            {"record_type": "steps", "value": 8421, "unit": "count",
             "start_time_ms": 1713446400000, "end_time_ms": 1713489296000},
            {"record_type": "heart_rate", "value": 72, "unit": "bpm",
             "start_time_ms": 1713446400000, "end_time_ms": 1713489296000},
        ]
    }
    normalizer = Normalizer(payload=payload, payload_hash="abc123", delivery_id="del-1")
    events = normalizer.normalize()
    assert len(events) == 2
