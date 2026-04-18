from unittest.mock import patch, MagicMock
from app.convex_client import ConvexClient


@patch.object(ConvexClient, '_conv_to_json', return_value={})
def test_store_raw_delivery_calls_mutation(_mock_conv):
    """store_raw_delivery delegates to mutations.js:storeRawDelivery via ConvexHttpClient."""
    client = ConvexClient(convex_url="http://127.0.0.1:3210", admin_key="key")

    with patch.object(client._client, 'mutation', return_value="delivery-123") as mock_mut:
        result = client.store_raw_delivery(
            source_ip="127.0.0.1",
            user_agent="test-agent",
            payload_json='{"test": true}',
            record_count=5,
        )
        assert result == "delivery-123"
        mock_mut.assert_called_once()
        call_args = mock_mut.call_args
        assert call_args[0][0] == "mutations.js:storeRawDelivery"