# HealthConnect Webhook Ingest Server — idea.md

## Goal

Build a small local Python server that receives webhook payloads from an Android app such as `health-connect-webhook`, validates and normalizes the incoming data, stores it durably, and exposes a few developer-friendly endpoints for inspection and debugging.

The first version should be easy to run locally on a Mac next to OpenClaw. It should also include a test suite and a mock sender process so development does not depend on a real phone or watch being present.

---

## Product intent

This project is **not** the source of truth for raw Health Connect itself.
It is a **local ingest and normalization layer** between:

- Android Health Connect data
- the webhook-sending Android app
- local storage
- optional downstream automations such as OpenClaw

That boundary is useful because it gives us:

- validation before data touches automation
- replayable local history
- an audit trail of received payloads
- easier development and testing
- a future path to Docker without rewriting the service

---

## Design stance

### Recommended scope for MVP

Do **not** start with Postgres, queues, multi-worker concurrency, or complex auth flows.

Start with:

- Python
- FastAPI
- SQLite
- a single-process local server
- bearer-token auth
- JSON payload logging
- test fixtures and a mock sender

Reason:

- one user
- one primary data producer
- low request volume
- local development first
- SQLite is more than enough at this stage

### When Postgres becomes worth it later

Only switch to Postgres if one or more of these becomes true:

- multiple devices or users
- more complex aggregations or dashboards
- frequent concurrent writes
- external analytics tooling
- hosted deployment beyond a single-machine setup

Until then, SQLite is the better tool.

---

## Core MVP requirements

### Ingest

The server must:

- accept `POST` webhook requests from the Android sender
- require a static bearer token
- reject oversized or malformed payloads
- log receipt metadata
- normalize the payload into a predictable internal structure
- store both:
  - the original raw payload
  - normalized event rows

### Storage

Use SQLite as the default database.

Store:

- raw webhook deliveries
- normalized measurements/events
- ingest errors
- optional dedupe markers

### Developer usability

The server should support easy local development:

- run from a venv with `uvicorn`
- use `.env` for configuration
- expose a health check endpoint
- expose a small debug endpoint to inspect recent ingests
- include a mock sender CLI or second process
- include sample payload fixtures

### Testability

The project must include a test suite that verifies:

- auth rejection
- payload validation
- normalization behavior
- database writes
- duplicate handling
- mock sender integration against a live local test server

---

## Proposed architecture

```text
Android app / mock sender
        |
        v
FastAPI webhook endpoint
        |
        +--> request validation
        +--> auth check
        +--> payload normalization
        +--> dedupe logic
        +--> raw payload persistence
        +--> normalized event persistence
        |
        +--> optional forwarder to OpenClaw webhook
        |
        v
SQLite database
```

### Optional downstream forwarding

The ingest server may optionally forward a summarized event to OpenClaw after successful persistence.

Important:

- persistence should happen **before** forwarding
- OpenClaw forwarding must be non-critical
- if OpenClaw is unavailable, the ingest should still succeed locally
- forwarding failures should be logged for retry or later inspection

---

## Suggested project structure

```text
health-ingest/
  app/
    __init__.py
    main.py
    config.py
    db.py
    models.py
    schemas.py
    auth.py
    normalize.py
    ingest_service.py
    forwarder.py
    routes/
      __init__.py
      ingest.py
      health.py
      debug.py
  tests/
    test_auth.py
    test_validation.py
    test_normalize.py
    test_ingest_db.py
    test_integration_mock_sender.py
  tools/
    mock_sender.py
    generate_fixture.py
  fixtures/
    healthconnect_steps.json
    healthconnect_heartrate.json
    healthconnect_weight.json
    healthconnect_mixed.json
  scripts/
    dev.sh
    test.sh
  .env.example
  pyproject.toml
  README.md
```

---

## API plan

### `POST /ingest/health/v1`

Main webhook endpoint.

Responsibilities:

