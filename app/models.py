"""Domain models for health events and record types."""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel


class RecordType(str, Enum):
    """Enumeration of supported health record types.

    Each value corresponds to a distinct health data category collected
    from the Health Connect platform.
    """

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
    """Normalized health event stored in the Convex database.

    Represents a single health data point after normalization from
    either the webhook or Android payload format.

    Attributes:
        source: Identifies the source system (always "health-connect-webhook").
        device_id: Unique identifier for the originating device.
        record_type: Category of health data (e.g., steps, heart_rate).
        value: Numeric measurement value.
        unit: Unit of the value (e.g., "count", "bpm", "kg").
        start_time: Start of the measurement period in Unix milliseconds.
        end_time: End of the measurement period in Unix milliseconds.
        captured_at: Time the data was captured on the device in Unix milliseconds.
        external_id: Optional external identifier for deduplication.
        payload_hash: SHA-256 hash of the original delivery payload JSON.
        raw_delivery_id: Identifier linking this event back to the raw delivery.
        fingerprint: SHA-256 hash used for record-level deduplication.
        metadata: Optional additional structured data about the event.
    """

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
