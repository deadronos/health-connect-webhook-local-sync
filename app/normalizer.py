"""Normalizers that transform incoming webhook payloads into internal health event format."""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Optional


class NormalizationError(ValueError):
    """Raised when a payload contains unsupported or malformed record types."""


def _now_ms() -> int:
    """Return the current Unix timestamp in milliseconds (UTC).

    Returns:
        Current time as a Unix timestamp in milliseconds.
    """
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _compact_dict(value: dict[str, Any]) -> dict[str, Any]:
    """Remove entries with None values from a dictionary.

    Args:
        value: Input dictionary potentially containing None values.

    Returns:
        A new dictionary with all None values removed.
    """
    return {key: item for key, item in value.items() if item is not None}


def _device_id_from_record(record: dict[str, Any]) -> Optional[str]:
    """Extract the device_id from a record, accepting either snake_case or camelCase.

    Args:
        record: A health data record dictionary.

    Returns:
        The device_id string if present, otherwise None.
    """
    return record.get("device_id") or record.get("deviceId")


def _external_id_from_record(record: dict[str, Any]) -> Optional[str]:
    """Extract the external_id from a record, accepting either snake_case or camelCase.

    Args:
        record: A health data record dictionary.

    Returns:
        The external_id string if present, otherwise None.
    """
    return record.get("external_id") or record.get("externalId")


