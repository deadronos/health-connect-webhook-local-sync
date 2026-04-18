# Phase 2 Analytics and Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add analytics APIs, a built-in dashboard, and moderate-burst ingest hardening without migrating the project off Convex yet.

**Architecture:** Keep Convex self-hosted as the system of record for raw deliveries and normalized events. Add a dedupe-aware ingest mutation plus rollup buckets in Convex, then expose analytics read APIs and a FastAPI-served dashboard using the same bearer-token model already used by `/debug/**`.

**Tech Stack:** FastAPI, Pydantic, Jinja2 templates, vanilla JavaScript, Convex self-hosted, pytest, httpx

---

## Planned File Structure

**Create:**
- `app/routes/analytics.py`
- `app/routes/dashboard.py`
- `app/templates/dashboard.html`
- `app/static/dashboard.css`
- `app/static/dashboard.js`
- `tests/test_ingest_idempotency.py`
- `tests/test_analytics_routes.py`
- `tests/test_dashboard.py`
- `docs/architecture/004-analytics-read-model.md`

**Modify:**
- `app/config.py`
- `app/convex_client.py`
- `app/main.py`
- `app/models.py`
- `app/normalizer.py`
- `app/routes/ingest.py`
- `app/schemas.py`
- `pyproject.toml`
- `convex/schema.ts`
- `convex/healthIngester/mutations.ts`
- `convex/healthIngester/queries.ts`
- `tests/test_config.py`
- `tests/test_normalize.py`
- `tests/test_android_normalizer.py`
- `tests/test_ingest.py`
- `tests/test_ingest_route_android.py`
- `docs/architecture/001-convex-as-database.md`
- `docs/architecture/002-strict-normalizer.md`
- `README.md`
- `CHANGELOG.md`
- `ROADMAP.md`

## Implementation Notes

- Keep `POST /ingest/health/v1` response shape unchanged.
- Add `ENABLE_ANALYTICS_ROUTES` to gate `/analytics/**` and `/dashboard`.
- Require bearer auth on `/analytics/**` and `/dashboard`; keep `GET /healthz` unauthenticated.
- Preserve `deviceId` when available and add optional event `metadata` for record-specific details that the dashboard needs later.
- Use a single Convex mutation for raw delivery storage, duplicate detection, event insertion, and bucket updates so the write path is idempotent for moderate retry bursts.
- Introduce a `fingerprint` field on normalized events and index on it instead of relying on the current loose `(recordType, startTime, valueNumeric, unit)` index.
- Store rollups in a single `healthEventBuckets` table with `bucketSize` values `hour` and `day`.

### Task 1: Align the Canonical Event Contract

**Files:**
- Modify: `app/models.py`
- Modify: `app/normalizer.py`
- Modify: `tests/test_normalize.py`
- Modify: `tests/test_android_normalizer.py`
- Modify: `tests/test_ingest_route_android.py`
- Modify: `docs/architecture/002-strict-normalizer.md`

- [ ] **Step 1: Write the failing tests for event metadata and device propagation**

