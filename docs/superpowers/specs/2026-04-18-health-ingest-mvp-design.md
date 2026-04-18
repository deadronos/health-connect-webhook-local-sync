# Health Connect Webhook Ingest MVP — Design

**Date:** 2026-04-18
**Status:** Approved
**Scope:** MVP — local ingest, SQLite-backed Convex, no Docker, no Postgres

---

## 1. Tech Stack & Project Structure

```
health_ingest/
  app/
    __init__.py
    main.py           # FastAPI app, startup, routes
    config.py        # pydantic-settings from .env
    convex_client.py # Convex client + table helpers
    models.py        # internal canonical event model (Pydantic)
    schemas.py       # incoming webhook payload schemas (Pydantic)
    auth.py          # bearer token middleware
    normalizer.py    # webhook payload → canonical events
    routes/
      __init__.py
      ingest.py      # POST /ingest/health/v1
      health.py      # GET /healthz
      debug.py       # GET /debug/recent
  tests/
    conftest.py
    test_auth.py
    test_validation.py
    test_normalize.py
    test_ingest.py
  tools/
    mock_sender.py
  fixtures/
    healthconnect_steps.json
    healthconnect_heartrate.json
    healthconnect_weight.json
    healthconnect_mixed.json
    healthconnect_invalid_missing_fields.json
    healthconnect_duplicate_event.json
  scripts/
    dev.sh
    test.sh
  .env.example
  pyproject.toml
  README.md
```

**Database:** Convex (Python client via `convexleyball`), schema managed by Convex migrations. No raw SQL migrations.

**Auth:** Static bearer token from `.env`.

**Testing:** pytest + httpx + pytest-asyncio.

---

## 2. Ingest Flow & Normalization

**Ingest request flow:**

1. `POST /ingest/health/v1` receives JSON body
2. Auth middleware verifies `Authorization: Bearer <token>` — rejects 401 if missing/wrong
3. Request body validated against Pydantic schema (max size enforced by FastAPI)
4. Raw payload stored to Convex `raw_deliveries` table with metadata (received_at, source_ip, user_agent, payload_hash, status)
5. Normalizer transforms payload into canonical event rows — one per record
6. Each canonical row stored to Convex `health_events` table
7. Success response: `{"ok": true, "received_records": N, "stored_records": N, "delivery_id": "uuid"}`

**Normalization — strict if/else per record type:**

```python
if record_type == "steps":
    → canonical row: record_type="steps", value=int, unit="count"
elif record_type == "heart_rate":
    → canonical row: record_type="heart_rate", value=int, unit="bpm"
elif record_type == "resting_heart_rate":
    → canonical row: record_type="resting_heart_rate", value=int, unit="bpm"
elif record_type == "weight":
    → canonical row: record_type="weight", value=float, unit="kg"
else:
    → raise ValidationError("unsupported record type")
```

Canonical model fields per event: `source`, `device_id`, `record_type`, `value`, `unit`, `start_time`, `end_time`, `captured_at`, `external_id`, `payload_hash`, `raw_delivery_id`

**Dedupe:** `payload_hash` (SHA-256 of raw JSON bytes) per delivery. All raw deliveries kept. Normalized events deduped by fingerprint: `record_type + start_time + value + unit`.

---

## 3. Database Schema (Convex Tables)

### `raw_deliveries`
- `_id` (Convex auto)
- `received_at` (DateTime)
- `source_ip` (string)
- `user_agent` (string, optional)
- `payload_json` (string — raw JSON text)
- `payload_hash` (string — SHA-256)
- `status` (string — "stored" | "error")
- `error_message` (string, optional)
- `record_count` (int)

### `health_events`
- `_id` (Convex auto)
- `raw_delivery_id` (string — reference to raw_deliveries._id)
- `record_type` (string — "steps" | "heart_rate" | "resting_heart_rate" | "weight")
- `value_numeric` (float)
- `unit` (string — "count" | "bpm" | "kg")
- `start_time` (DateTime)
- `end_time` (DateTime)
- `captured_at` (DateTime)
- `external_id` (string, optional)
- `payload_hash` (string)
- `created_at` (DateTime)

