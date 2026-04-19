# HTTP API Route Reference

> **Reference note:** this file documents the current HTTP surface area of the service. It complements the ADRs in this directory and focuses on the live route contract rather than architectural decisions.

## Scope

This document covers every route currently registered in `app/main.py`:

- `GET /healthz`
- `POST /ingest/health/v1`
- `GET /debug/recent`
- `GET /login`
- `POST /login`
- `POST /logout`
- `GET /analytics/overview`
- `GET /analytics/timeseries`
- `GET /analytics/events`
- `GET /analytics/export.csv`
- `GET /dashboard`
- `/static/*` mounted assets used by the dashboard UI

## Global conventions

Bearer auth header for direct API access:

```text
Authorization: Bearer <INGEST_TOKEN>
```

Browser session auth:

- `GET /login` renders a form that accepts the same shared `INGEST_TOKEN`
- `POST /login` validates the token and sets a signed `HttpOnly` session cookie
- the signed session cookie is accepted by `/dashboard` and `/analytics/**`

Bearer-only protected routes:

- `/ingest/health/v1`
- `/debug/recent`

Session-or-bearer protected routes:

- `/analytics/**`
- `/dashboard`

Unauthenticated route:

- `/healthz`

Feature gates:

- `ENABLE_DEBUG_ROUTES=true` enables `/debug/recent`
- `ENABLE_ANALYTICS_ROUTES=true` enables `/login`, `/logout`, `/analytics/**`, and `/dashboard`

When disabled, gated routes return `404`.

Time formats:

- query parameters such as `from_ms` and `to_ms` use Unix epoch milliseconds
- canonical API responses use Unix epoch milliseconds for event and bucket timestamps
- Android payload input uses ISO 8601 timestamps such as `2024-03-19T10:00:00Z`

Analytics `record_type` values:

- `steps`
- `sleep`
- `heart_rate`
- `heart_rate_variability`
- `distance`
- `active_calories`
- `total_calories`
- `weight`
- `height`
- `oxygen_saturation`
- `resting_heart_rate`
- `exercise`
- `nutrition`
- `basal_metabolic_rate`
- `body_fat`
- `lean_body_mass`
- `vo2_max`

Common error patterns:

- `303` redirect from `/dashboard` to `/login?next=/dashboard` when the browser is unauthenticated
- `401` for missing or invalid bearer/session auth on protected routes
- `404` when a gated route is disabled by config
- `413` when ingest payload size exceeds `MAX_BODY_BYTES`
- `422` for invalid request structure, malformed JSON, invalid query params, or invalid time-window validation
- `500` for server-side persistence failures

## Route summary

| Method | Path | Auth | Gate | Response type |
| ------ | ---- | ---- | ---- | ------------- |
| `GET` | `/healthz` | none | none | JSON |
| `POST` | `/ingest/health/v1` | bearer | none | JSON |
| `GET` | `/debug/recent` | bearer | `ENABLE_DEBUG_ROUTES` | JSON |
| `GET` | `/login` | none | `ENABLE_ANALYTICS_ROUTES` | HTML |
| `POST` | `/login` | token form | `ENABLE_ANALYTICS_ROUTES` | Redirect |
| `POST` | `/logout` | session optional | `ENABLE_ANALYTICS_ROUTES` | Redirect |
| `GET` | `/analytics/overview` | session or bearer | `ENABLE_ANALYTICS_ROUTES` | JSON |
| `GET` | `/analytics/timeseries` | session or bearer | `ENABLE_ANALYTICS_ROUTES` | JSON |
| `GET` | `/analytics/events` | session or bearer | `ENABLE_ANALYTICS_ROUTES` | JSON |
| `GET` | `/analytics/export.csv` | session or bearer | `ENABLE_ANALYTICS_ROUTES` | CSV stream |
| `GET` | `/dashboard` | session or bearer | `ENABLE_ANALYTICS_ROUTES` | HTML |
| `GET` | `/static/*` | none | dashboard support | CSS / JS / other static assets |

## `GET /healthz`

- **Purpose:** basic liveness and readiness route that asks the Convex client for database health.
- **Auth:** none.
- **Parameters:** none.
- **Response model:** `HealthResponse`.

Success example:

```json
{
  "ok": true,
  "db": "ok"
}
```

Notes:

- `db` may return values such as `ok`, `error`, or `unknown`.

## `POST /ingest/health/v1`

- **Purpose:** primary write endpoint for webhook deliveries. It authenticates the request, validates the payload, auto-detects flat vs Android shape, normalizes records, and uses one Convex mutation to store the raw delivery, dedupe events by fingerprint, and update rollup buckets.
- **Auth:** required.

Headers:

- `Authorization: Bearer <INGEST_TOKEN>`
- optional `User-Agent`

Body rules:

- request body must be a JSON object
- the route accepts either the flat `records` payload shape or the Android nested payload shape

### Flat payload example

```json
{
  "records": [
    {
      "record_type": "steps",
      "value": 1000,
      "unit": "count",
      "start_time_ms": 1710800000000,
      "end_time_ms": 1710803600000,
      "captured_at_ms": 1710803600000,
      "device_id": "pixel-watch",
      "external_id": "optional-source-id"
    }
  ]
}
```

