import csv
import io
import json
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.auth import BearerAuth
from app.config import Settings
from app.convex_client import ConvexClient
from app.models import RecordType
from app.schemas import (
    AnalyticsEvent,
    AnalyticsEventsResponse,
    AnalyticsOverviewCard,
    AnalyticsOverviewResponse,
    AnalyticsTimeseriesPoint,
    AnalyticsTimeseriesResponse,
)

settings = Settings()
auth = BearerAuth(token=settings.ingest_token)
client = ConvexClient(
    convex_url=settings.convex_self_hosted_url,
    admin_key=settings.convex_self_hosted_admin_key,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _validate_request(request: Request, from_ms: Optional[int], to_ms: Optional[int]) -> None:
    if not settings.enable_analytics_routes:
        raise HTTPException(status_code=404, detail="Analytics routes disabled")

    auth.verify(request.headers.get("authorization"))

    if from_ms is not None and to_ms is not None and from_ms > to_ms:
        raise HTTPException(status_code=422, detail="from_ms must be less than or equal to to_ms")


def _to_analytics_event(event: dict) -> AnalyticsEvent:
    return AnalyticsEvent(
        raw_delivery_id=event["rawDeliveryId"],
        record_type=event["recordType"],
        value=event["valueNumeric"],
        unit=event["unit"],
        start_time=event["startTime"],
        end_time=event["endTime"],
        captured_at=event["capturedAt"],
        device_id=event.get("deviceId"),
        external_id=event.get("externalId"),
        payload_hash=event["payloadHash"],
        fingerprint=event["fingerprint"],
        metadata=event.get("metadata"),
    )


def _timeseries_value(row: dict, stat: str) -> float:
    key_map = {
        "count": "count",
        "sum": "sum",
        "avg": "avg",
        "min": "min",
        "max": "max",
        "latest_value": "latestValue",
    }
    return float(row.get(key_map[stat], 0.0) or 0.0)


@router.get("/overview", response_model=AnalyticsOverviewResponse)
async def overview(
    request: Request,
    from_ms: int | None = Query(default=None, ge=0),
    to_ms: int | None = Query(default=None, ge=0),
    record_type: list[RecordType] | None = Query(default=None),
    device_id: str | None = Query(default=None),
):
    _validate_request(request, from_ms, to_ms)

    overview_cards = client.get_analytics_overview(
        from_ms=from_ms,
        to_ms=to_ms,
        record_types=[item.value for item in record_type] if record_type else None,
        device_id=device_id,
    )
    return AnalyticsOverviewResponse(
        cards=[
            AnalyticsOverviewCard(
                record_type=card["recordType"],
                count=card["count"],
                min=card.get("min"),
                max=card.get("max"),
                avg=card.get("avg"),
                sum=card.get("sum"),
                latest_value=card.get("latestValue"),
                latest_at=card.get("latestAt"),
            )
            for card in overview_cards
        ]
    )


@router.get("/timeseries", response_model=AnalyticsTimeseriesResponse)
async def timeseries(
    request: Request,
    record_type: RecordType = Query(...),
    bucket: Literal["hour", "day"] = Query(default="day"),
    stat: Literal["count", "sum", "avg", "min", "max", "latest_value"] = Query(default="sum"),
    from_ms: int | None = Query(default=None, ge=0),
    to_ms: int | None = Query(default=None, ge=0),
    device_id: str | None = Query(default=None),
):
    _validate_request(request, from_ms, to_ms)

    rows = client.get_analytics_timeseries(
        record_type=record_type.value,
        bucket_size=bucket,
        from_ms=from_ms,
        to_ms=to_ms,
        device_id=device_id,
    )
    return AnalyticsTimeseriesResponse(
        record_type=record_type.value,
        bucket=bucket,
        stat=stat,
        points=[
            AnalyticsTimeseriesPoint(
                bucket_start=row["bucketStart"],
                value=_timeseries_value(row, stat),
                count=row["count"],
                sum=row.get("sum"),
                avg=row.get("avg"),
                min=row.get("min"),
                max=row.get("max"),
                latest_value=row.get("latestValue"),
                latest_at=row.get("latestAt"),
            )
            for row in rows
        ],
    )


@router.get("/events", response_model=AnalyticsEventsResponse)
async def events(
    request: Request,
    from_ms: int | None = Query(default=None, ge=0),
    to_ms: int | None = Query(default=None, ge=0),
    record_type: list[RecordType] | None = Query(default=None),
    device_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
):
    _validate_request(request, from_ms, to_ms)

    rows = client.list_analytics_events(
        from_ms=from_ms,
        to_ms=to_ms,
        record_types=[item.value for item in record_type] if record_type else None,
        device_id=device_id,
        limit=limit,
    )
    return AnalyticsEventsResponse(events=[_to_analytics_event(row) for row in rows])


@router.get("/export.csv")
async def export_csv(
    request: Request,
    from_ms: int | None = Query(default=None, ge=0),
    to_ms: int | None = Query(default=None, ge=0),
    record_type: list[RecordType] | None = Query(default=None),
    device_id: str | None = Query(default=None),
    limit: int = Query(default=1000, ge=1, le=5000),
):
    _validate_request(request, from_ms, to_ms)

    rows = client.list_analytics_events(
        from_ms=from_ms,
        to_ms=to_ms,
        record_types=[item.value for item in record_type] if record_type else None,
        device_id=device_id,
        limit=limit,
    )

    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "raw_delivery_id",
            "record_type",
            "value",
            "unit",
            "start_time",
            "end_time",
            "captured_at",
            "device_id",
            "external_id",
            "payload_hash",
            "fingerprint",
            "metadata",
        ],
    )
    writer.writeheader()
    for event in rows:
        analytics_event = _to_analytics_event(event)
        writer.writerow({
            "raw_delivery_id": analytics_event.raw_delivery_id,
            "record_type": analytics_event.record_type,
            "value": analytics_event.value,
            "unit": analytics_event.unit,
            "start_time": analytics_event.start_time,
            "end_time": analytics_event.end_time,
            "captured_at": analytics_event.captured_at,
            "device_id": analytics_event.device_id,
            "external_id": analytics_event.external_id,
            "payload_hash": analytics_event.payload_hash,
            "fingerprint": analytics_event.fingerprint,
            "metadata": json.dumps(analytics_event.metadata or {}, sort_keys=True),
        })

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=health-events.csv"},
    )