### `forward_attempts` (stubbed for future use)
- `_id`, `raw_delivery_id`, `target_name`, `attempted_at`, `status_code`, `success`, `error_message`

Tables defined in `convex/schema.ts`. Python client uses `convexleyball` for all reads/writes.

---

## 4. Mock Sender & Test Fixtures

**Mock sender (`tools/mock_sender.py`):**

- Loads fixture JSON files from `fixtures/`
- Sends `POST` to `http://127.0.0.1:8787/ingest/health/v1`
- Includes `Authorization: Bearer <token>` header
- CLI args: `--fixture <file>`, `--repeat <N>`
- Optional timestamp jitter (`--jitter-hours`) to simulate new data
- Exit 0 on success, non-zero on failure

**Fixtures (`fixtures/`):**

| File | Contents |
|------|----------|
| `healthconnect_steps.json` | steps record, single type |
| `healthconnect_heartrate.json` | heart_rate record |
| `healthconnect_weight.json` | weight record |
| `healthconnect_mixed.json` | multiple record types in one payload |
| `healthconnect_invalid_missing_fields.json` | for validation tests |
| `healthconnect_duplicate_event.json` | for dedupe tests |

Fixtures based on plausible Health Connect webhook shapes. To be updated with real captured payloads once Android sender is connected.

**Test suite (`tests/`):**

- `test_auth.py` — missing token → 401, wrong token → 401, correct → pass
- `test_validation.py` — malformed JSON, oversized payload, missing fields → 422
- `test_normalize.py` — each fixture → expected canonical rows
- `test_ingest.py` — end-to-end with TestClient, verify stored rows
- `conftest.py` — shared fixtures, test client setup

---

## 5. API Endpoints

### `POST /ingest/health/v1`

**Request:**
```
Authorization: Bearer <INGEST_TOKEN>
Content-Type: application/json
```

Body: arbitrary JSON webhook payload from Health Connect sender

**Success response (200):**
```json
{
  "ok": true,
  "received_records": 12,
  "stored_records": 12,
  "delivery_id": "a1b2c3d4"
}
```

**Error responses:**
- 401 — missing or invalid bearer token
- 413 — payload too large (> MAX_BODY_BYTES)
- 422 — malformed JSON or unsupported record type
- 500 — internal error

### `GET /healthz`

No auth required.

**Response (200):**
```json
{
  "ok": true,
  "db": "ok"
}
```

### `GET /debug/recent`

Auth required.

**Query params:** `?limit=10` (default 10, max 100)

**Response (200):**
```json
{
  "deliveries": [
    {
      "delivery_id": "a1b2c3d4",
      "received_at": "2026-04-18T12:34:56Z",
      "record_count": 4,
      "status": "stored"
    }
  ]
}
```

### Config env vars

```env
APP_ENV=development
HOST=127.0.0.1
PORT=8787
INGEST_TOKEN=replace_me
CONVEX_DEPLOYMENT_URL=https://your-project.convex.cloud
CONVEX_ADMIN_KEY=replace_me
ENABLE_DEBUG_ROUTES=true
MAX_BODY_BYTES=262144
OPENCLAW_WEBHOOK_URL=
OPENCLAW_WEBHOOK_TOKEN=
```

---

## 6. Auth & Security

- Static bearer token from `INGEST_TOKEN` env var
- Request body size limit via `MAX_BODY_BYTES` (default 256KB)
- All endpoints except `/healthz` require auth
- Bearer token checked via `Authorization: Bearer <token>` header

---

## 7. Milestone 1 Deliverables

1. FastAPI app scaffold with `uvicorn`
2. `POST /ingest/health/v1` with bearer auth
3. `GET /healthz` health probe
4. `GET /debug/recent` debug route
5. `.env` / `.env.example` config
6. Convex client setup with `raw_deliveries` and `health_events` tables
7. Normalizer with 4 record types (steps, heart_rate, resting_heart_rate, weight)
8. Fixture files
9. Mock sender script
10. pytest test suite (auth, validation, normalization, end-to-end)

---

## 8. Out of Scope for MVP

- Docker
- Postgres
- OpenClaw forwarding (config-gated, non-blocking, future milestone)
- Hosted deployment
- Rate limiting
- HMAC signatures
- Multi-user support