Flat payload fields:

| Field | Required | Type | Notes |
| ----- | -------- | ---- | ----- |
| `records` | yes | array | List of flat webhook records |
| `record_type` | yes | string | Strictly supported here: `steps`, `heart_rate`, `resting_heart_rate`, `weight` |
| `value` | yes | any numeric-like | Converted to canonical numeric value |
| `unit` | yes | string | Preserved as provided by the client |
| `start_time_ms` | yes | integer | Unix epoch milliseconds |
| `end_time_ms` | yes | integer | Unix epoch milliseconds |
| `captured_at_ms` | no | integer | Defaults to current time if omitted |
| `device_id` | no | string | Preserved as canonical `deviceId` |
| `external_id` | no | string | Preserved as canonical `externalId` |

### Android nested payload example

Optional top-level metadata fields:

- `timestamp`
- `app_version`

Recognized top-level record arrays:

- `steps`
- `sleep`
- `heart_rate`
- `heart_rate_variability`
- `distance`
- `active_calories`
- `total_calories`
- `weight`
- `height`
- `oxygen_saturation`
- `resting_heart_rate`
- `exercise`
- `nutrition`
- `basal_metabolic_rate`
- `body_fat`
- `lean_body_mass`
- `vo2_max`

Example:

```json
{
  "timestamp": "2024-03-19T10:00:00Z",
  "app_version": "1.0.0",
  "exercise": [
    {
      "type": "running",
      "start_time": "2024-03-19T10:00:00Z",
      "end_time": "2024-03-19T10:30:00Z",
      "duration_seconds": 1800
    }
  ]
}
```

Success example:

```json
{
  "ok": true,
  "received_records": 1,
  "stored_records": 1,
  "delivery_id": "delivery-123"
}
```

Behavior notes:

- Android format is auto-detected when `records` is absent and one or more Android-specific top-level keys are present.
- `received_records` reports validated incoming record count.
- `stored_records` reports how many non-duplicate normalized events were stored.
- Raw deliveries are recorded through the atomic ingest mutation, even when some normalized events dedupe away.
- Canonical events include `fingerprint`, optional `deviceId`, optional `externalId`, and optional `metadata`.

## `GET /debug/recent`

- **Purpose:** returns a recent list of raw deliveries for local inspection.
- **Auth:** required.
- **Gate:** `ENABLE_DEBUG_ROUTES=true`.

Query parameters:

| Name | Required | Type | Constraints | Notes |
| ---- | -------- | ---- | ----------- | ----- |
| `limit` | no | integer | `1 <= limit <= 100` | Defaults to `10` |

Success example:

```json
{
  "deliveries": [
    {
      "delivery_id": "delivery-123",
      "received_at": "2026-04-19T10:15:00Z",
      "record_count": 4,
      "status": "stored"
    }
  ]
}
```

## `GET /login`

- **Purpose:** serves the browser login form for the dashboard.
- **Auth:** none.
- **Gate:** `ENABLE_ANALYTICS_ROUTES=true`.

Query parameters:

| Name | Required | Type | Constraints | Notes |
| ---- | -------- | ---- | ----------- | ----- |
| `next` | no | string | relative path only | Defaults to `/dashboard` |

Behavior notes:

- if the request already has a valid dashboard session cookie, the route redirects to the `next` path
- if the request includes a valid bearer header, the route starts a dashboard session and redirects to the `next` path

## `POST /login`

- **Purpose:** validates a submitted ingest token and creates a signed dashboard session cookie.
- **Auth:** none before login.
- **Gate:** `ENABLE_ANALYTICS_ROUTES=true`.

Form fields:

| Name | Required | Type | Notes |
| ---- | -------- | ---- | ----- |
| `token` | yes | string | Must equal `INGEST_TOKEN` |
| `next` | no | string | Relative redirect target; defaults to `/dashboard` |

Behavior notes:

- success returns `303` to the `next` path and sets the configured session cookie
- invalid or missing tokens return `401` and re-render the login page with an error message

## `POST /logout`

- **Purpose:** clears the current dashboard session and redirects the browser back to `/login`.
- **Auth:** no pre-auth required; safe to call even if no session exists.
- **Gate:** `ENABLE_ANALYTICS_ROUTES=true`.

## `GET /analytics/overview`

- **Purpose:** returns summary cards grouped by record type.
- **Auth:** required (valid bearer header or dashboard session cookie).
- **Gate:** `ENABLE_ANALYTICS_ROUTES=true`.

Query parameters:

| Name | Required | Type | Constraints | Notes |
| ---- | -------- | ---- | ----------- | ----- |
| `from_ms` | no | integer | `>= 0` | Lower bound for event filtering |
| `to_ms` | no | integer | `>= 0` | Upper bound for event filtering |
| `record_type` | no | repeated enum | valid `RecordType` values | Can be repeated in query string |
| `device_id` | no | string | none | Filters to a specific device |

Validation notes:

- if both `from_ms` and `to_ms` are provided, `from_ms <= to_ms` is required
- invalid `record_type` values return `422`

