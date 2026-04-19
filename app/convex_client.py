import hashlib
from datetime import datetime, UTC
from typing import Optional

from convex import ConvexError
from convex.http_client import ConvexHttpClient

from app.config import Settings


class ConvexClient:
    """HTTP client for Convex self-hosted, wrapping ConvexHttpClient."""

    def __init__(self, convex_url: str, admin_key: str):
        # ConvexHttpClient connects to the Convex backend at :3210
        self._client = ConvexHttpClient(convex_url)
        self._client.set_admin_auth(admin_key)
        self._convex_url = convex_url

    def _conv_to_json(self, args: dict) -> dict:
        """Convert Python args to Convex-compatible format - remove None values."""
        return {k: v for k, v in args.items() if v is not None}

    def store_raw_delivery(
        self,
        source_ip: str,
        user_agent: Optional[str],
        payload_json: str,
        record_count: int,
        status: str = "stored",
        error_message: Optional[str] = None,
    ) -> str:
        payload_hash = hashlib.sha256(payload_json.encode()).hexdigest()
        received_at = int(datetime.now(UTC).timestamp() * 1000)
        try:
            result = self._client.mutation("mutations.js:storeRawDelivery", self._conv_to_json({
                "receivedAt": received_at,
                "sourceIp": source_ip,
                "userAgent": user_agent,
                "payloadJson": payload_json,
                "payloadHash": payload_hash,
                "status": status,
                "errorMessage": error_message,
                "recordCount": record_count,
            }))
            return str(result) if result else ""
        except ConvexError as e:
            raise Exception(f"Convex error: {e}") from e

    def store_health_events(self, events: list[dict]) -> list[str]:
        if not events:
            return []
        try:
            result = self._client.mutation("mutations.js:storeHealthEvents", {
                "events": events,
            })
            return [str(r) for r in (result or [])]
        except ConvexError as e:
            raise Exception(f"Convex error: {e}") from e

    def ingest_delivery(self, raw_delivery: dict, events: list[dict]) -> dict:
        try:
            result = self._client.mutation("mutations.js:ingestNormalizedDelivery", {
                "rawDelivery": self._conv_to_json(raw_delivery),
                "events": events,
            })
            return {
                "delivery_id": str(result["deliveryId"]),
                "received_records": int(result["receivedRecords"]),
                "stored_records": int(result["storedRecords"]),
                "duplicate_records": int(result.get("duplicateRecords", 0)),
            }
        except ConvexError as e:
            raise Exception(f"Convex error: {e}") from e

    def check_duplicate(self, payload_hash: str) -> bool:
        try:
            result = self._client.mutation("mutations.js:checkDuplicateDelivery", {
                "payloadHash": payload_hash,
            })
            return bool(result)
        except ConvexError as e:
            raise Exception(f"Convex error: {e}") from e

    def list_recent_deliveries(self, limit: int = 10) -> list[dict]:
        try:
            result = self._client.query("queries.js:listRecentDeliveries", {
                "limit": limit,
            })
            return result if isinstance(result, list) else []
        except ConvexError as e:
            raise Exception(f"Convex error: {e}") from e

    def get_analytics_overview(
        self,
        from_ms: Optional[int] = None,
        to_ms: Optional[int] = None,
        record_types: Optional[list[str]] = None,
        device_id: Optional[str] = None,
    ) -> list[dict]:
        try:
            result = self._client.query("queries.js:getAnalyticsOverview", self._conv_to_json({
                "fromMs": from_ms,
                "toMs": to_ms,
                "recordTypes": record_types,
                "deviceId": device_id,
            }))
            return result if isinstance(result, list) else []
        except ConvexError as e:
            raise Exception(f"Convex error: {e}") from e

    def get_analytics_timeseries(
        self,
        *,
        record_type: str,
        bucket_size: str,
        from_ms: Optional[int] = None,
        to_ms: Optional[int] = None,
        device_id: Optional[str] = None,
    ) -> list[dict]:
        try:
            result = self._client.query("queries.js:getAnalyticsTimeseries", self._conv_to_json({
                "recordType": record_type,
                "bucketSize": bucket_size,
                "fromMs": from_ms,
                "toMs": to_ms,
                "deviceId": device_id,
            }))
            return result if isinstance(result, list) else []
        except ConvexError as e:
            raise Exception(f"Convex error: {e}") from e

    def list_analytics_events(
        self,
        *,
        from_ms: Optional[int] = None,
        to_ms: Optional[int] = None,
        record_types: Optional[list[str]] = None,
        device_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        try:
            result = self._client.query("queries.js:listAnalyticsEvents", self._conv_to_json({
                "fromMs": from_ms,
                "toMs": to_ms,
                "recordTypes": record_types,
                "deviceId": device_id,
                "limit": limit,
            }))
            return result if isinstance(result, list) else []
        except ConvexError as e:
            raise Exception(f"Convex error: {e}") from e

    def check_db_health(self) -> dict:
        try:
            result = self._client.query("queries.js:checkDbHealth", {})
            return result if isinstance(result, dict) else {}
        except ConvexError as e:
            raise Exception(f"Convex error: {e}") from e
