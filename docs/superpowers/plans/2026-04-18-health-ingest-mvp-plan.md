# Health Connect Webhook Ingest MVP — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Python FastAPI service that receives Health Connect webhook payloads, validates bearer auth, stores raw deliveries and normalized health event rows into self-hosted Convex (SQLite-backed), and exposes health/debug endpoints.

**Architecture:** Single-process FastAPI app with Convex as database. Convex schema managed via `convex` npm package in a sibling `convex/` project directory. Python Convex client uses HTTP actions exposed by the Convex backend.

**Tech Stack:** Python 3.12+, FastAPI, Uvicorn, Pydantic, pydantic-settings, `httpx`, pytest, pytest-asyncio. Convex self-hosted backend already running at `http://127.0.0.1:3210`.

---

## Project Structure

```
health_ingest/
  app/
    __init__.py
    main.py           # FastAPI app, lifespan, startup
    config.py        # pydantic-settings from env
    convex_client.py # Convex HTTP client helpers
    models.py        # Canonical event Pydantic models
    schemas.py       # Incoming webhook payload schemas
    auth.py          # Bearer token middleware
    normalizer.py    # Webhook payload → canonical events
    routes/
      __init__.py
      ingest.py      # POST /ingest/health/v1
      health.py      # GET /healthz
      debug.py       # GET /debug/recent
  tests/
    conftest.py     # Shared fixtures
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
convex/               # Sibling Convex project (npm init convex)
  schema.ts           # Table definitions
  healthIngester/
    lib.ts            # Query/action helpers
    mutations.ts      # Database mutations
    queries.ts       # Database queries
```

---

## Convex Schema Setup

The Python app communicates with Convex via its HTTP API (`http://127.0.0.1:3211` for site proxy / actions). The Convex schema lives in a sibling `convex/` directory.

**Files:**
- Create: `convex/package.json`
- Create: `convex/tsconfig.json`
- Create: `convex/schema.ts`
- Create: `convex/healthIngester/lib.ts`
- Create: `convex/healthIngester/mutations.ts`
- Create: `convex/healthIngester/queries.ts`
- Create: `convex/.env` (CONVEX_SELF_HOSTED_URL, CONVEX_SELF_HOSTED_ADMIN_KEY)

---

### Task 1: Initialize Convex Project

- [ ] **Step 1: Create convex/package.json**

```json
{
  "name": "health-ingest-convex",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "convex dev"
  },
  "dependencies": {
    "convex": "^1.17.0"
  },
  "devDependencies": {
    "typescript": "^5.0.0"
  }
}
```

Run: `cd convex && npm install`

- [ ] **Step 2: Create convex/tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true
  }
}
```

- [ ] **Step 3: Create convex/schema.ts**

```typescript
import { defineSchema } from "convex/schema";
import { authTables } from "convex/server";

export default defineSchema({
  rawDeliveries: defineTable({
    receivedAt: v.number(),           // Unix timestamp ms
    sourceIp: v.string(),
    userAgent: v.optional(v.string()),
    payloadJson: v.string(),          // Raw JSON text
    payloadHash: v.string(),          // SHA-256
    status: v.union(v.literal("stored"), v.literal("error")),
    errorMessage: v.optional(v.string()),
    recordCount: v.number(),
  }).setIndex("by_payload_hash", ["payloadHash"]),

  healthEvents: defineTable({
    rawDeliveryId: v.string(),
    recordType: v.union(
      v.literal("steps"),
      v.literal("heart_rate"),
      v.literal("resting_heart_rate"),
      v.literal("weight")
    ),
    valueNumeric: v.number(),
    unit: v.string(),
    startTime: v.number(),            // Unix timestamp ms
    endTime: v.number(),
    capturedAt: v.number(),
    externalId: v.optional(v.string()),
    payloadHash: v.string(),
    createdAt: v.number(),
  })
    .setIndex("by_delivery", ["rawDeliveryId"])
    .setIndex("by_payload_hash", ["payloadHash"])
    .setIndex("by_fingerprint", ["recordType", "startTime", "valueNumeric", "unit"]),

  forwardAttempts: defineTable({
    rawDeliveryId: v.string(),
    targetName: v.string(),
    attemptedAt: v.number(),
    statusCode: v.optional(v.number()),
    success: v.boolean(),
    errorMessage: v.optional(v.string()),
  }).setIndex("by_delivery", ["rawDeliveryId"]),
});
```

- [ ] **Step 4: Create convex/.env**

```env
CONVEX_SELF_HOSTED_URL=http://127.0.0.1:3210
CONVEX_SELF_HOSTED_ADMIN_KEY=convex-self-hosted|0136e973ee31d38fdb42a558cb59d61dec517e408fb42f0fc5fb6048c51268b873182be57b
```

- [ ] **Step 5: Create convex/healthIngester/lib.ts**

```typescript
import { mutations } from "./mutations";
import { queries } from "./queries";

