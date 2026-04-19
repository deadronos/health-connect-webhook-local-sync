import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Optional


class NormalizationError(ValueError):
    pass


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _compact_dict(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item is not None}


def _device_id_from_record(record: dict[str, Any]) -> Optional[str]:
    return record.get("device_id") or record.get("deviceId")


def _external_id_from_record(record: dict[str, Any]) -> Optional[str]:
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
    SUPPORTED_TYPES = {"steps", "heart_rate", "resting_heart_rate", "weight"}

    UNIT_MAP = {
        "steps": "count",
        "heart_rate": "bpm",
        "resting_heart_rate": "bpm",
        "weight": "kg",
    }

    def __init__(self, payload: dict[str, Any], payload_hash: str, delivery_id: str):
        self.payload = payload
        self.payload_hash = payload_hash
        self.delivery_id = delivery_id
        self._records: list[dict[str, Any]] = payload.get("records", [])

    def normalize(self) -> list[dict[str, Any]]:
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

    def __init__(self, payload: dict[str, Any], payload_hash: str, delivery_id: str):
        self.payload = payload
        self.payload_hash = payload_hash
        self.delivery_id = delivery_id

    def normalize(self) -> list[dict[str, Any]]:
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
            match key:
                case "steps":
                    return self._build_android_event(
                        base,
                        value_numeric=float(record["count"]),
                        unit="count",
                        start_time=self._parse_instant(record["start_time"]),
                        end_time=self._parse_instant(record["end_time"]),
                        captured_at=self._parse_instant(record["end_time"]),
                    )
                case "sleep":
                    return self._build_android_event(
                        base,
                        value_numeric=float(record["duration_seconds"]),
                        unit="seconds",
                        start_time=self._parse_instant(record["stages"][0]["start_time"]) if record.get("stages") and record["stages"] else 0,
                        end_time=self._parse_instant(record["session_end_time"]),
                        captured_at=self._parse_instant(record["session_end_time"]),
                    )
                case "heart_rate":
                    return self._instant_event(base, record, "bpm", "bpm")
                case "heart_rate_variability":
                    return self._instant_event(base, record, "rmssd_millis", "ms")
                case "distance":
                    return self._build_android_event(
                        base,
                        value_numeric=float(record["meters"]),
                        unit="m",
                        start_time=self._parse_instant(record["start_time"]),
                        end_time=self._parse_instant(record["end_time"]),
                        captured_at=self._parse_instant(record["end_time"]),
                    )
                case "active_calories" | "total_calories":
                    return self._build_android_event(
                        base,
                        value_numeric=float(record["calories"]),
                        unit="kcal",
                        start_time=self._parse_instant(record["start_time"]),
                        end_time=self._parse_instant(record["end_time"]),
                        captured_at=self._parse_instant(record["end_time"]),
                    )
                case "weight":
                    return self._build_android_event(
                        base,
                        value_numeric=float(record["kilograms"]),
                        unit="kg",
                        start_time=self._parse_instant(record["time"]),
                        end_time=self._parse_instant(record["time"]),
                        captured_at=self._parse_instant(record["time"]),
                    )
                case "height":
                    return self._build_android_event(
                        base,
                        value_numeric=float(record["meters"]),
                        unit="m",
                        start_time=self._parse_instant(record["time"]),
                        end_time=self._parse_instant(record["time"]),
                        captured_at=self._parse_instant(record["time"]),
                    )
                case "oxygen_saturation":
                    return self._build_android_event(
                        base,
                        value_numeric=float(record["percentage"]),
                        unit="%",
                        start_time=self._parse_instant(record["time"]),
                        end_time=self._parse_instant(record["time"]),
                        captured_at=self._parse_instant(record["time"]),
                    )
                case "resting_heart_rate":
                    return self._instant_event(base, record, "bpm", "bpm")
                case "exercise":
                    return self._build_android_event(
                        base,
                        value_numeric=float(record["duration_seconds"]),
                        unit="s",
                        start_time=self._parse_instant(record["start_time"]),
                        end_time=self._parse_instant(record["end_time"]),
                        captured_at=self._parse_instant(record["end_time"]),
                    )
                case "nutrition":
                    total_calories = record.get("calories")
                    return self._build_android_event(
                        base,
                        value_numeric=float(total_calories) if total_calories is not None else 0.0,
                        unit="kcal",
                        start_time=self._parse_instant(record["start_time"]),
                        end_time=self._parse_instant(record["end_time"]),
                        captured_at=self._parse_instant(record["end_time"]),
                    )
                case "basal_metabolic_rate":
                    return self._instant_event(base, record, "watts", "W")
                case "body_fat":
                    return self._instant_event(base, record, "percentage", "%")
                case "lean_body_mass":
                    return self._instant_event(base, record, "kilograms", "kg")
                case "vo2_max":
                    return self._instant_event(base, record, "ml_per_kg_per_min", "ml/kg/min")
                case _:
                    return None
        except KeyError:
            return None

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
        """Build an event for single-point-in-time record types."""
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
        if not ts:
            return 0
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return int(dt.timestamp() * 1000)
        except ValueError:
            return 0