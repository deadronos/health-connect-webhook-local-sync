---
name: health-connect-analytics-query
description: Use when an AI agent or external client needs to query health data from the Health Connect Webhook Ingest service analytics routes.
---

# Health Connect Analytics Query Skill

## Overview

The Health Connect Webhook Ingest service exposes read-only analytics endpoints at `/analytics/overview`, `/analytics/timeseries`, `/analytics/events`, and `/analytics/export.csv`, plus a health check at `/healthz`. These routes allow clients to query aggregated health data without direct Convex access. All routes require Bearer token authentication.

## Authentication

All analytics endpoints require a Bearer token in the `Authorization` header:

```
Authorization: Bearer <INGEST_TOKEN>
```

The `INGEST_TOKEN` value is the same token used for the `/ingest/health/v1` webhook endpoint. It is set as an environment variable (`INGEST_TOKEN`) in the service's `.env` file.

## Supported Record Types

The following `record_type` values are supported across all analytics endpoints:

| Value | Description |
|-------|-------------|
| `steps` | Step count measurements |
| `sleep` | Sleep session records |
| `heart_rate` | Heart rate measurements |
| `heart_rate_variability` | HRV (RMSSD) measurements |
| `distance` | Distance traveled |
| `active_calories` | Active energy burned |
| `total_calories` | Total energy burned |
| `weight` | Body weight measurements |
| `height` | Height measurements |
| `oxygen_saturation` | SpO2 percentage |
| `resting_heart_rate` | Resting heart rate |
| `exercise` | Exercise sessions |
| `nutrition` | Nutrition/food log entries |
| `basal_metabolic_rate` | BMR measurements |
| `body_fat` | Body fat percentage |
| `lean_body_mass` | Lean body mass |
| `vo2_max` | VO2 max measurements |

**Important:** Record type values must match exactly. Use `heart_rate`, not `heartRate`, `heart-rate`, or `HeartRate`.

## Base URL

```
http://<host>:<port>
```

Default local development: `http://127.0.0.1:8787`

## Endpoints Quick Reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/analytics/overview` | Aggregated stats (count, min, max, avg, sum, latest) per record type |
| GET | `/analytics/timeseries` | Time-bucketed series for a single record type |
| GET | `/analytics/events` | Raw individual events, newest first, with optional limit |
| GET | `/analytics/export.csv` | Same events as CSV file download |
| GET | `/healthz` | Database health check |

## Endpoint Details

### GET /analytics/overview

Returns aggregated summary statistics per record type.

**Query parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `from_ms` | integer | No | Start of time window (Unix ms, inclusive) |
| `to_ms` | integer | No | End of time window (Unix ms, inclusive) |
| `record_type` | string[] | No | Filter to specific record types |
| `device_id` | string | No | Filter to a specific device |

**Example request:**

```bash
curl -H "Authorization: Bearer $INGEST_TOKEN" \
  "http://127.0.0.1:8787/analytics/overview"
```

**Example response:**

```json
{
  "cards": [
    {
      "record_type": "steps",
      "count": 2880,
      "min": 0,
      "max": 15000,
      "avg": 8500.0,
      "sum": 24510000,
      "latest_value": 12000,
      "latest_at": 1718928000000
    }
  ]
}
```

### GET /analytics/timeseries

Returns time-bucketed data for a single record type.

**Query parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `record_type` | string | Yes | Record type to query |
| `bucket` | string | No | Bucket size: `hour` or `day` (default: `day`) |
| `stat` | string | No | Stat to return: `count`, `sum`, `avg`, `min`, `max`, `latest_value` (default: `sum`) |
| `from_ms` | integer | No | Start of time window (Unix ms) |
| `to_ms` | integer | No | End of time window (Unix ms) |
| `device_id` | string | No | Filter to a specific device |

**Example request:**

```bash
curl -H "Authorization: Bearer $INGEST_TOKEN" \
  "http://127.0.0.1:8787/analytics/timeseries?record_type=steps&bucket=day&stat=sum"
```