export const healthIngester = {
  mutations,
  queries,
};
```

- [ ] **Step 6: Create convex/healthIngester/mutations.ts**

```typescript
import { v } from "convex/values";
import { mutation } from "./_generatedServer";

export const storeRawDelivery = mutation({
  args: {
    receivedAt: v.number(),
    sourceIp: v.string(),
    userAgent: v.optional(v.string()),
    payloadJson: v.string(),
    payloadHash: v.string(),
    status: v.union(v.literal("stored"), v.literal("error")),
    errorMessage: v.optional(v.string()),
    recordCount: v.number(),
  },
  handler: async (ctx, args) => {
    const id = await ctx.db.insert("rawDeliveries", args);
    return id;
  },
});

export const storeHealthEvents = mutation({
  args: {
    events: v.array(
      v.object({
        rawDeliveryId: v.string(),
        recordType: v.union(
          v.literal("steps"),
          v.literal("heart_rate"),
          v.literal("resting_heart_rate"),
          v.literal("weight")
        ),
        valueNumeric: v.number(),
        unit: v.string(),
        startTime: v.number(),
        endTime: v.number(),
        capturedAt: v.number(),
        externalId: v.optional(v.string()),
        payloadHash: v.string(),
        createdAt: v.number(),
      })
    ),
  },
  handler: async (ctx, args) => {
    const ids: string[] = [];
    for (const event of args.events) {
      const id = await ctx.db.insert("healthEvents", event);
      ids.push(id);
    }
    return ids;
  },
});

export const checkDuplicateDelivery = mutation({
  args: { payloadHash: v.string() },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("rawDeliveries")
      .withIndex("by_payload_hash", (q) => q.eq("payloadHash", args.payloadHash))
      .first();
    return existing !== null;
  },
});
```

- [ ] **Step 7: Create convex/healthIngester/queries.ts**

```typescript
import { v } from "convex/values";
import { query } from "./_generatedServer";

export const listRecentDeliveries = query({
  args: { limit: v.optional(v.number()) },
  handler: async (ctx, args) => {
    const limit = args.limit ?? 10;
    const deliveries = await ctx.db
      .query("rawDeliveries")
      .order("desc")
      .take(limit);
    return deliveries.map((d) => ({
      deliveryId: d._id,
      receivedAt: d.receivedAt,
      recordCount: d.recordCount,
      status: d.status,
    }));
  },
});

export const getDeliveryById = query({
  args: { deliveryId: v.string() },
  handler: async (ctx, args) => {
    const delivery = await ctx.db.get(args.deliveryId as any);
    return delivery;
  },
});

export const getHealthEventsByDelivery = query({
  args: { rawDeliveryId: v.string() },
  handler: async (ctx, args) => {
    const events = await ctx.db
      .query("healthEvents")
      .withIndex("by_delivery", (q) => q.eq("rawDeliveryId", args.rawDeliveryId))
      .collect();
    return events;
  },
});

export const checkDbHealth = query({
  args: {},
  handler: async (ctx) => {
    try {
      await ctx.db.query("rawDeliveries").take(1);
      return { ok: true, db: "ok" };
    } catch {
      return { ok: false, db: "error" };
    }
  },
});
```

- [ ] **Step 8: Push Convex schema**

Run: `cd convex && npx convex dev --force`
(Accept all prompts to create the Convex project in the current directory. Say "yes" when asked to create the first app/module.)

Note: Convex dev expects to run interactively — use `--force` to skip prompts or pipe answers. Check `npx convex --help` for non-interactive options.

Alternative: if `convex dev` requires interactive setup, create a minimal `convex.json` pointing to the local deployment:

```json
{
  "functions": "healthIngester"
}
```

Then run `npx convex deploy` to push the schema.

- [ ] **Step 9: Commit**

```bash
git add convex/ && git commit -m "feat: add Convex schema and mutations/queries for health-ingest"
```

---

## Python Package Setup

**Files:**
- Create: `pyproject.toml`
- Create: `app/__init__.py`
- Create: `.env.example`

---

### Task 2: Python Package Boilerplate

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "health-ingest"
version = "0.1.0"
description = "Health Connect webhook ingest server"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "pydantic>=2.9.0",
    "pydantic-settings>=2.5.0",
    "httpx>=0.27.0",
    "python-dotenv>=1.0.0",
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

Run: `python3 -m venv .venv && source .venv/bin/activate && pip install -e .`

- [ ] **Step 2: Create app/__init__.py**

```python
"""Health Connect webhook ingest server."""
```

- [ ] **Step 3: Create .env.example**

```env
APP_ENV=development
APP_HOST=127.0.0.1
APP_PORT=8787
INGEST_TOKEN=replace_me
CONVEX_SELF_HOSTED_URL=http://127.0.0.1:3210
CONVEX_SELF_HOSTED_ADMIN_KEY=convex-self-hosted|REPLACE_ME
ENABLE_DEBUG_ROUTES=true
MAX_BODY_BYTES=262144
OPENCLAW_WEBHOOK_URL=
OPENCLAW_WEBHOOK_TOKEN=
```

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml app/__init__.py .env.example && git commit -m "feat: add Python package boilerplate"
```