def _build_fingerprint(
    *,
    record_type: str,
    value_numeric: float,
    unit: str,
    start_time: int,
    end_time: int,
    device_id: Optional[str],
    external_id: Optional[str],
    metadata: Optional[dict[str, Any]],
) -> str:
    """Build a SHA-256 fingerprint for deduplication of a single health event.

    The fingerprint is derived from the canonical form of all identifying fields,
    ensuring the same logical event always produces the same fingerprint.

    Args:
        record_type: Type of health record (e.g., "steps").
        value_numeric: Numeric value of the measurement.
        unit: Unit of the measurement.
        start_time: Start of measurement period in Unix milliseconds.
        end_time: End of measurement period in Unix milliseconds.
        device_id: Optional device identifier.
        external_id: Optional external deduplication ID.
        metadata: Optional additional structured data.

    Returns:
        A SHA-256 hex digest representing this event's fingerprint.
    """
    fingerprint_source = _compact_dict({
        "recordType": record_type,
        "valueNumeric": float(value_numeric),
        "unit": unit,
        "startTime": start_time,
        "endTime": end_time,
        "deviceId": device_id,
        "externalId": external_id,
        "metadata": metadata,
    })
    encoded = json.dumps(fingerprint_source, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _build_event(
    *,
    raw_delivery_id: str,
    record_type: str,
    value_numeric: float,
    unit: str,
    start_time: int,
    end_time: int,
    captured_at: int,
    payload_hash: str,
    created_at: int,
    external_id: Optional[str] = None,
    device_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Build a complete normalized health event dictionary.

    Args:
        raw_delivery_id: ID linking this event back to its raw delivery.
        record_type: Type of health record.
        value_numeric: Numeric value of the measurement.
        unit: Unit of the measurement.
        start_time: Start of measurement period in Unix milliseconds.
        end_time: End of measurement period in Unix milliseconds.
        captured_at: Time captured on device in Unix milliseconds.
        payload_hash: SHA-256 hash of the original delivery payload.
        created_at: Timestamp when this event was created in the system.
        external_id: Optional external deduplication ID.
        device_id: Optional device identifier.
        metadata: Optional additional structured data.

    Returns:
        A fully populated event dictionary suitable for Convex ingestion.
    """
    return _compact_dict({
        "rawDeliveryId": raw_delivery_id,
        "recordType": record_type,
        "valueNumeric": float(value_numeric),
        "unit": unit,
        "startTime": start_time,
        "endTime": end_time,
        "capturedAt": captured_at,
        "externalId": external_id,
        "deviceId": device_id,
        "payloadHash": payload_hash,
        "fingerprint": _build_fingerprint(
            record_type=record_type,
            value_numeric=value_numeric,
            unit=unit,
            start_time=start_time,
            end_time=end_time,
            device_id=device_id,
            external_id=external_id,
            metadata=metadata,
        ),
        "metadata": metadata,
        "createdAt": created_at,
    })


class Normalizer:
    """Normalizer for the generic webhook record format.

    Transforms flat records with a "records" array into normalized health events.
    Only supports a limited subset of record types.

    Attributes:
        SUPPORTED_TYPES: Set of record types this normalizer accepts.
        UNIT_MAP: Default units for each supported record type.
    """

    SUPPORTED_TYPES = {"steps", "heart_rate", "resting_heart_rate", "weight"}

    UNIT_MAP = {
        "steps": "count",
        "heart_rate": "bpm",
        "resting_heart_rate": "bpm",
        "weight": "kg",
    }

    def __init__(self, payload: dict[str, Any], payload_hash: str, delivery_id: str):
        """Initialize the normalizer with a payload and delivery context.

        Args:
            payload: The parsed JSON webhook payload containing a "records" list.
            payload_hash: SHA-256 hash of the original payload JSON.
            delivery_id: Unique identifier for this delivery.
        """
        self.payload = payload
        self.payload_hash = payload_hash
        self.delivery_id = delivery_id
        self._records: list[dict[str, Any]] = payload.get("records", [])

    def normalize(self) -> list[dict[str, Any]]:
        """Transform all records in the payload into normalized health events.

        Returns:
            List of normalized event dictionaries ready for Convex ingestion.

        Raises:
            NormalizationError: If a record has an unsupported record_type.
        """
        events: list[dict[str, Any]] = []
        created_at = _now_ms()

        for record in self._records:
            record_type = record.get("record_type")
            if record_type not in self.SUPPORTED_TYPES:
                raise NormalizationError(f"unsupported record type: {record_type}")

            metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else None
            events.append(
                _build_event(
                    raw_delivery_id=self.delivery_id,
                    record_type=record_type,
                    value_numeric=float(record["value"]),
                    unit=record.get("unit") or self.UNIT_MAP[record_type],
                    start_time=record["start_time_ms"],
                    end_time=record["end_time_ms"],
                    captured_at=record.get("captured_at_ms", _now_ms()),
                    external_id=_external_id_from_record(record),
                    device_id=_device_id_from_record(record),
                    payload_hash=self.payload_hash,
                    created_at=created_at,
                    metadata=metadata,
                )
            )

        return events


class AndroidPayloadNormalizer:
    """Normalizer for Android Health Connect webhook payloads.

    Transforms the Android app's nested JSON format into internal health events.
    Each array field (steps, heart_rate, etc.) is expanded into individual events.

    Attributes:
        TYPE_KEYS: Mapping from Android payload field names to canonical record types.
    """

    TYPE_KEYS = {
        "steps": "steps",
        "sleep": "sleep",
        "heart_rate": "heart_rate",
        "heart_rate_variability": "heart_rate_variability",
        "distance": "distance",
        "active_calories": "active_calories",
        "total_calories": "total_calories",
        "weight": "weight",
        "height": "height",
        "oxygen_saturation": "oxygen_saturation",
        "resting_heart_rate": "resting_heart_rate",
        "exercise": "exercise",
        "nutrition": "nutrition",
        "basal_metabolic_rate": "basal_metabolic_rate",
        "body_fat": "body_fat",
        "lean_body_mass": "lean_body_mass",
        "vo2_max": "vo2_max",
    }

    HANDLER_MAP = {
        "steps": lambda self, base, record: self._handle_duration_event(base, record, "count", "count"),
        "sleep": lambda self, base, record: self._handle_sleep(base, record),
        "heart_rate": lambda self, base, record: self._handle_instant_event_handler(base, record, "bpm", "bpm"),
        "heart_rate_variability": lambda self, base, record: self._handle_instant_event_handler(
            base, record, "rmssd_millis", "ms"
        ),
        "distance": lambda self, base, record: self._handle_duration_event(base, record, "meters", "m"),
        "active_calories": lambda self, base, record: self._handle_duration_event(base, record, "calories", "kcal"),
        "total_calories": lambda self, base, record: self._handle_duration_event(base, record, "calories", "kcal"),
        "weight": lambda self, base, record: self._handle_point_in_time_event(base, record, "kilograms", "kg"),
        "height": lambda self, base, record: self._handle_point_in_time_event(base, record, "meters", "m"),
        "oxygen_saturation": lambda self, base, record: self._handle_point_in_time_event(base, record, "percentage", "%"),
        "resting_heart_rate": lambda self, base, record: self._handle_instant_event_handler(base, record, "bpm", "bpm"),
        "exercise": lambda self, base, record: self._handle_duration_event(base, record, "duration_seconds", "s"),
        "nutrition": lambda self, base, record: self._handle_nutrition(base, record),
        "basal_metabolic_rate": lambda self, base, record: self._handle_instant_event_handler(
            base, record, "watts", "W"
        ),
        "body_fat": lambda self, base, record: self._handle_instant_event_handler(base, record, "percentage", "%"),
        "lean_body_mass": lambda self, base, record: self._handle_instant_event_handler(base, record, "kilograms", "kg"),
        "vo2_max": lambda self, base, record: self._handle_instant_event_handler(
            base, record, "ml_per_kg_per_min", "ml/kg/min"
        ),
    }

    def __init__(self, payload: dict[str, Any], payload_hash: str, delivery_id: str):
        """Initialize the Android normalizer.

        Args:
            payload: The parsed JSON Android Health Connect payload.
            payload_hash: SHA-256 hash of the original payload JSON.
            delivery_id: Unique identifier for this delivery.
        """
        self.payload = payload
        self.payload_hash = payload_hash
        self.delivery_id = delivery_id

    def normalize(self) -> list[dict[str, Any]]:
        """Transform all record arrays in the Android payload into normalized events.

        Returns:
            List of normalized event dictionaries ready for Convex ingestion.
        """
        events: list[dict[str, Any]] = []
        created_at = _now_ms()

        for key, record_type in self.TYPE_KEYS.items():
            records = self.payload.get(key, [])
            for record in records:
                event = self._normalize_record(record, key, record_type, created_at)
                if event:
                    events.append(event)

        return events

    def _normalize_record(
        self,
        record: dict[str, Any],
        key: str,
        record_type: str,
        created_at: int,
    ) -> Optional[dict[str, Any]]:
        """Normalize a single Android record into an event dictionary.

        Dispatches to the appropriate normalization method based on record type.

        Args:
            record: The individual record from an Android payload array.
            key: The field name in the payload (e.g., "steps", "heart_rate").
            record_type: Canonical record type string.
            created_at: Unix milliseconds timestamp for the creation time.

        Returns:
            A normalized event dictionary, or None if required fields are missing.
        """
        base = {
            "raw_delivery_id": self.delivery_id,
            "record_type": record_type,
            "payload_hash": self.payload_hash,
            "created_at": created_at,
            "external_id": _external_id_from_record(record),
            "device_id": _device_id_from_record(record),
            "metadata": self._metadata_for_record(key, record),
        }

        try:
            handler = self.HANDLER_MAP.get(key)
            if handler:
                return handler(self, base, record)
            return None
        except KeyError:
            return None

    def _handle_duration_event(
        self, base: dict[str, Any], record: dict[str, Any], value_key: str, unit: str
    ) -> dict[str, Any]:
        """Generic handler for duration-based record types."""
        return self._build_android_event(
            base,
            value_numeric=float(record[value_key]),
            unit=unit,
            start_time=self._parse_instant(record["start_time"]),
            end_time=self._parse_instant(record["end_time"]),
            captured_at=self._parse_instant(record["end_time"]),
        )

    def _handle_point_in_time_event(
        self, base: dict[str, Any], record: dict[str, Any], value_key: str, unit: str
    ) -> dict[str, Any]:
        """Generic handler for point-in-time record types."""
        instant = self._parse_instant(record["time"])
        return self._build_android_event(
            base,
            value_numeric=float(record[value_key]),
            unit=unit,
            start_time=instant,
            end_time=instant,
            captured_at=instant,
        )

    def _handle_instant_event_handler(
        self, base: dict[str, Any], record: dict[str, Any], value_key: str, unit: str
    ) -> dict[str, Any]:
        """Wrapper for _instant_event to match handler signature."""
        return self._instant_event(base, record, value_key, unit)

    def _handle_sleep(self, base: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
        """Specialized handler for sleep records."""
        return self._build_android_event(
            base,
            value_numeric=float(record["duration_seconds"]),
            unit="seconds",
            start_time=self._parse_instant(record["stages"][0]["start_time"])
            if record.get("stages") and record["stages"]
            else 0,
            end_time=self._parse_instant(record["session_end_time"]),
            captured_at=self._parse_instant(record["session_end_time"]),
        )

    def _handle_nutrition(self, base: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
        """Specialized handler for nutrition records."""
        total_calories = record.get("calories")
        return self._build_android_event(
            base,
            value_numeric=float(total_calories) if total_calories is not None else 0.0,
            unit="kcal",
            start_time=self._parse_instant(record["start_time"]),
            end_time=self._parse_instant(record["end_time"]),
            captured_at=self._parse_instant(record["end_time"]),
        )

    def _build_android_event(
        self,
        base: dict[str, Any],
        *,
        value_numeric: float,
        unit: str,
        start_time: int,
        end_time: int,
        captured_at: int,
    ) -> dict[str, Any]:
        """Build a normalized event from a duration-based Android record.

        Args:
            base: Base dictionary with delivery and identity fields.
            value_numeric: The measured value.
            unit: Unit of the measurement.
            start_time: Start of the measurement period in Unix milliseconds.
            end_time: End of the measurement period in Unix milliseconds.
            captured_at: Time captured on device in Unix milliseconds.

        Returns:
            A complete normalized event dictionary.
        """
        return _build_event(
            raw_delivery_id=base["raw_delivery_id"],
            record_type=base["record_type"],
            value_numeric=value_numeric,
            unit=unit,
            start_time=start_time,
            end_time=end_time,
            captured_at=captured_at,
            payload_hash=base["payload_hash"],
            created_at=base["created_at"],
            external_id=base.get("external_id"),
            device_id=base.get("device_id"),
            metadata=base.get("metadata"),
        )

    def _instant_event(self, base: dict[str, Any], record: dict[str, Any], value_key: str, unit: str) -> dict[str, Any]:
        """Build an event for single-point-in-time record types.

        For measurements that have no duration (e.g., heart_rate at a specific moment),
        start_time, end_time, and captured_at all equal the instant timestamp.

        Args:
            base: Base dictionary with delivery and identity fields.
            record: The Android record containing the measurement.
            value_key: Key in the record containing the numeric value.
            unit: Unit string for the measurement.

        Returns:
            A complete normalized event dictionary.
        """
        instant = self._parse_instant(record["time"])
        return self._build_android_event(
            base,
            value_numeric=float(record[value_key]),
            unit=unit,
            start_time=instant,
            end_time=instant,
            captured_at=instant,
        )

    def _metadata_for_record(self, key: str, record: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Extract and build metadata specific to certain record types.

        Args:
            key: The record type key (e.g., "exercise", "sleep", "nutrition").
            record: The raw Android record dictionary.

        Returns:
            A metadata dictionary, or None if no metadata applies.
        """
        metadata: dict[str, Any] = {}

        if key == "exercise" and record.get("type"):
            metadata["exerciseType"] = record["type"]

        if key == "sleep" and record.get("stages"):
            metadata["stageCount"] = len(record["stages"])

        if key == "nutrition":
            for source_key, metadata_key in (
                ("protein_grams", "proteinGrams"),
                ("carbs_grams", "carbsGrams"),
                ("fat_grams", "fatGrams"),
            ):
                if record.get(source_key) is not None:
                    metadata[metadata_key] = float(record[source_key])

        existing_metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else None
        if existing_metadata:
            metadata = {**existing_metadata, **metadata}

        return metadata or None

    def _parse_instant(self, ts: str) -> int:
        """Parse an ISO-8601 timestamp string into Unix milliseconds.

        Args:
            ts: ISO-8601 timestamp string, optionally with a Z suffix.

        Returns:
            Unix timestamp in milliseconds, or 0 if parsing fails.
        """
        if not ts:
            return 0
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return int(dt.timestamp() * 1000)
        except ValueError:
            return 0
