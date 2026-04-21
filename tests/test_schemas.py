"""Tests for Pydantic schema validation of ingest request/response formats."""

from app.schemas import IngestRequest, WebhookRecord


def test_ingest_request_parses_valid_payload():
    """IngestRequest should correctly parse a valid generic-format payload."""
    payload = {
        "records": [
            {
                "record_type": "steps",
                "value": 8421,
                "unit": "count",
                "start_time_ms": 1713446400000,
                "end_time_ms": 1713489296000,
            }
        ]
    }
    req = IngestRequest.model_validate(payload)
    assert len(req.records) == 1
    assert req.records[0].record_type == "steps"
    assert req.records[0].value == 8421