---

### Task 3: Config Module

**Files:**
- Create: `app/config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
from app.config import Settings

def test_settings_loads_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("INGEST_TOKEN", "test-token")
    monkeypatch.setenv("CONVEX_SELF_HOSTED_URL", "http://localhost:3210")
    monkeypatch.setenv("CONVEX_SELF_HOSTED_ADMIN_KEY", "test-key")
    settings = Settings()
    assert settings.ingest_token == "test-token"
    assert settings.convex_self_hosted_url == "http://localhost:3210"
```

Run: `pytest tests/test_config.py -v` — expect FAIL (module not found)

- [ ] **Step 2: Create app/config.py**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_env: str = "development"
    host: str = "127.0.0.1"
    port: int = 8787
    ingest_token: str = "replace_me"
    convex_self_hosted_url: str = "http://127.0.0.1:3210"
    convex_self_hosted_admin_key: str = ""
    enable_debug_routes: bool = True
    max_body_bytes: int = 262144
    openclaw_webhook_url: str = ""
    openclaw_webhook_token: str = ""

    @property
    def convex_site_url(self) -> str:
        """Site proxy URL for Convex HTTP actions."""
        return f"{self.convex_self_hosted_url}/api/site"
```

- [ ] **Step 3: Run test to verify it passes**

Run: `pytest tests/test_config.py -v` — expect PASS

- [ ] **Step 4: Commit**

```bash
git add app/config.py tests/test_config.py && git commit -m "feat: add Settings config module"
```

---

### Task 4: Pydantic Models & Schemas

**Files:**
- Create: `app/models.py`
- Create: `app/schemas.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_models.py
from app.models import HealthEvent

def test_health_event_model():
    event = HealthEvent(
        source="health-connect-webhook",
        record_type="steps",
        value=8421,
        unit="count",
        start_time=1713446400000,
        end_time=1713489296000,
        captured_at=1713489302000,
        payload_hash="abc123",
        raw_delivery_id="delivery-123",
    )
    assert event.record_type == "steps"
    assert event.value == 8421
    assert event.unit == "count"
```

```python
# tests/test_schemas.py
from app.schemas import IngestRequest

def test_ingest_request_parses_valid_payload():
    payload = {
        "records": [
            {
                "record_type": "steps",
                "value": 8421,
                "unit": "count",
                "start_time_ms": 1713446400000,
                "end_time_ms": 1713489296000,
            }
        ]
    }
    req = IngestRequest.model_validate(payload)
    assert len(req.records) == 1
    assert req.records[0].record_type == "steps"
```

Run: `pytest tests/test_models.py tests/test_schemas.py -v` — expect FAIL (modules not found)

- [ ] **Step 2: Create app/models.py**

```python
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RecordType(str, Enum):
    STEPS = "steps"
    HEART_RATE = "heart_rate"
    RESTING_HEART_RATE = "resting_heart_rate"
    WEIGHT = "weight"


class HealthEvent(BaseModel):
    source: str = "health-connect-webhook"
    device_id: Optional[str] = None
    record_type: RecordType
    value: float = Field(validation_alias="value_numeric")
    unit: str
    start_time: int = Field(validation_alias="start_time_ms")
    end_time: int = Field(validation_alias="end_time_ms")
    captured_at: int = Field(validation_alias="captured_at_ms")
    external_id: Optional[str] = None
    payload_hash: str
    raw_delivery_id: str

    model_config = {
        "populate_by_name": True,
    }
```

- [ ] **Step 3: Create app/schemas.py**

```python
from typing import Any, Optional

