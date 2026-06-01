"""Tests for AndroidPayloadNormalizer which handles Android Health Connect format normalization."""

import pytest
from app.normalizer import AndroidPayloadNormalizer


def test_normalize_steps():
    """AndroidPayloadNormalizer should correctly normalize steps records."""
    payload = {
        "steps": [{"count": 8421, "start_time": "2024-01-01T00:00:00Z", "end_time": "2024-01-01T01:00:00Z"}]
    }
    normalizer = AndroidPayloadNormalizer(payload, "hash123", "delivery456")
    events = normalizer.normalize()
    assert len(events) == 1
    assert events[0]["recordType"] == "steps"
    assert events[0]["valueNumeric"] == 8421.0
    assert events[0]["unit"] == "count"


def test_android_exercise_record_emits_metadata_and_fingerprint():
    """Exercise records should have exerciseType in metadata and a valid fingerprint."""
    payload = {
        "exercise": [
            {
                "type": "running",
                "start_time": "2024-03-19T10:00:00Z",
                "end_time": "2024-03-19T10:30:00Z",
                "duration_seconds": 1800,
            }
        ]
    }
    normalizer = AndroidPayloadNormalizer(payload, "hash123", "delivery456")
    event = normalizer.normalize()[0]

    assert event["recordType"] == "exercise"
    assert event["metadata"] == {"exerciseType": "running"}
    assert isinstance(event["fingerprint"], str)
    assert event["fingerprint"]


def test_normalize_heart_rate():
    """AndroidPayloadNormalizer should correctly normalize heart_rate instant events."""
    payload = {
        "heart_rate": [{"bpm": 72, "time": "2024-01-01T10:00:00Z"}]
    }
    normalizer = AndroidPayloadNormalizer(payload, "hash123", "delivery456")
    events = normalizer.normalize()
    assert len(events) == 1
    assert events[0]["recordType"] == "heart_rate"
    assert events[0]["valueNumeric"] == 72.0
    assert events[0]["unit"] == "bpm"


def test_normalize_weight():
    """AndroidPayloadNormalizer should correctly normalize weight records in kg."""
    payload = {
        "weight": [{"kilograms": 70.5, "time": "2024-01-01T08:00:00Z"}]
    }
    normalizer = AndroidPayloadNormalizer(payload, "hash123", "delivery456")
    events = normalizer.normalize()
    assert len(events) == 1
    assert events[0]["recordType"] == "weight"
    assert events[0]["valueNumeric"] == 70.5
    assert events[0]["unit"] == "kg"


@pytest.mark.parametrize("ts, expected", [
    ("2024-01-01T00:00:00Z", 1704067200000),
    ("2024-01-01T00:00:00+00:00", 1704067200000),
    ("invalid-date", 0),
    ("2024-13-01T00:00:00Z", 0),  # Invalid month
    ("2024-02-30T00:00:00Z", 0),  # Non-existent day
    ("not-a-timestamp", 0),
    ("", 0),
    (None, 0),
])
def test_parse_instant(ts, expected):
    """AndroidPayloadNormalizer._parse_instant should handle valid, invalid, and empty strings."""
    normalizer = AndroidPayloadNormalizer({}, "hash", "del")
    assert normalizer._parse_instant(ts) == expected

def test_malformed_record_returns_none():
    """AndroidPayloadNormalizer should skip records missing required keys."""
    payload = {
        "steps": [
            {"count": 8421, "start_time": "2024-01-01T00:00:00Z"},  # Missing end_time
            {"end_time": "2024-01-01T01:00:00Z", "start_time": "2024-01-01T00:00:00Z"}, # Missing count
        ]
    }
    normalizer = AndroidPayloadNormalizer(payload, "hash123", "delivery456")
    events = normalizer.normalize()
    assert len(events) == 0
