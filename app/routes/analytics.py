"""Analytics endpoints for querying aggregated health event statistics."""

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
    """Validate that analytics routes are enabled and request parameters are consistent.

    Args:
        request: The incoming HTTP request.
        from_ms: Start of the time window in Unix milliseconds.
        to_ms: End of the time window in Unix milliseconds.

    Raises:
        HTTPException: 404 if analytics routes are disabled, 422 if from_ms > to_ms.
    """
    if not settings.enable_analytics_routes:
        raise HTTPException(status_code=404, detail="Analytics routes disabled")

    auth.require_dashboard_access(request)

    if from_ms is not None and to_ms is not None and from_ms > to_ms:
        raise HTTPException(status_code=422, detail="from_ms must be less than or equal to to_ms")


def _to_analytics_event(event: dict) -> AnalyticsEvent:
    """Convert a raw event dictionary from Convex into an AnalyticsEvent schema.

    Args:
        event: Raw event dictionary with camelCase keys from Convex.

    Returns:
        An AnalyticsEvent Pydantic model with the event data.
    """
    fingerprint = event.get("fingerprint") or event["payloadHash"]
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
        fingerprint=fingerprint,
        metadata=event.get("metadata"),
    )


def _timeseries_value(row: dict, stat: str) -> float:
    """Extract the value for a requested statistic from a timeseries row.

    Args:
        row: A single timeseries data point from Convex.
        stat: The statistic name to extract ("count", "sum", "avg", etc.).

    Returns:
        The float value of the requested statistic, or 0.0 if not present.
    """
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
    """Get aggregated summary statistics for health events.

    Returns one card per record type with count, min, max, avg, sum, and
    the latest value. Results can be filtered by time window and device.

    Args:
        request: The incoming HTTP request.
        from_ms: Start of time window in Unix milliseconds (inclusive).
        to_ms: End of time window in Unix milliseconds (inclusive).
        record_type: Optional list of record types to filter by.
        device_id: Optional device ID to filter results to one device.

    Returns:
        An AnalyticsOverviewResponse with a card per record type.
    """
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
    """Get time-bucketed analytics for a specific record type.

    Returns data points grouped into hourly or daily buckets, each with
    the requested statistic (sum, avg, count, etc.).

    Args:
        request: The incoming HTTP request.
        record_type: The type of health record to query (required).
        bucket: Time bucket size — "hour" or "day" (default "day").
        stat: Which statistic to return per bucket — "sum", "avg", "count",
            "min", "max", or "latest_value" (default "sum").
        from_ms: Start of time window in Unix milliseconds.
        to_ms: End of time window in Unix milliseconds.
        device_id: Optional device ID to filter results.

    Returns:
        An AnalyticsTimeseriesResponse with ordered data points.
    """
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
    """List individual health events with optional filtering.

    Returns raw events rather than aggregated statistics. Useful for
    debugging and detailed inspection of specific records.

    Args:
        request: The incoming HTTP request.
        from_ms: Start of time window in Unix milliseconds.
        to_ms: End of time window in Unix milliseconds.
        record_type: Optional list of record types to filter by.
        device_id: Optional device ID to filter results.
        limit: Maximum events to return (default 100, max 1000).

    Returns:
        An AnalyticsEventsResponse with a list of individual events.
    """
    _validate_request(request, from_ms, to_ms)

    rows = client.list_analytics_events(
        from_ms=from_ms,
        to_ms=to_ms,
        record_types=[item.value for item in record_type] if record_type else None,
        device_id=device_id,
        limit=limit,
    )
    return AnalyticsEventsResponse(events=[_to_analytics_event(row) for row in rows])


def _generate_csv_rows(rows: list[dict]):
    """Generator that yields CSV rows one at a time from a list of event dictionaries.

    Writes the CSV header first, then yields each row individually, clearing the
    buffer after each yield to keep memory usage low.

    Args:
        rows: List of raw event dictionaries from Convex.

    Yields:
        CSV-formatted strings, one per chunk (header first, then each row).
    """
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
    yield buffer.getvalue()
    buffer.seek(0)
    buffer.truncate(0)

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
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)


@router.get("/export.csv")
async def export_csv(
    request: Request,
    from_ms: int | None = Query(default=None, ge=0),
    to_ms: int | None = Query(default=None, ge=0),
    record_type: list[RecordType] | None = Query(default=None),
    device_id: str | None = Query(default=None),
    limit: int = Query(default=1000, ge=1, le=5000),
):
    """Export filtered health events as a CSV file download.

    Returns the same data as the /events endpoint but formatted as a
    CSV file for easy download and analysis in spreadsheet tools.

    Args:
        request: The incoming HTTP request.
        from_ms: Start of time window in Unix milliseconds.
        to_ms: End of time window in Unix milliseconds.
        record_type: Optional list of record types to filter by.
        device_id: Optional device ID to filter results.
        limit: Maximum events to export (default 1000, max 5000).

    Returns:
        A StreamingResponse with CSV content and a download attachment header.
    """
    _validate_request(request, from_ms, to_ms)

    rows = client.list_analytics_events(
        from_ms=from_ms,
        to_ms=to_ms,
        record_types=[item.value for item in record_type] if record_type else None,
        device_id=device_id,
        limit=limit,
    )

    return StreamingResponse(
        _generate_csv_rows(rows),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=health-events.csv"},
    )