from pydantic import BaseModel, Field


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_models.py tests/test_schemas.py -v` — expect PASS

- [ ] **Step 5: Commit**

```bash
git add app/models.py app/schemas.py tests/test_models.py tests/test_schemas.py && git commit -m "feat: add Pydantic models and schemas"
```

---

### Task 5: Convex Client

**Files:**
- Create: `app/convex_client.py`
- Create: `tests/test_convex_client.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_convex_client.py
from app.convex_client import ConvexClient

def test_convex_client_site_url():
    client = ConvexClient(
        convex_url="http://127.0.0.1:3210",
        admin_key="test-key"
    )
    assert client.site_url == "http://127.0.0.1:3210/api/site"
```

Run: `pytest tests/test_convex_client.py -v` — expect FAIL

- [ ] **Step 2: Create app/convex_client.py**

```python
import hashlib
import json
from datetime import datetime
from typing import Optional

import httpx

from app.config import Settings


class ConvexClient:
    def __init__(self, convex_url: str, admin_key: str):
        self.site_url = f"{convex_url}/api/site"
        self.admin_key = admin_key

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.admin_key}",
            "Content-Type": "application/json",
        }

    def mutation(self, mutation_name: str, args: dict) -> dict:
        payload = {
            "mutation": mutation_name,
            "args": args,
        }
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                self.site_url,
                json=payload,
                headers=self._headers(),
            )
        resp.raise_for_status()
        return resp.json()

    def query(self, query_name: str, args: dict) -> dict:
        payload = {
            "query": query_name,
            "args": args,
        }
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                self.site_url,
                json=payload,
                headers=self._headers(),
            )
        resp.raise_for_status()
        return resp.json()

    def store_raw_delivery(
        self,
        source_ip: str,
        user_agent: Optional[str],
        payload_json: str,
        record_count: int,
        status: str = "stored",
        error_message: Optional[str] = None,
    ) -> str:
        payload_hash = hashlib.sha256(payload_json.encode()).hexdigest()
        received_at = int(datetime.utcnow().timestamp() * 1000)
        result = self.mutation("healthIngester/mutations/storeRawDelivery", {
            "receivedAt": received_at,
            "sourceIp": source_ip,
            "userAgent": user_agent,
            "payloadJson": payload_json,
            "payloadHash": payload_hash,
            "status": status,
            "errorMessage": error_message,
            "recordCount": record_count,
        })
        return result["value"]

    def store_health_events(self, events: list[dict]) -> list[str]:
        if not events:
            return []
        result = self.mutation("healthIngester/mutations/storeHealthEvents", {
            "events": events,
        })
        return result["value"]

    def check_duplicate(self, payload_hash: str) -> bool:
        result = self.mutation("healthIngester/mutations/checkDuplicateDelivery", {
            "payloadHash": payload_hash,
        })
        return result["value"]

    def list_recent_deliveries(self, limit: int = 10) -> list[dict]:
        result = self.query("healthIngester/queries/listRecentDeliveries", {
            "limit": limit,
        })
        return result["value"] or []

    def check_db_health(self) -> dict:
        result = self.query("healthIngester/queries/checkDbHealth", {})
        return result["value"]
```

- [ ] **Step 3: Run test to verify it passes**

Run: `pytest tests/test_convex_client.py -v` — expect PASS

- [ ] **Step 4: Commit**

```bash
git add app/convex_client.py tests/test_convex_client.py && git commit -m "feat: add Convex HTTP client"
```

---

### Task 6: Auth Middleware

**Files:**
- Create: `app/auth.py`
- Create: `tests/test_auth.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_auth.py
import pytest
from fastapi import HTTPException
from app.auth import BearerAuthMiddleware

def test_missing_token_raises():
    middleware = BearerAuthMiddleware(token="secret")
    with pytest.raises(HTTPException) as exc_info:
        middleware.verify(None)
    assert exc_info.value.status_code == 401

def test_wrong_token_raises():
    middleware = BearerAuthMiddleware(token="secret")
    with pytest.raises(HTTPException) as exc_info:
        middleware.verify("Bearer wrong")
    assert exc_info.value.status_code == 401

def test_correct_token_passes():
    middleware = BearerAuthMiddleware(token="secret")
    result = middleware.verify("Bearer secret")
    assert result is True
```

Run: `pytest tests/test_auth.py -v` — expect FAIL

- [ ] **Step 2: Create app/auth.py**

```python
from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import Settings


