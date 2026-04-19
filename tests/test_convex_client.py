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


def test_ingest_delivery_calls_atomic_mutation():
    """ingest_delivery delegates to the new idempotent write mutation."""
    client = ConvexClient(convex_url="http://127.0.0.1:3210", admin_key="key")

    with patch.object(
        client._client,
        "mutation",
        return_value={
            "deliveryId": "delivery-123",
            "receivedRecords": 2,
            "storedRecords": 1,
            "duplicateRecords": 1,
        },
    ) as mock_mut:
        result = client.ingest_delivery(
            raw_delivery={
                "receivedAt": 1710803600000,
                "sourceIp": "127.0.0.1",
                "userAgent": "pytest",
                "payloadJson": '{"records": []}',
                "payloadHash": "hash123",
                "status": "stored",
                "recordCount": 2,
            },
            events=[
                {
                    "rawDeliveryId": "delivery-123",
                    "recordType": "steps",
                    "valueNumeric": 1000.0,
                    "unit": "count",
                    "startTime": 1710800000000,
                    "endTime": 1710803600000,
                    "capturedAt": 1710803600000,
                    "payloadHash": "hash123",
                    "fingerprint": "fingerprint-123",
                    "createdAt": 1710803600000,
                }
            ],
        )

    assert result["stored_records"] == 1
    mock_mut.assert_called_once()
    assert mock_mut.call_args[0][0] == "mutations.js:ingestNormalizedDelivery"