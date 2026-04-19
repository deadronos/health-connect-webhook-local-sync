from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_overview_requires_auth():
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/analytics/overview")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_timeseries_returns_points():
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()

    with patch("app.routes.analytics.client") as mock_client:
        mock_client.get_analytics_timeseries.return_value = [
            {
                "bucketStart": 1710800000000,
                "count": 2,
                "sum": 1500.0,
                "avg": 750.0,
                "min": 500.0,
                "max": 1000.0,
                "latestValue": 1000.0,
                "latestAt": 1710803600000,
            }
        ]

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/analytics/timeseries",
                params={"record_type": "steps", "bucket": "day", "stat": "sum"},
                headers={"Authorization": "Bearer test-token"},
            )

    assert response.status_code == 200
    assert response.json()["points"][0]["value"] == 1500.0


@pytest.mark.asyncio
async def test_timeseries_invalid_record_type_returns_422():
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/analytics/timeseries",
            params={"record_type": "not-a-real-record", "bucket": "day", "stat": "sum"},
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_export_csv_returns_attachment():
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()

    with patch("app.routes.analytics.client") as mock_client:
        mock_client.list_analytics_events.return_value = [
            {
                "rawDeliveryId": "delivery-123",
                "recordType": "steps",
                "valueNumeric": 1000.0,
                "unit": "count",
                "startTime": 1710800000000,
                "endTime": 1710803600000,
                "capturedAt": 1710803600000,
                "deviceId": "pixel-watch",
                "externalId": None,
                "payloadHash": "hash123",
                "fingerprint": "fingerprint-123",
                "metadata": {"source": "fixture"},
            }
        ]

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/analytics/export.csv",
                headers={"Authorization": "Bearer test-token"},
            )

    assert response.status_code == 200
    assert response.headers["content-disposition"] == "attachment; filename=health-events.csv"
    assert "record_type" in response.text


@pytest.mark.asyncio
async def test_events_legacy_row_without_fingerprint_uses_payload_hash():
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()

    with patch("app.routes.analytics.client") as mock_client:
        mock_client.list_analytics_events.return_value = [
            {
                "rawDeliveryId": "delivery-legacy",
                "recordType": "steps",
                "valueNumeric": 1000.0,
                "unit": "count",
                "startTime": 1710800000000,
                "endTime": 1710803600000,
                "capturedAt": 1710803600000,
                "deviceId": None,
                "externalId": None,
                "payloadHash": "legacy-hash-123",
                "metadata": None,
            }
        ]

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/analytics/events",
                headers={"Authorization": "Bearer test-token"},
            )

    assert response.status_code == 200
    assert response.json()["events"][0]["fingerprint"] == "legacy-hash-123"


@pytest.mark.asyncio
async def test_export_csv_legacy_row_without_fingerprint_uses_payload_hash():
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()

    with patch("app.routes.analytics.client") as mock_client:
        mock_client.list_analytics_events.return_value = [
            {
                "rawDeliveryId": "delivery-legacy",
                "recordType": "steps",
                "valueNumeric": 1000.0,
                "unit": "count",
                "startTime": 1710800000000,
                "endTime": 1710803600000,
                "capturedAt": 1710803600000,
                "deviceId": None,
                "externalId": None,
                "payloadHash": "legacy-hash-123",
                "metadata": None,
            }
        ]

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/analytics/export.csv",
                headers={"Authorization": "Bearer test-token"},
            )

    assert response.status_code == 200
    assert "legacy-hash-123" in response.text
