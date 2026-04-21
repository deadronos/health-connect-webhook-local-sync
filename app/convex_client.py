"""HTTP client for interacting with a self-hosted Convex deployment."""

import hashlib
from datetime import datetime, UTC
from typing import Optional

from convex import ConvexError
from convex.http_client import ConvexHttpClient

from app.config import Settings


DEFAULT_INGEST_EVENT_BATCH_SIZE = 1000


class ConvexClient:
    """HTTP client for Convex self-hosted, wrapping ConvexHttpClient.

    Provides typed methods for all Convex mutations and queries used by
    the webhook ingest service, including raw delivery storage, health event
    ingestion, and analytics queries.

    Attributes:
        DEFAULT_INGEST_EVENT_BATCH_SIZE: Default number of events per chunk for large deliveries.
    """

    def __init__(self, convex_url: str, admin_key: str, ingest_batch_size: int = DEFAULT_INGEST_EVENT_BATCH_SIZE):
        """Initialize the Convex HTTP client.

        Args:
            convex_url: Base URL of the Convex self-hosted deployment.
            admin_key: Admin authentication key for Convex.
            ingest_batch_size: Maximum number of events to send in a single
                chunk when ingesting large deliveries (default 1000).

        Raises:
            ValueError: If ingest_batch_size is less than 1.
        """
        # ConvexHttpClient connects to the Convex backend at :3210
        self._client = ConvexHttpClient(convex_url)
        self._client.set_admin_auth(admin_key)
        self._convex_url = convex_url
        if ingest_batch_size < 1:
            raise ValueError("ingest_batch_size must be >= 1")
        self._ingest_batch_size = ingest_batch_size

    def _conv_to_json(self, args: dict) -> dict:
        """Convert Python args to Convex-compatible format by removing None values.

        Convex mutations reject None values for optional fields.

        Args:
            args: Dictionary of arguments to pass to a Convex mutation/query.

        Returns:
            A new dictionary with all None values removed.
        """
        return {k: v for k, v in args.items() if v is not None}

    def _iter_event_chunks(self, events: list[dict]):
        """Yield successive chunks of events of at most _ingest_batch_size.

        Args:
            events: Full list of events to split into chunks.

        Yields:
            Lists of events, each with at most _ingest_batch_size elements.
        """
        for start in range(0, len(events), self._ingest_batch_size):
            yield events[start:start + self._ingest_batch_size]

    def _store_raw_delivery_payload(self, raw_delivery: dict) -> str:
        """Store the raw delivery payload in Convex and return its ID.

        Args:
            raw_delivery: Raw delivery dictionary with status already set.

        Returns:
            The string ID of the stored raw delivery.
        """
        result = self._client.mutation("mutations.js:storeRawDelivery", self._conv_to_json(raw_delivery))
        return str(result) if result else ""

    def _update_raw_delivery_status(
        self,
        raw_delivery_id: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> None:
        """Update the status of a raw delivery in Convex.

        Args:
            raw_delivery_id: ID of the raw delivery to update.
            status: New status string (e.g., "completed", "error", "in_progress").
            error_message: Optional error description when status is "error".
        """
        self._client.mutation("mutations.js:updateRawDeliveryStatus", self._conv_to_json({
            "rawDeliveryId": raw_delivery_id,
            "status": status,
            "errorMessage": error_message,
        }))

    def _ingest_delivery_chunk(self, raw_delivery_id: str, events: list[dict]) -> dict:
        """Ingest a single chunk of events for a large delivery.

        Args:
            raw_delivery_id: ID of the parent raw delivery.
            events: List of normalized event dictionaries for this chunk.

        Returns:
            Dictionary with received_records, stored_records, and duplicate_records counts.
        """
        result = self._client.mutation("mutations.js:ingestNormalizedEventsChunk", {
            "rawDeliveryId": raw_delivery_id,
            "events": events,
        })
        return {
            "received_records": int(result["receivedRecords"]),
            "stored_records": int(result["storedRecords"]),
            "duplicate_records": int(result.get("duplicateRecords", 0)),
        }

    def _with_delivery_status(
        self,
        raw_delivery: dict,
        *,
        status: str,
        error_message: Optional[str] = None,
    ) -> dict:
        """Create a copy of a raw delivery with an updated status.

        Args:
            raw_delivery: Original raw delivery dictionary.
            status: New status string.
            error_message: Optional error message to set or remove.

        Returns:
            A new raw delivery dictionary with the updated status.
        """
        next_raw_delivery = dict(raw_delivery)
        next_raw_delivery["status"] = status
        if error_message is not None:
            next_raw_delivery["errorMessage"] = error_message
        else:
            next_raw_delivery.pop("errorMessage", None)
        return self._conv_to_json(next_raw_delivery)

    def _mark_raw_delivery_error_best_effort(self, raw_delivery_id: str, error_message: str) -> None:
        """Attempt to mark a raw delivery as errored, silently ignoring failures.

        Used during cleanup after a chunked ingest fails partway through.

        Args:
            raw_delivery_id: ID of the raw delivery to mark.
            error_message: Error description to store.
        """
        try:
            self._update_raw_delivery_status(raw_delivery_id, "error", error_message)
        except Exception:
            pass

    def store_raw_delivery(
        self,
        source_ip: str,
        user_agent: Optional[str],
        payload_json: str,
        record_count: int,
        status: str = "completed",
        error_message: Optional[str] = None,
        data_class: str = "valid",
        data_class_reason: Optional[str] = None,
    ) -> str:
        """Store a raw delivery record in Convex.

        Computes the payload hash and received-at timestamp automatically.

        Args:
            source_ip: IP address of the request origin.
            user_agent: User-Agent header from the ingest request.
            payload_json: Raw JSON string of the payload.
            record_count: Number of records in the payload.
            status: Processing status (default "completed").
            error_message: Optional error message for failed deliveries.
            data_class: Classification label (default "valid", also "test").
            data_class_reason: Optional explanation for the classification.

        Returns:
            The string ID of the stored raw delivery.

        Raises:
            Exception: If the Convex mutation fails.
        """
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
        """Store a batch of pre-normalized health events directly.

        Args:
            events: List of normalized event dictionaries.

        Returns:
            List of string IDs for the stored events.

        Raises:
            Exception: If the Convex mutation fails.
        """
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
        """Ingest a complete delivery (raw payload + normalized events) into Convex.

        For small deliveries (under the batch size limit), sends events in a single
        mutation. For large deliveries, chunks events and stores the raw delivery
        separately first with "in_progress" status, then streams chunks.

        Args:
            raw_delivery: Dictionary with raw delivery metadata.
            events: List of normalized event dictionaries to ingest.

        Returns:
            Dictionary with delivery_id, received_records, stored_records, and
            duplicate_records.

        Raises:
            Exception: If Convex ingestion fails.
        """
        try:
            if len(events) <= self._ingest_batch_size:
                result = self._client.mutation("mutations.js:ingestNormalizedDelivery", {
                    "rawDelivery": self._with_delivery_status(raw_delivery, status="completed"),
                    "events": events,
                })
                return {
                    "delivery_id": str(result["deliveryId"]),
                    "received_records": int(result["receivedRecords"]),
                    "stored_records": int(result["storedRecords"]),
                    "duplicate_records": int(result.get("duplicateRecords", 0)),
                }

            delivery_id = self._store_raw_delivery_payload(
                self._with_delivery_status(raw_delivery, status="in_progress")
            )
            received_records = 0
            stored_records = 0
            duplicate_records = 0

            try:
                for chunk in self._iter_event_chunks(events):
                    chunk_result = self._ingest_delivery_chunk(delivery_id, chunk)
                    received_records += chunk_result["received_records"]
                    stored_records += chunk_result["stored_records"]
                    duplicate_records += chunk_result["duplicate_records"]

                self._update_raw_delivery_status(delivery_id, "completed")
            except Exception as e:
                self._mark_raw_delivery_error_best_effort(delivery_id, str(e))
                raise

            return {
                "delivery_id": delivery_id,
                "received_records": received_records,
                "stored_records": stored_records,
                "duplicate_records": duplicate_records,
            }

        except ConvexError as e:
            raise Exception(f"Convex error: {e}") from e

    def check_duplicate(self, payload_hash: str) -> bool:
        """Check whether a delivery with the given payload hash already exists.

        Args:
            payload_hash: SHA-256 hash of the payload JSON.

        Returns:
            True if a duplicate delivery exists, False otherwise.

        Raises:
            Exception: If the Convex mutation fails.
        """
        try:
            result = self._client.mutation("mutations.js:checkDuplicateDelivery", {
                "payloadHash": payload_hash,
            })
            return bool(result)
        except ConvexError as e:
            raise Exception(f"Convex error: {e}") from e

    def list_recent_deliveries(self, limit: int = 10) -> list[dict]:
        """Fetch the most recent raw deliveries from Convex.

        Args:
            limit: Maximum number of deliveries to return (default 10).

        Returns:
            List of raw delivery dictionaries, most recent first.

        Raises:
            Exception: If the Convex query fails.
        """
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
        """Fetch aggregated overview statistics for health events.

        Args:
            from_ms: Start of time window in Unix milliseconds (inclusive).
            to_ms: End of time window in Unix milliseconds (inclusive).
            record_types: Optional list of record types to filter by.
            device_id: Optional device ID to filter by.

        Returns:
            List of overview card dictionaries, one per record type.

        Raises:
            Exception: If the Convex query fails.
        """
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
        """Fetch time-bucketed analytics for a specific record type.

        Args:
            record_type: The record type to query (e.g., "steps").
            bucket_size: Time bucket size ("hour" or "day").
            from_ms: Start of time window in Unix milliseconds.
            to_ms: End of time window in Unix milliseconds.
            device_id: Optional device ID to filter by.

        Returns:
            List of time-bucketed data dictionaries.

        Raises:
            Exception: If the Convex query fails.
        """
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
        """List individual health events with optional filters.

        Args:
            from_ms: Start of time window in Unix milliseconds.
            to_ms: End of time window in Unix milliseconds.
            record_types: Optional list of record types to filter by.
            device_id: Optional device ID to filter by.
            limit: Maximum number of events to return (default 100, max 1000).

        Returns:
            List of event dictionaries.

        Raises:
            Exception: If the Convex query fails.
        """
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
        """Check the health of the Convex database connection.

        Returns:
            A dictionary with at least "ok" (bool) and "db" (str) fields.

        Raises:
            Exception: If the Convex query fails.
        """
        try:
            result = self._client.query("queries.js:checkDbHealth", {})
            return result if isinstance(result, dict) else {}
        except ConvexError as e:
            raise Exception(f"Convex error: {e}") from e

    def get_trend(self, record_type: str, from_ms: Optional[int] = None, to_ms: Optional[int] = None) -> dict:
        """Fetch trend analysis for a record type.

        Args:
            record_type: Type of health record (e.g., "steps").
            from_ms: Start of current window in Unix ms.
            to_ms: End of current window in Unix ms.

        Returns:
            dict with direction, percentChange, currentValue, priorValue.

        Raises:
            Exception: If the Convex query fails.
        """
        try:
            result = self._client.query("queries.js:getTrend", self._conv_to_json({
                "recordType": record_type,
                "fromMs": from_ms,
                "toMs": to_ms,
            }))
            return result if isinstance(result, dict) else {}
        except ConvexError as e:
            raise Exception(f"Convex error: {e}") from e

    def detect_anomalies(
        self,
        record_type: str,
        bucket_size: str,
        from_ms: Optional[int] = None,
        to_ms: Optional[int] = None,
        threshold: Optional[float] = None,
    ) -> dict:
        """Detect anomalous buckets for a record type.

        Args:
            record_type: Type of health record.
            bucket_size: "hour" or "day".
            from_ms: Start of window in Unix ms.
            to_ms: End of window in Unix ms.
            threshold: Number of stddevs to flag (default 2.0).

        Returns:
            dict with buckets, mean, stddev, anomalyCount.

        Raises:
            Exception: If the Convex query fails.
        """
        try:
            result = self._client.query("queries.js:detectAnomalies", self._conv_to_json({
                "recordType": record_type,
                "bucketSize": bucket_size,
                "fromMs": from_ms,
                "toMs": to_ms,
                "threshold": threshold,
            }))
            return result if isinstance(result, dict) else {}
        except ConvexError as e:
            raise Exception(f"Convex error: {e}") from e

    def get_period_summaries(
        self,
        record_types: list[str],
        period: str,
        from_ms: Optional[int] = None,
        to_ms: Optional[int] = None,
    ) -> dict:
        """Fetch period summaries for multiple record types.

        Args:
            record_types: List of record types to include.
            period: "day", "week", or "month".
            from_ms: Start of window in Unix ms.
            to_ms: End of window in Unix ms.

        Returns:
            dict with summaries array.

        Raises:
            Exception: If the Convex query fails.
        """
        try:
            result = self._client.query("queries.js:getPeriodSummaries", self._conv_to_json({
                "recordTypes": record_types,
                "period": period,
                "fromMs": from_ms,
                "toMs": to_ms,
            }))
            return result if isinstance(result, dict) else {}
        except ConvexError as e:
            raise Exception(f"Convex error: {e}") from e

    def get_goal_progress(self, user_id: str, record_type: Optional[str] = None) -> dict:
        """Fetch goal progress for a user.

        Args:
            user_id: User identifier.
            record_type: Optional specific record type (omit for all goals).

        Returns:
            dict with goals array.

        Raises:
            Exception: If the Convex query fails.
        """
        try:
            result = self._client.query("queries.js:getGoalProgress", self._conv_to_json({
                "userId": user_id,
                "recordType": record_type,
            }))
            return result if isinstance(result, dict) else {}
        except ConvexError as e:
            raise Exception(f"Convex error: {e}") from e

    def set_health_goal(
        self,
        user_id: str,
        record_type: str,
        target_value: float,
        target_unit: str,
        period: str,
    ) -> str:
        """Create or update a health goal.

        Args:
            user_id: User identifier.
            record_type: Type of health record.
            target_value: Target value to reach.
            target_unit: Unit of the target.
            period: "day", "week", or "month".

        Returns:
            Goal ID string.

        Raises:
            Exception: If the Convex mutation fails.
        """
        try:
            result = self._client.mutation("mutations.js:setHealthGoal", self._conv_to_json({
                "userId": user_id,
                "recordType": record_type,
                "targetValue": target_value,
                "targetUnit": target_unit,
                "period": period,
            }))
            return str(result) if result else ""
        except ConvexError as e:
            raise Exception(f"Convex error: {e}") from e

    def get_correlation_hints(
        self,
        record_types: list[str],
        from_ms: Optional[int] = None,
        to_ms: Optional[int] = None,
    ) -> dict:
        """Fetch correlation hints between record type pairs.

        Args:
            record_types: List of 2-10 record types to correlate.
            from_ms: Start of window in Unix ms.
            to_ms: End of window in Unix ms.

        Returns:
            dict with hints array and windowMs.

        Raises:
            Exception: If the Convex query fails.
        """
        try:
            result = self._client.query("queries.js:getCorrelationHints", self._conv_to_json({
                "recordTypes": record_types,
                "fromMs": from_ms,
                "toMs": to_ms,
            }))
            return result if isinstance(result, dict) else {}
        except ConvexError as e:
            raise Exception(f"Convex error: {e}") from e
