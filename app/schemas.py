"""Pydantic schemas for API request/response validation across all endpoints."""

from typing import Any, Optional

from pydantic import BaseModel


class WebhookRecord(BaseModel):
    """Single health data record from the webhook (generic) format.

    Attributes:
        record_type: Type of health record (e.g., "steps", "heart_rate").
        value: Numeric or structured value of the measurement.
        unit: Unit of the measurement (e.g., "count", "bpm").
        start_time_ms: Start of measurement window in Unix milliseconds.
        end_time_ms: End of measurement window in Unix milliseconds.
        captured_at_ms: Time data was captured on device in Unix milliseconds.
        device_id: Optional device identifier.
        external_id: Optional external deduplication ID.
    """

    record_type: str
    value: Any
    unit: str
    start_time_ms: int
    end_time_ms: int
    captured_at_ms: Optional[int] = None
    device_id: Optional[str] = None
    external_id: Optional[str] = None


class IngestRequest(BaseModel):
    """Request body for the /ingest/health/v1 endpoint using the generic format.

    Attributes:
        records: List of health data records to ingest.
    """

    records: list[WebhookRecord]


class IngestResponse(BaseModel):
    """Response body returned after a successful ingest operation.

    Attributes:
        ok: Whether the ingest was successful.
        received_records: Number of records received in the payload.
        stored_records: Number of records actually stored (after deduplication).
        delivery_id: Unique identifier for this delivery.
    """

    ok: bool
    received_records: int
    stored_records: int
    delivery_id: str


class DebugDelivery(BaseModel):
    """A single delivery entry returned by the debug endpoint.

    Attributes:
        delivery_id: Unique identifier for the delivery.
        received_at: ISO-8601 timestamp when the delivery was received.
        record_count: Number of records in the delivery.
        status: Processing status of the delivery (e.g., "completed", "error").
    """

    delivery_id: str
    received_at: str
    record_count: int
    status: str


class DebugResponse(BaseModel):
    """Response body for the /debug/recent endpoint.

    Attributes:
        deliveries: List of recent deliveries ordered by most recent first.
    """

    deliveries: list[DebugDelivery]


class AnalyticsOverviewCard(BaseModel):
    """Summary statistics for a single record type.

    Attributes:
        record_type: The type of health record these stats apply to.
        count: Total number of events for this record type.
        min: Minimum value observed.
        max: Maximum value observed.
        avg: Average value across all events.
        sum: Sum of all values.
        latest_value: Most recent individual event value.
        latest_at: Unix timestamp of the most recent event.
    """

    record_type: str
    count: int
    min: Optional[float] = None
    max: Optional[float] = None
    avg: Optional[float] = None
    sum: Optional[float] = None
    latest_value: Optional[float] = None
    latest_at: Optional[int] = None


class AnalyticsOverviewResponse(BaseModel):
    """Response body for the /analytics/overview endpoint.

    Attributes:
        cards: List of summary cards, one per requested record type.
    """

    cards: list[AnalyticsOverviewCard]


class AnalyticsTimeseriesPoint(BaseModel):
    """A single data point in a time-bucketed analytics series.

    Attributes:
        bucket_start: Unix timestamp marking the start of the bucket.
        value: The requested statistic value for this bucket.
        count: Number of events within this bucket.
        sum: Sum of values within this bucket.
        avg: Average value within this bucket.
        min: Minimum value within this bucket.
        max: Maximum value within this bucket.
        latest_value: Value of the most recent event in this bucket.
        latest_at: Timestamp of the most recent event in this bucket.
    """

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
    """Response body for the /analytics/timeseries endpoint.

    Attributes:
        record_type: Record type being queried.
        bucket: Time bucket size (e.g., "hour", "day").
        stat: Which statistic is being returned (e.g., "sum", "avg").
        points: Ordered list of time-bucketed data points.
    """

    record_type: str
    bucket: str
    stat: str
    points: list[AnalyticsTimeseriesPoint]


class AnalyticsEvent(BaseModel):
    """A single event returned by the analytics events endpoint.

    Attributes:
        raw_delivery_id: ID of the raw delivery this event came from.
        record_type: Type of health record.
        value: Numeric value of the event.
        unit: Unit of the value.
        start_time: Event start in Unix milliseconds.
        end_time: Event end in Unix milliseconds.
        captured_at: Time captured on device in Unix milliseconds.
        device_id: Optional originating device ID.
        external_id: Optional external deduplication ID.
        payload_hash: Hash of the original delivery payload.
        fingerprint: Hash used for record-level deduplication.
        metadata: Optional additional event data.
    """

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
    """Response body for the /analytics/events endpoint.

    Attributes:
        events: List of individual health events matching the query.
    """

    events: list[AnalyticsEvent]


class StepRecord(BaseModel):
    """A single steps measurement from the Android Health Connect app.

    Attributes:
        count: Number of steps recorded.
        start_time: ISO-8601 start time of the measurement period.
        end_time: ISO-8601 end time of the measurement period.
    """

    count: int
    start_time: str
    end_time: str


class SleepStage(BaseModel):
    """A single sleep stage within a sleep session.

    Attributes:
        stage: Name of the sleep stage (e.g., "awake", "light", "deep", "rem").
        start_time: ISO-8601 start of this stage.
        end_time: ISO-8601 end of this stage.
        duration_seconds: Duration of this stage in seconds.
    """

    stage: str
    start_time: str
    end_time: str
    duration_seconds: int


