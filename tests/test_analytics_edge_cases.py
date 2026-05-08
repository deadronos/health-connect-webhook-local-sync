"""Tests for analytics route edge cases: from_ms > to_ms validation, timeseries stat extraction, events filtering, debug endpoint."""

import pytest
from unittest.mock import patch


@pytest.mark.asyncio
async def test_overview_from_ms_greater_than_to_ms_returns_422():
    """Overview should reject when from_ms > to_ms."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/login", data={"token": "test-token", "next": "/dashboard"})
        response = await client.get(
            "/analytics/overview",
            params={"from_ms": 9999999999999, "to_ms": 1000},
        )
    assert response.status_code == 422
    assert "from_ms must be less than or equal to to_ms" in response.json()["detail"]


@pytest.mark.asyncio
async def test_timeseries_from_ms_greater_than_to_ms_returns_422():
    """Timeseries should reject when from_ms > to_ms."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/login", data={"token": "test-token", "next": "/dashboard"})
        response = await client.get(
            "/analytics/timeseries",
            params={"record_type": "steps", "bucket": "day", "stat": "sum",
                    "from_ms": 9999999999999, "to_ms": 1000},
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_events_requires_auth():
    """The /analytics/events endpoint should require authentication."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/analytics/events")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_export_csv_requires_auth():
    """The /analytics/export.csv endpoint should require authentication."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/analytics/export.csv")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_timeseries_all_stat_types():
    """Timeseries should correctly extract each stat type from Convex response rows."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()

    stat_expectations = {
        "count": 5,
        "sum": 1500.0,
        "avg": 300.0,
        "min": 100.0,
        "max": 500.0,
        "latest_value": 500.0,
    }

    for stat, expected_value in stat_expectations.items():
        with patch("app.routes.analytics.client") as mock_client:
            mock_client.get_analytics_timeseries.return_value = [
                {
                    "bucketStart": 1710800000000,
                    "count": 5,
                    "sum": 1500.0,
                    "avg": 300.0,
                    "min": 100.0,
                    "max": 500.0,
                    "latestValue": 500.0,
                    "latestAt": 1710803600000,
                }
            ]

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                # Re-login for each iteration since each is a new app
                await client.post("/login", data={"token": "test-token", "next": "/dashboard"})
                response = await client.get(
                    "/analytics/timeseries",
                    params={"record_type": "steps", "bucket": "day", "stat": stat},
                )
            assert response.status_code == 200
            points = response.json()["points"]
            assert len(points) == 1
            assert points[0]["value"] == expected_value


@pytest.mark.asyncio
async def test_events_with_filters():
    """The events endpoint should pass filter params to Convex and return events."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()

    with patch("app.routes.analytics.client") as mock_client:
        mock_client.list_analytics_events.return_value = [
            {
                "rawDeliveryId": "del-1",
                "recordType": "steps",
                "valueNumeric": 1000.0,
                "unit": "count",
                "startTime": 1710800000000,
                "endTime": 1710803600000,
                "capturedAt": 1710803600000,
                "deviceId": "watch-1",
                "externalId": None,
                "payloadHash": "hash1",
                "fingerprint": "fp-1",
                "metadata": None,
            }
        ]

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/login", data={"token": "test-token", "next": "/dashboard"})
            response = await client.get(
                "/analytics/events",
                params={"record_type": "steps", "device_id": "watch-1", "limit": 50},
            )

    assert response.status_code == 200
    assert len(response.json()["events"]) == 1
    assert response.json()["events"][0]["device_id"] == "watch-1"


@pytest.mark.asyncio
async def test_debug_recent_requires_bearer_auth():
    """The /debug/recent endpoint should require Bearer auth (not session)."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Login to get a session — this should NOT grant debug access
        await client.post("/login", data={"token": "test-token", "next": "/dashboard"})
        response = await client.get("/debug/recent")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_debug_recent_with_bearer():
    """The /debug/recent endpoint should work with Bearer auth."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()

    with patch("app.routes.debug.client") as mock_client:
        mock_client.list_recent_deliveries.return_value = [
            {"deliveryId": "del-1", "receivedAt": 1710803600000, "recordCount": 5, "status": "completed"}
        ]

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/debug/recent",
                headers={"Authorization": "Bearer test-token"},
                params={"limit": 5},
            )

    assert response.status_code == 200
    data = response.json()
    assert len(data["deliveries"]) == 1
    assert data["deliveries"][0]["delivery_id"] == "del-1"
    assert data["deliveries"][0]["status"] == "completed"


@pytest.mark.asyncio
async def test_debug_recent_with_custom_limit():
    """The /debug/recent endpoint should accept a custom limit parameter."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()

    with patch("app.routes.debug.client") as mock_client:
        mock_client.list_recent_deliveries.return_value = []

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/debug/recent",
                headers={"Authorization": "Bearer test-token"},
                params={"limit": 50},
            )

    assert response.status_code == 200
    mock_client.list_recent_deliveries.assert_called_once_with(limit=50)


@pytest.mark.asyncio
async def test_overview_with_record_type_filter():
    """Overview endpoint should pass record_type filter parameters to Convex."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()

    with patch("app.routes.analytics.client") as mock_client:
        mock_client.get_analytics_overview.return_value = [
            {"recordType": "steps", "count": 10, "min": 100, "max": 5000, "avg": 2500, "sum": 25000, "latestValue": 3000, "latestAt": 1710803600000}
        ]

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/login", data={"token": "test-token", "next": "/dashboard"})
            response = await client.get(
                "/analytics/overview",
                params={"record_type": "steps"},
            )

    assert response.status_code == 200
    assert response.json()["cards"][0]["record_type"] == "steps"


@pytest.mark.asyncio
async def test_overview_with_device_filter():
    """Overview endpoint should pass device_id filter to Convex."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()

    with patch("app.routes.analytics.client") as mock_client:
        mock_client.get_analytics_overview.return_value = []

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/login", data={"token": "test-token", "next": "/dashboard"})
            response = await client.get(
                "/analytics/overview",
                params={"device_id": "pixel-watch"},
            )

    assert response.status_code == 200
    mock_client.get_analytics_overview.assert_called_once()
    call_kwargs = mock_client.get_analytics_overview.call_args
    assert call_kwargs.kwargs.get("device_id") == "pixel-watch" or call_kwargs[1].get("device_id") == "pixel-watch"