```python
def test_android_exercise_record_emits_metadata():
    payload = {
        "exercise": [
            {
                "type": "running",
                "start_time": "2024-03-19T10:00:00Z",
                "end_time": "2024-03-19T10:30:00Z",
                "duration_seconds": 1800,
            }
        ]
    }
    normalizer = AndroidPayloadNormalizer(payload, "hash123", "delivery456")
    event = normalizer.normalize()[0]
    assert event["recordType"] == "exercise"
    assert event["metadata"] == {"exerciseType": "running"}


def test_flat_record_preserves_device_id():
    payload = {
        "records": [
            {
                "record_type": "steps",
                "value": 1000,
                "unit": "count",
                "start_time_ms": 1710800000000,
                "end_time_ms": 1710803600000,
                "device_id": "pixel-watch",
            }
        ]
    }
    normalizer = Normalizer(payload, "hash123", "delivery456")
    event = normalizer.normalize()[0]
    assert event["deviceId"] == "pixel-watch"
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `pytest tests/test_normalize.py tests/test_android_normalizer.py tests/test_ingest_route_android.py -q`
Expected: FAIL on missing `metadata` support or incomplete event shape.

- [ ] **Step 3: Expand the canonical event contract in Python**

```python
class HealthEvent(BaseModel):
    source: str = "health-connect-webhook"
    device_id: Optional[str] = None
    record_type: str
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
```

Update both normalizers so each emitted event includes:
- `deviceId`
- `fingerprint`
- optional `metadata`

- [ ] **Step 4: Update the normalizer ADR to match current reality**

Document that the project now has:
- a strict flat-payload normalizer
- a strict Android-payload normalizer
- current support for the full Android record set already accepted by the app

- [ ] **Step 5: Re-run the targeted tests**

Run: `pytest tests/test_normalize.py tests/test_android_normalizer.py tests/test_ingest_route_android.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/models.py app/normalizer.py tests/test_normalize.py tests/test_android_normalizer.py tests/test_ingest_route_android.py docs/architecture/002-strict-normalizer.md
git commit -m "feat: align canonical event contract for analytics"
```

### Task 2: Make Ingest Idempotent and Rollup-Aware

**Files:**
- Modify: `convex/schema.ts`
- Modify: `convex/healthIngester/mutations.ts`
- Modify: `app/convex_client.py`
- Modify: `app/routes/ingest.py`
- Modify: `tests/test_convex_client.py`
- Create: `tests/test_ingest_idempotency.py`

- [ ] **Step 1: Write the failing ingest idempotency tests**

```python
def test_ingest_route_uses_single_delivery_mutation(mock_convex_client, client):
    mock_convex_client.ingest_delivery.return_value = {
        "deliveryId": "delivery-123",
        "receivedRecords": 2,
        "storedRecords": 1,
        "duplicateRecords": 1,
    }
    response = client.post(
        "/ingest/health/v1",
        json={"records": [record_one, record_two]},
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    assert response.json()["stored_records"] == 1
    mock_convex_client.ingest_delivery.assert_called_once()
```

- [ ] **Step 2: Run the ingest/client tests to verify they fail**

Run: `pytest tests/test_ingest.py tests/test_ingest_idempotency.py tests/test_convex_client.py -q`
Expected: FAIL because `ConvexClient.ingest_delivery` does not exist yet.

- [ ] **Step 3: Update the Convex schema for fingerprints and buckets**

```ts
healthEvents: defineTable({
  rawDeliveryId: v.string(),
  recordType: v.string(),
  valueNumeric: v.number(),
  unit: v.string(),
  startTime: v.number(),
  endTime: v.number(),
  capturedAt: v.number(),
  deviceId: v.optional(v.string()),
  externalId: v.optional(v.string()),
  payloadHash: v.string(),
  fingerprint: v.string(),
  metadata: v.optional(v.any()),
  createdAt: v.number(),
}).index("by_fingerprint", ["fingerprint"])

healthEventBuckets: defineTable({
  bucketSize: v.union(v.literal("hour"), v.literal("day")),
  bucketStart: v.number(),
  recordType: v.string(),
  deviceId: v.optional(v.string()),
  count: v.number(),
  sum: v.number(),
  min: v.number(),
  max: v.number(),
  latestValue: v.number(),
  latestAt: v.number(),
}).index("by_bucket", ["bucketSize", "recordType", "bucketStart"])
```

- [ ] **Step 4: Replace the split write flow with one mutation**

Create a new mutation, for example `ingestNormalizedDelivery`, that:
- inserts the raw delivery once
- checks `fingerprint` on each event
- inserts only new events
- updates both `hour` and `day` buckets for inserted events
- returns `deliveryId`, `receivedRecords`, `storedRecords`, and `duplicateRecords`

```ts
return {
  deliveryId,
  receivedRecords: args.events.length,
  storedRecords,
  duplicateRecords: args.events.length - storedRecords,
};
```

- [ ] **Step 5: Update the Python client and ingest route**

```python
result = self._client.mutation("mutations.js:ingestNormalizedDelivery", {
    "rawDelivery": raw_delivery,
    "events": events,
})

return {
    "delivery_id": str(result["deliveryId"]),
    "received_records": int(result["receivedRecords"]),
    "stored_records": int(result["storedRecords"]),
}
```

Update `app/routes/ingest.py` to call only `client.ingest_delivery(...)`.

- [ ] **Step 6: Re-run the ingest/client tests**

Run: `pytest tests/test_ingest.py tests/test_ingest_idempotency.py tests/test_convex_client.py -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add convex/schema.ts convex/healthIngester/mutations.ts app/convex_client.py app/routes/ingest.py tests/test_ingest.py tests/test_ingest_idempotency.py tests/test_convex_client.py
git commit -m "feat: make ingest idempotent and rollup aware"
```

### Task 3: Add Analytics Queries and JSON APIs

**Files:**
- Create: `app/routes/analytics.py`
- Modify: `app/config.py`
- Modify: `app/convex_client.py`
- Modify: `app/main.py`
- Modify: `app/schemas.py`
- Modify: `tests/test_config.py`
- Modify: `convex/healthIngester/queries.ts`
- Create: `tests/test_analytics_routes.py`

- [ ] **Step 1: Write the failing API tests**

```python
def test_overview_requires_auth(async_client):
    response = await async_client.get("/analytics/overview")
    assert response.status_code == 401


def test_timeseries_returns_points(mock_convex_client, async_client):
    mock_convex_client.get_analytics_timeseries.return_value = [
        {"bucketStart": 1710800000000, "count": 2, "sum": 1500.0, "avg": 750.0}
    ]
    response = await async_client.get(
        "/analytics/timeseries",
        params={"record_type": "steps", "bucket": "day", "stat": "sum"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    assert response.json()["points"][0]["value"] == 1500.0
```

- [ ] **Step 2: Run the analytics route tests to verify they fail**

Run: `pytest tests/test_analytics_routes.py -q`
Expected: FAIL because `/analytics/**` routes do not exist yet.

- [ ] **Step 3: Add Convex query functions for overview, timeseries, and event lists**

Add query functions:
- `getAnalyticsOverview`
- `getAnalyticsTimeseries`
- `listAnalyticsEvents`

Each query should filter by:
- `fromMs`
- `toMs`
- optional `recordTypes`
- optional `deviceId`

- [ ] **Step 4: Add Python schemas and client methods**

```python
class AnalyticsOverviewCard(BaseModel):
    record_type: str
    count: int
    min: float | None
    max: float | None
    avg: float | None
    sum: float | None
    latest_value: float | None
    latest_at: int | None
```

Add matching client methods:
- `get_analytics_overview(...)`
- `get_analytics_timeseries(...)`
- `list_analytics_events(...)`

- [ ] **Step 5: Implement `app/routes/analytics.py`**

Create these endpoints:
- `GET /analytics/overview`
- `GET /analytics/timeseries`
- `GET /analytics/events`
- `GET /analytics/export.csv`

Use `StreamingResponse` for CSV export:

```python
return StreamingResponse(
    iter([csv_text]),
    media_type="text/csv",
    headers={"Content-Disposition": "attachment; filename=health-events.csv"},
)
```

- [ ] **Step 6: Register the router and config gate**

Add `enable_analytics_routes: bool = True` to `Settings`, extend `tests/test_config.py` to cover it, and include the router from `app/main.py`.

- [ ] **Step 7: Re-run the analytics tests**

Run: `pytest tests/test_analytics_routes.py -q`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add app/routes/analytics.py app/config.py app/convex_client.py app/main.py app/schemas.py convex/healthIngester/queries.ts tests/test_analytics_routes.py
git commit -m "feat: add analytics read APIs"
```

### Task 4: Add the Built-In Dashboard

**Files:**
- Create: `app/routes/dashboard.py`
- Create: `app/templates/dashboard.html`
- Create: `app/static/dashboard.css`
- Create: `app/static/dashboard.js`
- Modify: `app/main.py`
- Modify: `pyproject.toml`
- Create: `tests/test_dashboard.py`

- [ ] **Step 1: Write the failing dashboard tests**

```python
def test_dashboard_requires_auth(client):
    response = client.get("/dashboard")
    assert response.status_code == 401


def test_dashboard_returns_html(client):
    response = client.get("/dashboard", headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Health Analytics Dashboard" in response.text
```

- [ ] **Step 2: Run the dashboard tests to verify they fail**

Run: `pytest tests/test_dashboard.py -q`
Expected: FAIL because `/dashboard` does not exist yet.

- [ ] **Step 3: Implement the dashboard route and template shell**

Mount static files in `app/main.py` and serve a Jinja2 template with:
- date range controls
- record-type filter
- overview cards
- time-series chart container
- recent events table
- CSV export link

```python
templates = Jinja2Templates(directory="app/templates")

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    auth.verify(request.headers.get("authorization"))
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "title": "Health Analytics Dashboard"},
    )
```

- [ ] **Step 4: Add the template dependency and static assets**

Add `jinja2` to `pyproject.toml`:

```toml
dependencies = [
    "fastapi>=0.115.0",
    "jinja2>=3.1.0",
]
```

Keep the UI lightweight:
- `dashboard.css` for layout, cards, filters, tables
- `dashboard.js` for calling `/analytics/**` and rendering charts/tables

Use the existing JSON APIs; do not add a separate frontend build toolchain.

- [ ] **Step 5: Re-run the dashboard tests**

Run: `pytest tests/test_dashboard.py -q`
Expected: PASS

- [ ] **Step 6: Perform a manual smoke check**

Run: `uvicorn app.main:app --reload`
Then open `http://127.0.0.1:8000/dashboard` with a valid bearer token and verify:
- filters load
- overview cards render
- time-series requests succeed
- CSV export downloads

- [ ] **Step 7: Commit**

```bash
git add app/routes/dashboard.py app/templates/dashboard.html app/static/dashboard.css app/static/dashboard.js app/main.py pyproject.toml tests/test_dashboard.py
git commit -m "feat: add built-in analytics dashboard"
```

### Task 5: Finish Documentation and Full Verification

**Files:**
- Create: `docs/architecture/004-analytics-read-model.md`
- Modify: `docs/architecture/001-convex-as-database.md`
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `ROADMAP.md`

- [ ] **Step 1: Add the analytics ADR**

Write `docs/architecture/004-analytics-read-model.md` to record:
- why the project is staying Convex-first for phase 2
- why rollup buckets are being added now
- why Postgres is still deferred

- [ ] **Step 2: Update ADR-001 and README**

Update:
- `docs/architecture/001-convex-as-database.md` to mention phase-2 rollups and explicit migration triggers
- `README.md` to document `/analytics/**`, `/dashboard`, new env flags, and the updated architecture diagram

- [ ] **Step 3: Update project-facing docs**

Append sanitized lines to `CHANGELOG.md` and refresh `ROADMAP.md` so:
- current state reflects the new analytics/dashboard phase once complete
- future work remains clearly separated from shipped behavior

- [ ] **Step 4: Run the full test suite**

Run: `pytest tests/ -q`
Expected: PASS

- [ ] **Step 5: Run one end-to-end ingest and dashboard smoke check**

Run:

```bash
./scripts/dev.sh
python tools/mock_sender.py --fixture fixtures/healthconnect_android_mixed.json --token test-token
```

Verify:
- ingest succeeds
- `/debug/recent` shows the delivery
- `/analytics/overview` returns summaries
- `/dashboard` loads the new data

- [ ] **Step 6: Commit**

```bash
git add docs/architecture/004-analytics-read-model.md docs/architecture/001-convex-as-database.md README.md CHANGELOG.md ROADMAP.md
git commit -m "docs: record analytics architecture and roadmap"
```

## Acceptance Criteria

- `POST /ingest/health/v1` stays compatible while becoming idempotent for duplicate event bursts.
- Event rows persist `deviceId`, `fingerprint`, and optional `metadata`.
- Convex exposes overview, timeseries, and recent-event queries without requiring a second database.
- FastAPI exposes authenticated `/analytics/**` endpoints and `/dashboard`.
- The first dashboard works without a separate frontend app or Node build pipeline.
- Docs are updated in the same implementation branch: ADRs, README, CHANGELOG, and roadmap stay aligned.

## Risk Checks

- If bucket updates make ingest too slow, keep the single mutation but move day-bucket recomputation to a follow-up mutation before considering a database migration.
- If the dashboard needs dimensions or joins beyond `recordType`, time range, and optional `deviceId`, treat that as a signal to revisit the read model before piling on more route-specific queries.
- If sustained concurrent writers start causing repeated contention or duplicate escapes, treat that as a concrete trigger for the Postgres migration work already called out in `ROADMAP.md`.
