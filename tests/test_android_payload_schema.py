from app.schemas import AndroidPayload

def test_parse_steps():
    payload = AndroidPayload.model_validate({
        "steps": [{"count": 1000, "start_time": "2024-01-01T00:00:00Z", "end_time": "2024-01-01T01:00:00Z"}]
    })
    assert payload.steps[0].count == 1000