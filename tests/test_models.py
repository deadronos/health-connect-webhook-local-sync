from app.models import HealthEvent, RecordType

def test_health_event_record_type_enum():
    assert RecordType.STEPS.value == "steps"
    assert RecordType.EXERCISE.value == "exercise"
    assert RecordType.HEART_RATE.value == "heart_rate"
    assert RecordType.RESTING_HEART_RATE.value == "resting_heart_rate"
    assert RecordType.WEIGHT.value == "weight"

def test_health_event_model():
    event = HealthEvent(
        source="health-connect-webhook",
        record_type=RecordType.STEPS,
        value=8421,
        unit="count",
        start_time=1713446400000,
        end_time=1713489296000,
        captured_at=1713489302000,
        payload_hash="abc123",
        raw_delivery_id="delivery-123",
        fingerprint="fingerprint-123",
        metadata={"source": "fixture"},
    )
    assert event.record_type == RecordType.STEPS
    assert event.value == 8421.0
    assert event.unit == "count"
    assert event.fingerprint == "fingerprint-123"
    assert event.metadata == {"source": "fixture"}