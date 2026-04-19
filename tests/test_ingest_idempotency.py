"""Tests for idempotent ingest behavior through the Convex write path."""

import pytest
from unittest.mock import patch


@pytest.mark.asyncio
async def test_ingest_route_uses_single_client_delivery_call():
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()
    payload = {
        "records": [
            {
                "record_type": "steps",
                "value": 1000,
                "unit": "count",
                "start_time_ms": 1710800000000,
                "end_time_ms": 1710803600000,
            },
            {
                "record_type": "steps",
                "value": 1000,
                "unit": "count",
                "start_time_ms": 1710800000000,
                "end_time_ms": 1710803600000,
            },
        ]
    }

    with patch("app.routes.ingest.client") as mock_client:
        mock_client.ingest_delivery.return_value = {
            "delivery_id": "delivery-123",
            "received_records": 2,
            "stored_records": 1,
            "duplicate_records": 1,
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/ingest/health/v1",
                json=payload,
                headers={"Authorization": "Bearer test-token"},
            )

    assert response.status_code == 200
    assert response.json()["stored_records"] == 1
    mock_client.ingest_delivery.assert_called_once()