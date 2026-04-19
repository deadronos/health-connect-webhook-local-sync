from typing import Any, Optional

from pydantic import BaseModel


class WebhookRecord(BaseModel):
    record_type: str
    value: Any
    unit: str
    start_time_ms: int
    end_time_ms: int
    captured_at_ms: Optional[int] = None
    device_id: Optional[str] = None
    external_id: Optional[str] = None


class IngestRequest(BaseModel):
    records: list[WebhookRecord]


class IngestResponse(BaseModel):
    ok: bool
    received_records: int
    stored_records: int
    delivery_id: str


class DebugDelivery(BaseModel):
    delivery_id: str
    received_at: str
    record_count: int
    status: str


class DebugResponse(BaseModel):
    deliveries: list[DebugDelivery]


class AnalyticsOverviewCard(BaseModel):
    record_type: str
    count: int
    min: Optional[float] = None
    max: Optional[float] = None
    avg: Optional[float] = None
    sum: Optional[float] = None
    latest_value: Optional[float] = None
    latest_at: Optional[int] = None


class AnalyticsOverviewResponse(BaseModel):
    cards: list[AnalyticsOverviewCard]


class AnalyticsTimeseriesPoint(BaseModel):
    bucket_start: int
    value: float
    count: int
    sum: Optional[float] = None
    avg: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None
    latest_value: Optional[float] = None
    latest_at: Optional[int] = None


class AnalyticsTimeseriesResponse(BaseModel):
    record_type: str
    bucket: str
    stat: str
    points: list[AnalyticsTimeseriesPoint]


class AnalyticsEvent(BaseModel):
    raw_delivery_id: str
    record_type: str
    value: float
    unit: str
    start_time: int
    end_time: int
    captured_at: int
    device_id: Optional[str] = None
    external_id: Optional[str] = None
    payload_hash: str
    fingerprint: str
    metadata: Optional[dict[str, Any]] = None


class AnalyticsEventsResponse(BaseModel):
    events: list[AnalyticsEvent]


class StepRecord(BaseModel):
    count: int
    start_time: str
    end_time: str


class SleepStage(BaseModel):
    stage: str
    start_time: str
    end_time: str
    duration_seconds: int


class SleepRecord(BaseModel):
    session_end_time: str
    duration_seconds: int
    stages: list[SleepStage]


class HeartRateRecord(BaseModel):
    bpm: int
    time: str


class HeartRateVariabilityRecord(BaseModel):
    rmssd_millis: float
    time: str


class DistanceRecord(BaseModel):
    meters: float
    start_time: str
    end_time: str


class CaloriesRecord(BaseModel):
    calories: float
    start_time: str
    end_time: str


class WeightRecord(BaseModel):
    kilograms: float
    time: str


class HeightRecord(BaseModel):
    meters: float
    time: str


class OxygenSaturationRecord(BaseModel):
    percentage: float
    time: str


class RestingHeartRateRecord(BaseModel):
    bpm: int
    time: str


class ExerciseRecord(BaseModel):
    type: str
    start_time: str
    end_time: str
    duration_seconds: int


class NutritionRecord(BaseModel):
    calories: Optional[float] = None
    protein_grams: Optional[float] = None
    carbs_grams: Optional[float] = None
    fat_grams: Optional[float] = None
    start_time: str
    end_time: str


class BasalMetabolicRateRecord(BaseModel):
    watts: float
    time: str


class BodyFatRecord(BaseModel):
    percentage: float
    time: str


class LeanBodyMassRecord(BaseModel):
    kilograms: float
    time: str


class Vo2MaxRecord(BaseModel):
    ml_per_kg_per_min: float
    time: str


class AndroidPayload(BaseModel):
    timestamp: Optional[str] = None
    app_version: Optional[str] = None
    steps: list[StepRecord] = []
    sleep: list[SleepRecord] = []
    heart_rate: list[HeartRateRecord] = []
    heart_rate_variability: list[HeartRateVariabilityRecord] = []
    distance: list[DistanceRecord] = []
    active_calories: list[CaloriesRecord] = []
    total_calories: list[CaloriesRecord] = []
    weight: list[WeightRecord] = []
    height: list[HeightRecord] = []
    oxygen_saturation: list[OxygenSaturationRecord] = []
    resting_heart_rate: list[RestingHeartRateRecord] = []
    exercise: list[ExerciseRecord] = []
    nutrition: list[NutritionRecord] = []
    basal_metabolic_rate: list[BasalMetabolicRateRecord] = []
    body_fat: list[BodyFatRecord] = []
    lean_body_mass: list[LeanBodyMassRecord] = []
    vo2_max: list[Vo2MaxRecord] = []