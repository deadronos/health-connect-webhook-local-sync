from unittest.mock import patch, MagicMock
from app.convex_client import ConvexClient

def test_convex_client_site_url():
    client = ConvexClient(
        convex_url="http://127.0.0.1:3210",
        admin_key="test-key"
    )
    assert client.site_url == "http://127.0.0.1:3210/api/site"

@patch("httpx.Client")
def test_store_raw_delivery_calls_mutation(mock_client):
    mock_instance = MagicMock()
    mock_instance.__enter__ = MagicMock(return_value=mock_instance)
    mock_instance.__exit__ = MagicMock(return_value=False)
    mock_instance.post.return_value = MagicMock(
        status_code=200,
        json=lambda: {"value": "delivery-123"}
    )
    mock_client.return_value = mock_instance

    client = ConvexClient(convex_url="http://127.0.0.1:3210", admin_key="key")
    result = client.store_raw_delivery(
        source_ip="127.0.0.1",
        user_agent="test-agent",
        payload_json='{"test": true}',
        record_count=5,
    )
    assert result == "delivery-123"
    mock_instance.post.assert_called_once()