class BearerAuthMiddleware:
    def __init__(self, token: str):
        self.token = token

    def verify(self, authorization: str | None) -> bool:
        if not authorization:
            raise HTTPException(status_code=401, detail="Missing authorization header")
        parts = authorization.split(" ")
        if len(parts) != 2 or parts[0] != "Bearer":
            raise HTTPException(status_code=401, detail="Invalid authorization header format")
        if parts[1] != self.token:
            raise HTTPException(status_code=401, detail="Invalid token")
        return True
```

- [ ] **Step 3: Run test to verify it passes**

Run: `pytest tests/test_auth.py -v` — expect PASS

- [ ] **Step 4: Commit**

```bash
git add app/auth.py tests/test_auth.py && git commit -m "feat: add bearer token auth middleware"
```

---

### Task 7: Normalizer

**Files:**
- Create: `app/normalizer.py`
- Create: `tests/test_normalize.py`
- Create: `fixtures/healthconnect_steps.json` and other fixtures

- [ ] **Step 1: Write failing test**

```python
# tests/test_normalize.py
from app.normalizer import Normalizer

def test_normalize_steps():
    payload = {
        "records": [
            {
                "record_type": "steps",
                "value": 8421,
                "unit": "count",
                "start_time_ms": 1713446400000,
                "end_time_ms": 1713489296000,
                "captured_at_ms": 1713489302000,
            }
        ]
    }
    normalizer = Normalizer(payload_hash="abc123", delivery_id="del-1")
    events = normalizer.normalize()
    assert len(events) == 1
    assert events[0]["record_type"] == "steps"
    assert events[0]["value_numeric"] == 8421
    assert events[0]["unit"] == "count"

def test_normalize_unsupported_type_raises():
    payload = {
        "records": [
            {
                "record_type": "blood_oxygen",
                "value": 98,
                "unit": "%",
                "start_time_ms": 1713446400000,
                "end_time_ms": 1713489296000,
            }
        ]
    }
    normalizer = Normalizer(payload_hash="abc123", delivery_id="del-1")
    with pytest.raises(ValueError, match="unsupported record type"):
        normalizer.normalize()
```

Run: `pytest tests/test_normalize.py -v` — expect FAIL

- [ ] **Step 2: Create fixtures**

Create `fixtures/healthconnect_steps.json`:
```json
{
  "records": [
    {
      "record_type": "steps",
      "value": 8421,
      "unit": "count",
      "start_time_ms": 1713446400000,
      "end_time_ms": 1713489296000,
      "captured_at_ms": 1713489302000
    }
  ]
}
```

Create `fixtures/healthconnect_heartrate.json`:
```json
{
  "records": [
    {
      "record_type": "heart_rate",
      "value": 72,
      "unit": "bpm",
      "start_time_ms": 1713446400000,
      "end_time_ms": 1713489296000,
      "captured_at_ms": 1713489302000
    }
  ]
}
```

Create `fixtures/healthconnect_weight.json`:
```json
{
  "records": [
    {
      "record_type": "weight",
      "value": 72.5,
      "unit": "kg",
      "start_time_ms": 1713446400000,
      "end_time_ms": 1713489296000,
      "captured_at_ms": 1713489302000
    }
  ]
}
```

Create `fixtures/healthconnect_mixed.json`:
```json
{
  "records": [
    {
      "record_type": "steps",
      "value": 8421,
      "unit": "count",
      "start_time_ms": 1713446400000,
      "end_time_ms": 1713489296000,
      "captured_at_ms": 1713489302000
    },
    {
      "record_type": "heart_rate",
      "value": 72,
      "unit": "bpm",
      "start_time_ms": 1713446400000,
      "end_time_ms": 1713489296000,
      "captured_at_ms": 1713489302000
    }
  ]
}
```

Create `fixtures/healthconnect_invalid_missing_fields.json`:
```json
{
  "records": [
    {
      "record_type": "steps",
      "value": 8421
    }
  ]
}
```

Create `fixtures/healthconnect_duplicate_event.json`:
```json
{
  "records": [
    {
      "record_type": "steps",
      "value": 8421,
      "unit": "count",
      "start_time_ms": 1713446400000,
      "end_time_ms": 1713489296000,
      "captured_at_ms": 1713489302000
    }
  ]
}
```

- [ ] **Step 3: Create app/normalizer.py**

```python
import hashlib
import json
from datetime import datetime
from typing import Any

from app.models import RecordType


class NormalizationError(ValueError):
    pass


