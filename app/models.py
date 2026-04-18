from enum import Enum
from typing import Optional

from pydantic import BaseModel


class RecordType(str, Enum):
    STEPS = "steps"
    HEART_RATE = "heart_rate"
    RESTING_HEART_RATE = "resting_heart_rate"
    WEIGHT = "weight"


class HealthEvent(BaseModel):
    source: str = "health-connect-webhook"
    device_id: Optional[str] = None
    record_type: RecordType
    value: float
    unit: str
    start_time: int
    end_time: int
    captured_at: int
    external_id: Optional[str] = None
    payload_hash: str
    raw_delivery_id: str