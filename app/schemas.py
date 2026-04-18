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