class Normalizer:
    SUPPORTED_TYPES = {"steps", "heart_rate", "resting_heart_rate", "weight"}

    UNIT_MAP = {
        "steps": "count",
        "heart_rate": "bpm",
        "resting_heart_rate": "bpm",
        "weight": "kg",
    }

    def __init__(self, payload: dict[str, Any], payload_hash: str, delivery_id: str):
        self.payload = payload
        self.payload_hash = payload_hash
        self.delivery_id = delivery_id
        self._records: list[dict] = payload.get("records", [])

    def normalize(self) -> list[dict]:
        events = []
        for record in self._records:
            record_type = record.get("record_type")
            if record_type not in self.SUPPORTED_TYPES:
                raise NormalizationError(f"unsupported record type: {record_type}")

            value = record["value"]
            unit = record.get("unit") or self.UNIT_MAP[record_type]
            start_time = record["start_time_ms"]
            end_time = record["end_time_ms"]
            captured_at = record.get("captured_at_ms", int(datetime.utcnow().timestamp() * 1000))
            external_id = record.get("external_id")
            device_id = record.get("device_id")

            # Fingerprint for dedupe at event level
            fingerprint = f"{record_type}:{start_time}:{value}:{unit}"

            event = {
                "rawDeliveryId": self.delivery_id,
                "recordType": record_type,
                "valueNumeric": float(value),
                "unit": unit,
                "startTime": start_time,
                "endTime": end_time,
                "capturedAt": captured_at,
                "externalId": external_id,
                "deviceId": device_id,
                "payloadHash": self.payload_hash,
                "createdAt": int(datetime.utcnow().timestamp() * 1000),
            }
            events.append(event)
        return events

    def compute_payload_hash(self) -> str:
        return hashlib.sha256(
            json.dumps(self.payload, sort_keys=True).encode()
        ).hexdigest()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_normalize.py -v` — expect PASS

- [ ] **Step 5: Commit**

```bash
git add app/normalizer.py tests/test_normalize.py fixtures/ && git commit -m "feat: add normalizer and fixture files"
```

---

### Task 8: Route Modules

**Files:**
- Create: `app/routes/__init__.py`
- Create: `app/routes/ingest.py`
- Create: `app/routes/health.py`
- Create: `app/routes/debug.py`

- [ ] **Step 1: Write failing test for ingest route**

```python
# tests/test_ingest_route.py
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_ingest_requires_auth():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.post("/ingest/health/v1", json={"records": []})
        assert resp.status_code == 401
```

Run: `pytest tests/test_ingest_route.py -v` — expect FAIL

- [ ] **Step 2: Create app/routes/__init__.py**

```python
"""Route modules."""
```

- [ ] **Step 3: Create app/routes/ingest.py**

```python
import hashlib
import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException, Depends

from app.auth import BearerAuthMiddleware
from app.config import Settings
from app.schemas import IngestRequest, IngestResponse
from app.convex_client import ConvexClient
from app.normalizer import Normalizer, NormalizationError

settings = Settings()
auth = BearerAuthMiddleware(token=settings.ingest_token)
client = ConvexClient(
    convex_url=settings.convex_self_hosted_url,
    admin_key=settings.convex_self_hosted_admin_key,
)

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/health/v1", response_model=IngestResponse)
async def ingest_health(request: Request):
    # Verify auth
    auth_header = request.headers.get("authorization")
    auth.verify(auth_header)

    # Parse body
    body = await request.body()
    if len(body) > settings.max_body_bytes:
        raise HTTPException(status_code=413, detail="Payload too large")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="Malformed JSON")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Payload must be a JSON object")

    # Validate with schema
    try:
        ingest_req = IngestRequest.model_validate(payload)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid payload: {e}")

    # Compute hash
    payload_json = json.dumps(payload, sort_keys=True)
    payload_hash = hashlib.sha256(payload_json.encode()).hexdigest()

    # Generate delivery ID
    delivery_id = str(uuid.uuid4())[:8]

    # Store raw delivery
    source_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent")

    try:
        stored_delivery_id = client.store_raw_delivery(
            source_ip=source_ip,
            user_agent=user_agent,
            payload_json=payload_json,
            record_count=len(ingest_req.records),
            status="stored",
        )
    except Exception as e:
        client.store_raw_delivery(
            source_ip=source_ip,
            user_agent=user_agent,
            payload_json=payload_json,
            record_count=0,
            status="error",
            error_message=str(e),
        )
        raise HTTPException(status_code=500, detail="Database error")

    # Normalize and store events
    normalizer = Normalizer(payload=payload, payload_hash=payload_hash, delivery_id=stored_delivery_id)
    try:
        events = normalizer.normalize()
    except NormalizationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    stored_count = 0
    if events:
        try:
            client.store_health_events(events)
            stored_count = len(events)
        except Exception:
            pass  # Log but don't fail — raw delivery succeeded

    return IngestResponse(
        ok=True,
        received_records=len(ingest_req.records),
        stored_records=stored_count,
        delivery_id=stored_delivery_id,
    )
