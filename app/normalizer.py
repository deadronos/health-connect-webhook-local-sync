from datetime import datetime, timezone
from typing import Any

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