class SleepRecord(BaseModel):
    """A complete sleep session from the Android Health Connect app.

    Attributes:
        session_end_time: ISO-8601 end timestamp of the entire sleep session.
        duration_seconds: Total sleep duration in seconds.
        stages: List of individual sleep stages within the session.
    """

    session_end_time: str
    duration_seconds: int
    stages: list[SleepStage]


class HeartRateRecord(BaseModel):
    """A single heart rate measurement from the Android Health Connect app.

    Attributes:
        bpm: Heart rate in beats per minute.
        time: ISO-8601 timestamp of the measurement.
    """

    bpm: int
    time: str


class HeartRateVariabilityRecord(BaseModel):
    """A heart rate variability measurement from the Android Health Connect app.

    Attributes:
        rmssd_millis: Root mean square of successive differences in milliseconds.
        time: ISO-8601 timestamp of the measurement.
    """

    rmssd_millis: float
    time: str


class DistanceRecord(BaseModel):
    """A distance measurement from the Android Health Connect app.

    Attributes:
        meters: Distance traveled in meters.
        start_time: ISO-8601 start of the measurement period.
        end_time: ISO-8601 end of the measurement period.
    """

    meters: float
    start_time: str
    end_time: str


class CaloriesRecord(BaseModel):
    """A calories measurement from the Android Health Connect app.

    Attributes:
        calories: Energy consumed/burned in kilocalories.
        start_time: ISO-8601 start of the measurement period.
        end_time: ISO-8601 end of the measurement period.
    """

    calories: float
    start_time: str
    end_time: str


class WeightRecord(BaseModel):
    """A body weight measurement from the Android Health Connect app.

    Attributes:
        kilograms: Body weight in kilograms.
        time: ISO-8601 timestamp of the measurement.
    """

    kilograms: float
    time: str


class HeightRecord(BaseModel):
    """A body height measurement from the Android Health Connect app.

    Attributes:
        meters: Height in meters.
        time: ISO-8601 timestamp of the measurement.
    """

    meters: float
    time: str


class OxygenSaturationRecord(BaseModel):
    """An oxygen saturation measurement from the Android Health Connect app.

    Attributes:
        percentage: Oxygen saturation as a percentage (0-100).
        time: ISO-8601 timestamp of the measurement.
    """

    percentage: float
    time: str


class RestingHeartRateRecord(BaseModel):
    """A resting heart rate measurement from the Android Health Connect app.

    Attributes:
        bpm: Resting heart rate in beats per minute.
        time: ISO-8601 timestamp of the measurement.
    """

    bpm: int
    time: str


class ExerciseRecord(BaseModel):
    """A structured exercise session from the Android Health Connect app.

    Attributes:
        type: Type of exercise performed (e.g., "running", "cycling").
        start_time: ISO-8601 start of the exercise session.
        end_time: ISO-8601 end of the exercise session.
        duration_seconds: Total duration in seconds.
    """

    type: str
    start_time: str
    end_time: str
    duration_seconds: int


class NutritionRecord(BaseModel):
    """A nutrition/food log entry from the Android Health Connect app.

    Attributes:
        calories: Total energy in kilocalories.
        protein_grams: Protein intake in grams.
        carbs_grams: Carbohydrate intake in grams.
        fat_grams: Fat intake in grams.
        start_time: ISO-8601 start of the nutrition entry period.
        end_time: ISO-8601 end of the nutrition entry period.
    """

    calories: Optional[float] = None
    protein_grams: Optional[float] = None
    carbs_grams: Optional[float] = None
    fat_grams: Optional[float] = None
    start_time: str
    end_time: str


class BasalMetabolicRateRecord(BaseModel):
    """A basal metabolic rate measurement from the Android Health Connect app.

    Attributes:
        watts: BMR in watts.
        time: ISO-8601 timestamp of the measurement.
    """

    watts: float
    time: str


class BodyFatRecord(BaseModel):
    """A body fat percentage measurement from the Android Health Connect app.

    Attributes:
        percentage: Body fat as a percentage.
        time: ISO-8601 timestamp of the measurement.
    """

    percentage: float
    time: str


class LeanBodyMassRecord(BaseModel):
    """A lean body mass measurement from the Android Health Connect app.

    Attributes:
        kilograms: Lean body mass in kilograms.
        time: ISO-8601 timestamp of the measurement.
    """

    kilograms: float
    time: str


class Vo2MaxRecord(BaseModel):
    """A VO2 max measurement from the Android Health Connect app.

    Attributes:
        ml_per_kg_per_min: VO2 max in milliliters per kilogram per minute.
        time: ISO-8601 timestamp of the measurement.
    """

    ml_per_kg_per_min: float
    time: str


class AndroidPayload(BaseModel):
    """Full Android Health Connect webhook payload format.

    Represents the nested JSON structure sent by the Android app,
    containing arrays of records for each health data type.

    Attributes:
        timestamp: ISO-8601 timestamp of when the payload was generated.
        app_version: Version string of the sending Android app.
        steps: List of steps records.
        sleep: List of sleep session records.
        heart_rate: List of heart rate measurement records.
        heart_rate_variability: List of HRV measurement records.
        distance: List of distance records.
        active_calories: List of active calories records.
        total_calories: List of total calories records.
        weight: List of weight measurement records.
        height: List of height measurement records.
        oxygen_saturation: List of SpO2 records.
        resting_heart_rate: List of resting heart rate records.
        exercise: List of exercise session records.
        nutrition: List of nutrition log records.
        basal_metabolic_rate: List of BMR records.
        body_fat: List of body fat percentage records.
        lean_body_mass: List of lean body mass records.
        vo2_max: List of VO2 max records.
    """

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