- verify `Authorization: Bearer <token>`
- parse JSON body
- enforce content-length limits
- validate required fields and shape
- persist raw payload
- normalize records
- persist normalized rows
- return a compact success response

Example success response:

```json
{
  "ok": true,
  "received_records": 12,
  "stored_records": 12,
  "delivery_id": "uuid-here"
}
```

### `GET /healthz`

Simple health probe.

Example response:

```json
{
  "ok": true,
  "db": "ok"
}
```

### `GET /debug/recent`

Development-only endpoint to inspect recent deliveries.

Can be disabled in production mode later.

Example response:

```json
{
  "deliveries": [
    {
      "delivery_id": "...",
      "received_at": "...",
      "record_count": 4,
      "status": "stored"
    }
  ]
}
```

---

## Payload strategy

### Important assumption

The Android sender may not always emit the exact same payload shape forever.

So the server should separate:

- **transport payload**: whatever the sender posts
- **internal canonical model**: what the server stores after normalization

That means the normalizer should be written as an adapter layer, not mixed directly into route code.

### Canonical internal event model

Every normalized event should map into a shape like:

```json
{
  "source": "health-connect-webhook",
  "device_id": "optional-device-id",
  "record_type": "steps",
  "value": 8421,
  "unit": "count",
  "start_time": "2026-04-18T00:00:00Z",
  "end_time": "2026-04-18T12:34:56Z",
  "captured_at": "2026-04-18T12:35:02Z",
  "external_id": "optional-source-record-id",
  "payload_hash": "sha256...",
  "raw_delivery_id": "uuid..."
}
```

### Initial record types to support

Support these first:

- steps
- heart_rate
- resting_heart_rate
- weight

Potential later types:

- distance
- calories
- sleep
- blood_oxygen
- workout/session summaries

---

## Database plan

### Tables

#### `raw_deliveries`

Store each received webhook request.

Suggested fields:

- `id`
- `received_at`
- `source_ip`
- `user_agent`
- `payload_json`
- `payload_hash`
- `status`
- `error_message`

#### `health_events`

Store normalized measurements.

Suggested fields:

- `id`
- `raw_delivery_id`
- `record_type`
- `value_numeric`
- `unit`
- `start_time`
- `end_time`
- `captured_at`
- `external_id`
- `payload_hash`
- `created_at`

#### `forward_attempts`

Optional table for downstream forwarding.

Suggested fields:

- `id`
- `raw_delivery_id`
- `target_name`
- `attempted_at`
- `status_code`
- `success`
- `error_message`

### SQLite notes

Use:

- WAL mode
- parameterized queries
- lightweight migrations

Recommended migration/tool choices:

- plain SQL migration files, or
- Alembic if desired

Do not overcomplicate ORM choices early. SQLAlchemy Core or SQLModel are fine.

---

## Auth and security plan

### MVP auth

Use a static bearer token from `.env`.

Request must include:

```text
Authorization: Bearer <INGEST_TOKEN>
```

### Additional defensive controls

Also add:

- request body size limit
- request timeout
- minimal structured logging
- narrow endpoint path
- reject non-JSON content types

### Future security enhancements

Later, optionally add:

- HMAC signature header
- per-device tokens
- IP allowlist if environment permits
- rate limiting
- secret rotation support

---

## Local development plan

### MVP local run flow

1. Create venv
2. Install dependencies
3. Copy `.env.example` to `.env`
4. Start SQLite-backed FastAPI app
5. Run mock sender against `http://127.0.0.1:8787/ingest/health/v1`
6. Inspect `/debug/recent`

### Suggested env vars

```env
APP_ENV=development
HOST=127.0.0.1
PORT=8787
INGEST_TOKEN=replace_me
DB_PATH=./data/health.db
ENABLE_DEBUG_ROUTES=true
OPENCLAW_WEBHOOK_URL=
OPENCLAW_WEBHOOK_TOKEN=
MAX_BODY_BYTES=262144
```