```

- [ ] **Step 4: Create app/routes/health.py**

```python
from fastapi import APIRouter
from pydantic import BaseModel

from app.convex_client import ConvexClient
from app.config import Settings

settings = Settings()
client = ConvexClient(
    convex_url=settings.convex_self_hosted_url,
    admin_key=settings.convex_self_hosted_admin_key,
)

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    ok: bool
    db: str


@router.get("/healthz", response_model=HealthResponse)
async def healthz():
    health = client.check_db_health()
    return HealthResponse(
        ok=health.get("ok", False),
        db=health.get("db", "unknown"),
    )
```

- [ ] **Step 5: Create app/routes/debug.py**

```python
from fastapi import APIRouter, Query, Request, HTTPException, Depends

from app.auth import BearerAuthMiddleware
from app.config import Settings
from app.schemas import DebugResponse, DebugDelivery
from app.convex_client import ConvexClient

settings = Settings()
auth = BearerAuthMiddleware(token=settings.ingest_token)
client = ConvexClient(
    convex_url=settings.convex_self_hosted_url,
    admin_key=settings.convex_self_hosted_admin_key,
)

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/recent", response_model=DebugResponse)
async def debug_recent(request: Request, limit: int = Query(default=10, ge=1, le=100)):
    if not settings.enable_debug_routes:
        raise HTTPException(status_code=404, detail="Debug routes disabled")

    auth_header = request.headers.get("authorization")
    auth.verify(auth_header)

    deliveries = client.list_recent_deliveries(limit=limit)
    return DebugResponse(
        deliveries=[
            DebugDelivery(
                delivery_id=d["deliveryId"],
                received_at=datetime.fromtimestamp(d["receivedAt"] / 1000).isoformat() + "Z",
                record_count=d["recordCount"],
                status=d["status"],
            )
            for d in deliveries
        ]
    )
```

- [ ] **Step 6: Commit**

```bash
git add app/routes/ && git commit -m "feat: add FastAPI route modules"
```

---

### Task 9: Main App

**Files:**
- Create: `app/main.py`
- Modify: `app/routes/ingest.py` (add missing import)

- [ ] **Step 1: Write failing test**

```python
# tests/test_main.py
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_healthz_no_auth():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.get("/healthz")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
```

Run: `pytest tests/test_main.py -v` — expect FAIL

- [ ] **Step 2: Create app/main.py**

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.routes import ingest, health, debug


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: verify Convex connection
    yield
    # Shutdown


def create_app() -> FastAPI:
    app = FastAPI(
        title="Health Connect Webhook Ingest",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(health.router)
    app.include_router(ingest.router)
    app.include_router(debug.router)
    return app


app = create_app()
```

- [ ] **Step 3: Fix import in ingest.py** — add `from datetime import datetime` at top

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_main.py -v` — expect PASS

- [ ] **Step 5: Commit**

```bash
git add app/main.py app/routes/ingest.py && git commit -m "feat: add FastAPI main app"
```

---

### Task 10: Mock Sender

**Files:**
- Create: `tools/mock_sender.py`
- Create: `scripts/dev.sh`
- Create: `scripts/test.sh`

- [ ] **Step 1: Create tools/mock_sender.py**

```python
#!/usr/bin/env python3
"""Mock sender — sends fixture payloads to the ingest server."""

import argparse
import hashlib
import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

import httpx


def jitter_timestamps(payload: dict, jitter_hours: int = 1) -> dict:
    """Shift all timestamps by a random offset within jitter_hours."""
    offset_ms = random.randint(-jitter_hours, jitter_hours) * 3600 * 1000
    records = payload.get("records", [])
    for record in records:
        for field in ("start_time_ms", "end_time_ms", "captured_at_ms"):
            if field in record:
                record[field] += offset_ms
    return payload


def send_fixture(
    fixture_path: Path,
    url: str,
    token: str,
    jitter_hours: int = 0,
    repeat: int = 1,
) -> bool:
    with open(fixture_path) as f:
        payload = json.load(f)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=30.0) as client:
        for i in range(repeat):
            p = jitter_timestamps(payload, jitter_hours) if jitter_hours > 0 else payload
            try:
                resp = client.post(url, json=p, headers=headers)
                resp.raise_for_status()
                print(f"[{i+1}/{repeat}] OK: {resp.json()}")
            except httpx.HTTPStatusError as e:
                print(f"[{i+1}/{repeat}] ERROR {e.response.status_code}: {e.response.text}", file=sys.stderr)
                return False
            except Exception as e:
                print(f"[{i+1}/{repeat}] ERROR: {e}", file=sys.stderr)
                return False
    return True


