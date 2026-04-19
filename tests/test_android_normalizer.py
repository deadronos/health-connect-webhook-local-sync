from app.normalizer import AndroidPayloadNormalizer

def test_normalize_steps():
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
    payload = {
        "weight": [{"kilograms": 70.5, "time": "2024-01-01T08:00:00Z"}]
    }
    normalizer = AndroidPayloadNormalizer(payload, "hash123", "delivery456")
    events = normalizer.normalize()
    assert len(events) == 1
    assert events[0]["recordType"] == "weight"
    assert events[0]["valueNumeric"] == 70.5
    assert events[0]["unit"] == "kg"