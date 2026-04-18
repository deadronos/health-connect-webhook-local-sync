# Agents.md

This file guides agents working in this repository.

## Source of Truth

**`docs/architecture/`** is the source of truth for architectural decisions.

All significant technical decisions — database choices, auth strategy, normalization approach, API design, and other cross-cutting concerns — are documented as ADR (Architecture Decision Records) in `docs/architecture/`. When making changes, read the relevant ADR first.

The `docs/superpowers/` directory contains planning and skill artifacts (specs, plans) from the superpowers workflow used to build this project. These are historical records of _how_ decisions were made, not _what_ was decided. In case of conflict between an ADR and a superpowers doc, the ADR wins.

## Mandatory: Keep Docs and Code in Sync

**Every change to the codebase must either:**
1. Align the codebase to match the docs, **or**
2. Update the docs to match the new reality

**Docs and code must never diverge.** If you implement something that contradicts an ADR, you must update the ADR first. If you discover the docs are wrong, update them before or alongside the code change.

Specifically:
- If you add a new record type to the normalizer, update `002-strict-normalizer.md` if it changes the architectural stance
- If you change auth, update `003-bearer-token-auth.md`
- If you change the database layer, update `001-convex-as-database.md`
- If you add a new API endpoint, add or update an ADR
- If you remove or refactor a feature, update or deprecate the relevant ADR

ADRs should be kept accurate but _not_ cluttered with implementation details. They document decisions, not code.

## Mandatory: Changelog

**Append to `CHANGELOG.md`** on every change that affects runtime behavior, API, data model, or developer-facing tooling.

Format: one line per change, starting with `YYYY-MM-DD`. Lines should be:
- **Sanitized** — no tokens, secrets, internal IDs, or verbose debug output
- **Descriptive** — what changed from a reader's perspective
- **Atomic** — one logical change per line

Example:
```
2026-04-18 Add strict if/else normalizer for health record types
2026-04-18 Add bearer token auth to POST /ingest/health/v1
2026-04-18 Add GET /healthz health check endpoint
```

Bad examples (don't do these):
```
2026-04-18 Fixed bug
2026-04-18 Changed stuff
2026-04-18 Updated INGRESS_TOKEN to new value
```

## When to Create a New ADR

Create a new ADR in `docs/architecture/` when:
- You make a decision that affects the architecture (not just implementation details)
- You choose one approach over alternatives — even if the choice seems obvious, document _why_
- You change a previous decision (supersede or mark the old ADR as superseded)

You do not need an ADR for:
- Bug fixes that don't change intended behavior
- Refactoring that preserves the same external API and data model
- Test additions without behavior change

## Project Structure Overview

```
app/                   # FastAPI Python service
  main.py             # App factory and lifespan
  config.py           # pydantic-settings
  auth.py             # BearerAuth
  convex_client.py    # Convex HTTP client
  normalizer.py       # Webhook → canonical events
  models.py           # Internal canonical models
  schemas.py          # Request/response schemas
  routes/
    ingest.py         # POST /ingest/health/v1
    health.py         # GET /healthz
    debug.py          # GET /debug/recent

convex/               # Convex backend (sibling project)
  schema.ts          # Table definitions
  healthIngester/
    mutations.ts     # Database mutations
    queries.ts       # Database queries

fixtures/             # JSON fixture payloads for testing
tools/                # Mock sender CLI
scripts/              # dev.sh, test.sh
tests/                # pytest test suite
docs/
  architecture/       # ADRs (source of truth)
  superpowers/        # Planning artifacts
```

## Key Conventions

- **Python 3.12+**, **FastAPI**, **pydantic-settings**, **httpx**
- **Convex self-hosted** at `http://127.0.0.1:3210`, site proxy at `:3211`
- Bearer token auth — `Authorization: Bearer <INGEST_TOKEN>` on `/ingest/**` and `/debug/**`
- `GET /healthz` is unauthenticated (intentional — for load balancer probes)
- Strict normalizer — raises `NormalizationError` on unknown record types
- All timestamps in milliseconds (Unix epoch ms)