**Example response:**

```json
{
  "record_type": "steps",
  "bucket": "day",
  "stat": "sum",
  "points": [
    {
      "bucket_start": 1718841600000,
      "value": 8500.0,
      "count": 12,
      "sum": 8500,
      "avg": 708.33,
      "min": 0,
      "max": 15000,
      "latest_value": 12000,
      "latest_at": 1718928000000
    }
  ]
}
```

### GET /analytics/events

Returns raw individual health events, sorted newest first.

**Query parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `from_ms` | integer | No | Start of time window (Unix ms) |
| `to_ms` | integer | No | End of time window (Unix ms) |
| `record_type` | string[] | No | Filter to specific record types |
| `device_id` | string | No | Filter to a specific device |
| `limit` | integer | No | Max events to return, 1–1000 (default: 100) |

**Example request:**

```bash
curl -H "Authorization: Bearer $INGEST_TOKEN" \
  "http://127.0.0.1:8787/analytics/events?record_type=heart_rate&limit=5"
```

**Example response:**

```json
{
  "events": [
    {
      "raw_delivery_id": "a1b2c3d4",
      "record_type": "heart_rate",
      "value": 72.0,
      "unit": "bpm",
      "start_time": 1718928000000,
      "end_time": 1718928060000,
      "captured_at": 1718928000000,
      "device_id": "device-xyz",
      "external_id": null,
      "payload_hash": "abc123...",
      "fingerprint": "def456...",
      "metadata": null
    }
  ]
}
```

### GET /analytics/export.csv

Returns the same data as `/analytics/events` but as a downloadable CSV file attachment. Useful for downloading and analyzing data in spreadsheet tools.

**Query parameters:** Same as `/analytics/events` (except `limit` max is 5000 instead of 1000).

**Example request:**

```bash
curl -H "Authorization: Bearer $INGEST_TOKEN" \
  "http://127.0.0.1:8787/analytics/export.csv?record_type=steps" \
  --output health-data.csv
```

### GET /healthz

Returns the health status of the Convex database connection. Does not require Bearer auth (returns db status regardless).

**Example request:**

```bash
curl -H "Authorization: Bearer $INGEST_TOKEN" \
  "http://127.0.0.1:8787/healthz"
```

**Example response:**

```json
{
  "ok": true,
  "db": "ok"
}
```

## Common Mistakes

1. **Wrong `record_type` format** — Values must be lowercase with underscores (e.g., `heart_rate`). Using `heartRate`, `heart-rate`, or `HeartRate` will silently return no data.

2. **Missing `Authorization` header** — Without it, the server returns `401 Missing authorization header or dashboard session`.

3. **Confusing `INGEST_TOKEN` with a separate query token** — There is no separate query token. Use the same `INGEST_TOKEN` that authenticates ingest requests.

4. **`from_ms` / `to_ms` defaults** — If not provided, endpoints use a default time window (typically the last 7–30 days depending on the endpoint). Always set explicit time windows for deterministic, reproducible results.

5. **`limit` upper bound** — `/analytics/events` caps at 1000 records. Use `from_ms`/`to_ms` to narrow the window if you need more specific data.

6. **Timestamps are Unix milliseconds** — All time parameters and response timestamps are in Unix milliseconds (not seconds). Multiply seconds by 1000 when converting.

## Error Responses

| Status | Meaning |
|--------|---------|
| 401 | Missing or invalid Bearer token |
| 404 | Analytics routes are disabled (`ENABLE_ANALYTICS_ROUTES=false`) |
| 422 | Invalid parameter value (e.g., `from_ms > to_ms`) |
| 500 | Database error from Convex |

## Finding the Token

If you do not know the `INGEST_TOKEN` value, check the service's `.env` file:

```bash
grep INGEST_TOKEN .env
```

Or ask the service operator to provide it securely out-of-band.
