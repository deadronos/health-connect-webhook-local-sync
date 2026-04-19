import hashlib
from datetime import datetime, UTC
from typing import Optional

from convex import ConvexError
from convex.http_client import ConvexHttpClient

from app.config import Settings


DEFAULT_INGEST_EVENT_BATCH_SIZE = 1000


class ConvexClient:
    """HTTP client for Convex self-hosted, wrapping ConvexHttpClient."""

    def __init__(self, convex_url: str, admin_key: str, ingest_batch_size: int = DEFAULT_INGEST_EVENT_BATCH_SIZE):
        # ConvexHttpClient connects to the Convex backend at :3210
        self._client = ConvexHttpClient(convex_url)
        self._client.set_admin_auth(admin_key)
        self._convex_url = convex_url
        if ingest_batch_size < 1:
            raise ValueError("ingest_batch_size must be >= 1")
        self._ingest_batch_size = ingest_batch_size

    def _conv_to_json(self, args: dict) -> dict:
        """Convert Python args to Convex-compatible format - remove None values."""
        return {k: v for k, v in args.items() if v is not None}

    def _iter_event_chunks(self, events: list[dict]):
        for start in range(0, len(events), self._ingest_batch_size):
            yield events[start:start + self._ingest_batch_size]

    def _store_raw_delivery_payload(self, raw_delivery: dict) -> str:
        result = self._client.mutation("mutations.js:storeRawDelivery", self._conv_to_json(raw_delivery))
        return str(result) if result else ""

    def _ingest_delivery_chunk(self, raw_delivery_id: str, events: list[dict]) -> dict:
        result = self._client.mutation("mutations.js:ingestNormalizedEventsChunk", {
            "rawDeliveryId": raw_delivery_id,
            "events": events,
        })
        return {
            "received_records": int(result["receivedRecords"]),
            "stored_records": int(result["storedRecords"]),
            "duplicate_records": int(result.get("duplicateRecords", 0)),
        }

    def store_raw_delivery(
        self,
        source_ip: str,
        user_agent: Optional[str],
        payload_json: str,
        record_count: int,
        status: str = "stored",
        error_message: Optional[str] = None,
        data_class: str = "valid",
        data_class_reason: Optional[str] = None,
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
                "dataClass": data_class,
                "dataClassReason": data_class_reason,
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
            if len(events) <= self._ingest_batch_size:
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

            delivery_id = self._store_raw_delivery_payload(raw_delivery)
            received_records = 0
            stored_records = 0
            duplicate_records = 0

            for chunk in self._iter_event_chunks(events):
                chunk_result = self._ingest_delivery_chunk(delivery_id, chunk)
                received_records += chunk_result["received_records"]
                stored_records += chunk_result["stored_records"]
                duplicate_records += chunk_result["duplicate_records"]

            return {
                "delivery_id": delivery_id,
                "received_records": received_records,
                "stored_records": stored_records,
                "duplicate_records": duplicate_records,
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