Success example:

```json
{
  "cards": [
    {
      "record_type": "steps",
      "count": 2,
      "min": 500.0,
      "max": 1000.0,
      "avg": 750.0,
      "sum": 1500.0,
      "latest_value": 1000.0,
      "latest_at": 1710803600000
    }
  ]
}
```

## `GET /analytics/timeseries`

- **Purpose:** returns bucketed time-series points for one record type.
- **Auth:** required (valid bearer header or dashboard session cookie).
- **Gate:** `ENABLE_ANALYTICS_ROUTES=true`.

Query parameters:

| Name | Required | Type | Constraints | Notes |
| ---- | -------- | ---- | ----------- | ----- |
| `record_type` | yes | enum | valid `RecordType` | Exactly one record type |
| `bucket` | no | enum | `hour` or `day` | Defaults to `day` |
| `stat` | no | enum | `count`, `sum`, `avg`, `min`, `max`, `latest_value` | Defaults to `sum` |
| `from_ms` | no | integer | `>= 0` | Lower bound |
| `to_ms` | no | integer | `>= 0` | Upper bound |
| `device_id` | no | string | none | If present, route may aggregate from event rows rather than buckets |

Validation notes:

- if both `from_ms` and `to_ms` are provided, `from_ms <= to_ms` is required
- invalid `record_type`, `bucket`, or `stat` values return `422`
- for exact bucket-aligned windows, rollup buckets may be used directly
- for partial windows, the backend falls back to event-level aggregation so the range stays accurate

Success example:

```json
{
  "record_type": "steps",
  "bucket": "day",
  "stat": "sum",
  "points": [
    {
      "bucket_start": 1710800000000,
      "value": 1500.0,
      "count": 2,
      "sum": 1500.0,
      "avg": 750.0,
      "min": 500.0,
      "max": 1000.0,
      "latest_value": 1000.0,
      "latest_at": 1710803600000
    }
  ]
}
```

## `GET /analytics/events`

- **Purpose:** returns recent normalized canonical events.
- **Auth:** required (valid bearer header or dashboard session cookie).
- **Gate:** `ENABLE_ANALYTICS_ROUTES=true`.

Query parameters:

| Name | Required | Type | Constraints | Notes |
| ---- | -------- | ---- | ----------- | ----- |
| `from_ms` | no | integer | `>= 0` | Lower bound |
| `to_ms` | no | integer | `>= 0` | Upper bound |
| `record_type` | no | repeated enum | valid `RecordType` | Can be repeated |
| `device_id` | no | string | none | Device filter |
| `limit` | no | integer | `1 <= limit <= 1000` | Defaults to `100` |

Success example:

```json
{
  "events": [
    {
      "raw_delivery_id": "delivery-123",
      "record_type": "steps",
      "value": 1000.0,
      "unit": "count",
      "start_time": 1710800000000,
      "end_time": 1710803600000,
      "captured_at": 1710803600000,
      "device_id": "pixel-watch",
      "external_id": null,
      "payload_hash": "hash123",
      "fingerprint": "fingerprint-123",
      "metadata": {
        "source": "fixture"
      }
    }
  ]
}
```

## `GET /analytics/export.csv`

- **Purpose:** streams filtered canonical events as CSV.
- **Auth:** required (valid bearer header or dashboard session cookie).
- **Gate:** `ENABLE_ANALYTICS_ROUTES=true`.
- **Query model:** same filtering model as `/analytics/events`, except `limit` allows `1 <= limit <= 5000` and defaults to `1000`.

Response details:

- media type: `text/csv`
- header: `Content-Disposition: attachment; filename=health-events.csv`
- CSV columns:
  - `raw_delivery_id`
  - `record_type`
  - `value`
  - `unit`
  - `start_time`
  - `end_time`
  - `captured_at`
  - `device_id`
  - `external_id`
  - `payload_hash`
  - `fingerprint`
  - `metadata`

## `GET /dashboard`

- **Purpose:** serves the built-in HTML dashboard shell.
- **Auth:** required (valid bearer header or dashboard session cookie).
- **Gate:** `ENABLE_ANALYTICS_ROUTES=true`.
- **Query parameters:** none required by the route itself.

Response details:

- response class: HTML
- template: `app/templates/dashboard.html`
- unauthenticated browser requests are redirected to `/login?next=/dashboard`
- authenticated dashboard JavaScript uses same-origin requests and the signed browser session cookie to call protected analytics endpoints

Notes:

- direct clients may still call the route with a valid bearer header, which also initializes a browser session cookie
- this is part of the current HTTP surface, but it is a UI route rather than a JSON API endpoint
- static assets used by the dashboard are served under `/static/*`

## `/static/*`

- **Purpose:** serves dashboard support assets mounted from `app/static/`.
- **Auth:** none at the route-mount level.

Current assets:

- `/static/dashboard.css`
- `/static/dashboard.js`

Notes:

- these assets support the built-in dashboard and are not intended to be a stable third-party API surface
- the dashboard JavaScript is responsible for calling the protected `/analytics/**` routes with the bearer token from the authenticated page load
