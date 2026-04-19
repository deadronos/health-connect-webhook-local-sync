from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel


class RecordType(str, Enum):
    STEPS = "steps"
    SLEEP = "sleep"
    HEART_RATE = "heart_rate"
    HEART_RATE_VARIABILITY = "heart_rate_variability"
    DISTANCE = "distance"
    ACTIVE_CALORIES = "active_calories"
    TOTAL_CALORIES = "total_calories"
    RESTING_HEART_RATE = "resting_heart_rate"
    WEIGHT = "weight"
    HEIGHT = "height"
    OXYGEN_SATURATION = "oxygen_saturation"
    EXERCISE = "exercise"
    NUTRITION = "nutrition"
    BASAL_METABOLIC_RATE = "basal_metabolic_rate"
    BODY_FAT = "body_fat"
    LEAN_BODY_MASS = "lean_body_mass"
    VO2_MAX = "vo2_max"


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
    fingerprint: str
    metadata: Optional[dict[str, Any]] = None