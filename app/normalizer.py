from datetime import datetime, timezone
from typing import Any, Optional

from app.models import RecordType


class NormalizationError(ValueError):
    pass


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
        self._records: list[dict] = payload.get("records", [])

    def normalize(self) -> list[dict]:
        events = []
        for record in self._records:
            record_type = record.get("record_type")
            if record_type not in self.SUPPORTED_TYPES:
                raise NormalizationError(f"unsupported record type: {record_type}")

            value = record["value"]
            unit = record.get("unit") or self.UNIT_MAP[record_type]
            start_time = record["start_time_ms"]
            end_time = record["end_time_ms"]
            captured_at = record.get("captured_at_ms", int(datetime.now(timezone.utc).timestamp() * 1000))
            external_id = record.get("external_id")
            device_id = record.get("device_id")

            event = {
                "rawDeliveryId": self.delivery_id,
                "recordType": record_type,
                "valueNumeric": float(value),
                "unit": unit,
                "startTime": start_time,
                "endTime": end_time,
                "capturedAt": captured_at,
                "externalId": external_id,
                "deviceId": device_id,
                "payloadHash": self.payload_hash,
                "createdAt": int(datetime.now(timezone.utc).timestamp() * 1000),
            }
            events.append(event)
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

    def normalize(self) -> list[dict]:
        events = []
        created_at = int(datetime.now(timezone.utc).timestamp() * 1000)

        for key, record_type in self.TYPE_KEYS.items():
            records = self.payload.get(key, [])
            for record in records:
                event = self._normalize_record(record, key, record_type, created_at)
                if event:
                    events.append(event)

        return events

    def _normalize_record(self, record: dict, key: str, record_type: str, created_at: int) -> Optional[dict]:
        base = {
            "rawDeliveryId": self.delivery_id,
            "recordType": record_type,
            "payloadHash": self.payload_hash,
            "createdAt": created_at,
        }
        try:
            match key:
                case "steps":
                    return {
                        **base,
                        "valueNumeric": float(record["count"]),
                        "unit": "count",
                        "startTime": self._parse_instant(record["start_time"]),
                        "endTime": self._parse_instant(record["end_time"]),
                        "capturedAt": self._parse_instant(record["end_time"]),
                    }
                case "sleep":
                    return {
                        **base,
                        "valueNumeric": float(record["duration_seconds"]),
                        "unit": "seconds",
                        "startTime": self._parse_instant(record["stages"][0]["start_time"]) if record.get("stages") and record["stages"] else 0,
                        "endTime": self._parse_instant(record["session_end_time"]),
                        "capturedAt": self._parse_instant(record["session_end_time"]),
                    }
                case "heart_rate":
                    return self._instant_event(base, record, "bpm", "bpm")
                case "heart_rate_variability":
                    return self._instant_event(base, record, "rmssd_millis", "ms")
                case "distance":
                    return {
                        **base,
                        "valueNumeric": float(record["meters"]),
                        "unit": "m",
                        "startTime": self._parse_instant(record["start_time"]),
                        "endTime": self._parse_instant(record["end_time"]),
                        "capturedAt": self._parse_instant(record["end_time"]),
                    }
                case "active_calories" | "total_calories":
                    return {
                        **base,
                        "valueNumeric": float(record["calories"]),
                        "unit": "kcal",
                        "startTime": self._parse_instant(record["start_time"]),
                        "endTime": self._parse_instant(record["end_time"]),
                        "capturedAt": self._parse_instant(record["end_time"]),
                    }
                case "weight":
                    return {
                        **base,
                        "valueNumeric": float(record["kilograms"]),
                        "unit": "kg",
                        "startTime": self._parse_instant(record["time"]),
                        "endTime": self._parse_instant(record["time"]),
                        "capturedAt": self._parse_instant(record["time"]),
                    }
                case "height":
                    return {
                        **base,
                        "valueNumeric": float(record["meters"]),
                        "unit": "m",
                        "startTime": self._parse_instant(record["time"]),
                        "endTime": self._parse_instant(record["time"]),
                        "capturedAt": self._parse_instant(record["time"]),
                    }
                case "oxygen_saturation":
                    return {
                        **base,
                        "valueNumeric": float(record["percentage"]),
                        "unit": "%",
                        "startTime": self._parse_instant(record["time"]),
                        "endTime": self._parse_instant(record["time"]),
                        "capturedAt": self._parse_instant(record["time"]),
                    }
                case "resting_heart_rate":
                    return self._instant_event(base, record, "bpm", "bpm")
                case "exercise":
                    return {
                        **base,
                        "valueNumeric": float(record["duration_seconds"]),
                        "unit": "s",
                        "startTime": self._parse_instant(record["start_time"]),
                        "endTime": self._parse_instant(record["end_time"]),
                        "capturedAt": self._parse_instant(record["end_time"]),
                    }
                case "nutrition":
                    nutrition = record
                    total_cal = nutrition.get("calories")
                    return {
                        **base,
                        "valueNumeric": float(total_cal) if total_cal else 0.0,
                        "unit": "kcal",
                        "startTime": self._parse_instant(nutrition["start_time"]),
                        "endTime": self._parse_instant(nutrition["end_time"]),
                        "capturedAt": self._parse_instant(nutrition["end_time"]),
                    }
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

    def _instant_event(self, base: dict, record: dict, value_key: str, unit: str) -> dict:
        """Build an event for single-point-in-time record types."""
        return {
            **base,
            "valueNumeric": float(record[value_key]),
            "unit": unit,
            "startTime": self._parse_instant(record["time"]),
            "endTime": self._parse_instant(record["time"]),
            "capturedAt": self._parse_instant(record["time"]),
        }

    def _parse_instant(self, ts: str) -> int:
        if not ts:
            return 0
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return int(dt.timestamp() * 1000)
        except ValueError:
            return 0