def main():
    parser = argparse.ArgumentParser(description="Send mock Health Connect webhook payloads")
    parser.add_argument("--fixture", type=Path, required=True, help="Path to fixture JSON file")
    parser.add_argument("--url", default="http://127.0.0.1:8787/ingest/health/v1", help="Ingest endpoint URL")
    parser.add_argument("--token", default="replace_me", help="Bearer token")
    parser.add_argument("--repeat", type=int, default=1, help="Number of times to repeat")
    parser.add_argument("--jitter-hours", type=int, default=0, help="Random timestamp jitter in hours")
    args = parser.parse_args()

    if not args.fixture.exists():
        print(f"Fixture not found: {args.fixture}", file=sys.stderr)
        sys.exit(1)

    success = send_fixture(
        fixture_path=args.fixture,
        url=args.url,
        token=args.token,
        jitter_hours=args.jitter_hours,
        repeat=args.repeat,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create scripts/dev.sh**

```bash
#!/bin/bash
set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
uvicorn app.main:app --reload --host 127.0.0.1 --port 8787
```

- [ ] **Step 3: Create scripts/test.sh**

```bash
#!/bin/bash
set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest tests/ -v
```

- [ ] **Step 4: Make scripts executable**

Run: `chmod +x scripts/dev.sh scripts/test.sh tools/mock_sender.py`

- [ ] **Step 5: Commit**

```bash
git add tools/mock_sender.py scripts/dev.sh scripts/test.sh && git commit -m "feat: add mock sender and dev scripts"
```

---

### Task 11: Test Suite — Auth, Validation, Normalization

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/test_auth.py` (already created in Task 6, verify)
- Create: `tests/test_validation.py`
- Create: `tests/test_normalize.py` (already created in Task 7, verify)

- [ ] **Step 1: Create tests/conftest.py**

```python
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

@pytest.fixture
def mock_convex_client():
    with patch("app.convex_client.ConvexClient") as mock:
        client = MagicMock()
        client.store_raw_delivery.return_value = "test-delivery-id"
        client.store_health_events.return_value = ["event-1"]
        client.check_duplicate.return_value = False
        client.list_recent_deliveries.return_value = []
        client.check_db_health.return_value = {"ok": True, "db": "ok"}
        mock.return_value = client
        yield client


@pytest.fixture
def test_client(mock_convex_client):
    from app.main import create_app
    app = create_app()
    return TestClient(app)
```

- [ ] **Step 2: Create tests/test_validation.py**

```python
import pytest
from unittest.mock import patch, MagicMock


def test_malformed_json_rejected(test_client):
    with patch("app.convex_client.ConvexClient") as mock:
        client = MagicMock()
        client.store_raw_delivery.return_value = "test-id"
        mock.return_value = client
        response = test_client.post(
            "/ingest/health/v1",
            content=b"not valid json",
            headers={"Authorization": "Bearer replace_me", "Content-Type": "application/json"},
        )
        assert response.status_code == 422


def test_missing_record_type_rejected(test_client):
    with patch("app.convex_client.ConvexClient") as mock:
        client = MagicMock()
        client.store_raw_delivery.return_value = "test-id"
        mock.return_value = client
        payload = {"records": [{"value": 100, "unit": "count"}]}
        response = test_client.post(
            "/ingest/health/v1",
            json=payload,
            headers={"Authorization": "Bearer replace_me"},
        )
        assert response.status_code == 422
```

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/ -v` — expect all PASS

- [ ] **Step 4: Commit**

```bash
git add tests/ && git commit -m "test: add test suite"
```

---

## Spec Coverage Check

| Spec Section | Task(s) |
|---|---|
| Tech stack & structure | Task 1, 2 |
| Bearer auth | Task 6 |
| `/ingest/health/v1` endpoint | Task 8 |
| `/healthz` endpoint | Task 8 |
| `/debug/recent` endpoint | Task 8 |
| `.env` config | Task 3, 4 |
| Convex tables (raw_deliveries, health_events) | Task 1 |
| Normalizer (4 record types) | Task 7 |
| Fixture files | Task 7 |
| Mock sender | Task 10 |
| pytest test suite | Task 4, 6, 7, 11 |
| Debug routes gated by config | Task 8 |

---

## Plan Complete

All tasks written. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