---

## Mock sender and test fixtures

This is an important part of the project and should not be treated as optional.

### Why the mock sender matters

A mock sender gives:

- repeatable local development
- no dependency on phone/watch availability
- deterministic test coverage
- easier schema evolution

### Mock sender responsibilities

The mock sender should:

- run as a simple Python script or second process
- send realistic POST requests to the server
- include bearer auth header
- support multiple fixture files
- support repeated sends for dedupe testing
- optionally jitter timestamps to simulate new data

### Fixture strategy

Create fixture JSON payloads that are:

- based on expected Health Connect-like structures
- close to the real Android app payloads
- versioned and editable
- separated by record type

Suggested fixtures:

- `healthconnect_steps.json`
- `healthconnect_heartrate.json`
- `healthconnect_weight.json`
- `healthconnect_mixed.json`
- `healthconnect_invalid_missing_fields.json`
- `healthconnect_duplicate_event.json`

### Important realism note

At least once, capture one or more **real payloads** from the Android sender in a controlled dev session and preserve them as anonymized fixtures.

That matters more than inventing payloads from memory.

So the fixture strategy should be:

1. start with guessed but plausible structures
2. capture real requests once the app is connected
3. update fixtures to match reality
4. keep both:
   - raw captured fixtures
   - canonical normalized expected outputs

---

## Test plan

### Unit tests

#### `test_auth.py`

Verify:

- missing token rejected
- wrong token rejected
- correct token accepted

#### `test_validation.py`

Verify:

- invalid JSON rejected
- unsupported content type rejected
- oversized payload rejected
- missing fields handled correctly

#### `test_normalize.py`

Verify:

- steps payload becomes canonical event rows
- heart rate payload becomes canonical event rows
- weight payload becomes canonical event rows
- mixed payload becomes multiple canonical event rows

#### `test_ingest_db.py`

Verify:

- raw delivery inserted
- normalized rows inserted
- failure state logged correctly on malformed input

### Integration tests

#### `test_integration_mock_sender.py`

Run the app in-process or as a background process and have the mock sender post to it.

Verify:

- end-to-end ingest works
- persisted row counts are correct
- response payload is correct
- debug endpoint shows recent delivery

### Optional contract tests

Once real payloads are captured, add contract tests that ensure the normalizer still supports them.

That is more useful than writing many speculative tests against imaginary formats.

---

## Dedupe strategy

Do not ignore this.

Webhook senders retry. Mobile apps resend. Background jobs can duplicate.

MVP dedupe approach:

- compute a stable `payload_hash` for raw payloads
- compute a stable event fingerprint for normalized rows
- optionally reject exact duplicate raw deliveries within a short window
- or allow duplicate raw deliveries but prevent duplicate normalized event rows

Recommended stance:

- keep all raw deliveries
- dedupe at normalized event level

That gives better observability.

---

## Logging and observability

Use structured logs for:

- request received
- auth failed
- validation failed
- delivery stored
- normalization count
- forwarding success/failure

Also log:

- delivery ID
- record count
- elapsed time

Avoid overbuilding metrics for MVP.
Plain logs are enough initially.

---

## Optional OpenClaw integration

Not required for the first milestone.

But when added, it should be a separate module that:

- receives normalized events or daily summaries
- POSTs to a local OpenClaw webhook
- never blocks the main ingest success path
- can be disabled by config

Possible modes:

- **summary mode**: send only compact summaries
- **alert mode**: send only unusual conditions
- **mirror mode**: send every normalized event

Recommended first integration:

- summary mode only

Raw event spam into OpenClaw is probably the wrong default.

---

## Milestones

### Milestone 1 — local ingest skeleton

Deliver:

- FastAPI app scaffold
- `/healthz`
- `/ingest/health/v1`
- `.env` config
- bearer auth
- request validation

Success criteria:

- can run locally
- accepts authenticated JSON POST
- returns stable JSON response

### Milestone 2 — SQLite persistence

Deliver:

- database initialization
- `raw_deliveries` table
- `health_events` table
- persistence after ingest
- debug route for recent ingests

Success criteria:

- raw payload and normalized rows persist locally
- recent ingests can be inspected

### Milestone 3 — normalizer and fixtures

Deliver:

- normalizer module
- initial canonical model
- sample fixtures for steps / heart rate / weight / mixed
- mock sender script

Success criteria:

- mock sender can exercise realistic payloads
- stored rows match expected normalized output

### Milestone 4 — test suite

Deliver:

- unit tests
- integration tests using mock sender
- duplicate handling tests

Success criteria:

- core paths covered by tests
- regression protection for payload changes

### Milestone 5 — optional OpenClaw forwarding

Deliver:

- downstream forwarder module
- config-gated forwarding
- forwarding logs

Success criteria:

- successful local persistence does not depend on OpenClaw availability
- forwarding can be toggled on and off

---

## Future phase: Dockerized deployment

This should be a **later phase**, not part of the first successful dev milestone.

### Future Docker target

Run the service in Docker with:

- FastAPI app container
- persistent storage
- SQLite or Postgres
- optional Tailscale / Funnel exposure handled outside or alongside

### Persistence options

#### Option A — SQLite + Docker volume

Use when:

- still single user
- low write volume
- simplest ops desired

Pros:

- minimal complexity
- easy backup/copy
- cheap to run

Cons:

- less suited to multi-process / multi-instance scale

#### Option B — Postgres + Docker volume

Use when:

- analytics become richer
- multiple writers or services appear
- hosted deployment becomes more serious

Pros:

- better concurrency
- easier future expansion

Cons:

- more operational weight
- unnecessary for first version

### Recommendation

Future Docker milestone should start with:

- **FastAPI in Docker**
- **SQLite persisted in a Docker volume or bind-mounted directory**

Postgres should remain a later migration, not an early requirement.

---

## Suggested tech stack

### Core

- Python 3.12+
- FastAPI
- Uvicorn
- Pydantic
- SQLAlchemy Core or SQLModel
- SQLite

### Testing

- pytest
- httpx
- pytest-asyncio
- subprocess-based or thread-based mock sender integration

### Nice-to-have

- Ruff
- mypy
- Alembic

---

## Risks and critique

### Risk: inventing the wrong payload format

Mitigation:

- capture real payloads early
- keep fixtures updated from reality

### Risk: coupling route logic to sender-specific JSON too tightly

Mitigation:

- keep transport parsing and normalization separate

### Risk: overengineering persistence too early

Mitigation:

- stay on SQLite for MVP
- migrate later only when there is evidence

### Risk: making OpenClaw a hard dependency

Mitigation:

- OpenClaw forwarding must be optional and non-blocking

---

## Definition of done for MVP

The MVP is done when all of this is true:

- local FastAPI server runs from a venv
- authenticated webhook requests are accepted
- raw payloads are stored
- normalized rows are stored
- a mock sender can send realistic fixtures
- test suite passes locally
- recent ingests can be inspected through a debug route

Not required for MVP:

- Docker
- Postgres
- hosted deployment
- dashboards
- advanced analytics
- hard OpenClaw integration

---

## Good first prompt for an implementation agent

Build a local Python FastAPI service named `health-ingest` that exposes `POST /ingest/health/v1`, validates a bearer token, accepts JSON webhook payloads from an Android Health Connect sender, stores raw deliveries and normalized health event rows into SQLite, exposes `GET /healthz` and `GET /debug/recent`, includes a mock sender script plus fixture payloads for steps, heart rate, and weight, and includes a pytest test suite covering auth, validation, normalization, persistence, and end-to-end ingest using the mock sender. Keep OpenClaw forwarding optional behind config and do not require Docker for the first working version.
