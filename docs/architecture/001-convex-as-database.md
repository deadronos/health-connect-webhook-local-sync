# ADR-001: Use Convex as the Primary Database

**Date:** 2026-04-18
**Status:** Accepted
**Deciders:** deadronos

---

## Context

The health-ingest service needs durable storage for:

- Raw webhook deliveries (for audit/replay)
- Normalized health event rows
- Analytics rollup buckets for overview and time-series reads
- Forward attempt metadata (future use)

Three candidates were considered:

1. **Convex self-hosted (SQLite-backed)** — as recommended in `idea.md`
2. **Raw SQLite + SQLAlchemy/SQLModel** — explicit schema, more control
3. **PostgreSQL** — over-engineered for MVP scope

---

## Decision

Use **Convex self-hosted with SQLite backing** as the default database for the ingest write path and the phase-2 analytics read model.

---

## Reasons

### Convex vs Raw SQLite

- **Schema management** — Convex manages migrations automatically via `convex dev`. No manual `ALTER TABLE` statements or migration files.
- **HTTP API** — Python client communicates via HTTP, which naturally fits a FastAPI service and avoids threading/concurrency issues with SQLite.
- **TypeScript-generated bindings** — The `_generated/` directory provides end-to-end type safety from schema to queries.
- **Query engine** — Convex's query engine handles indexing and ordering efficiently without requiring raw SQL.
- **MVP-appropriate** — The self-hosted Convex deployment in `convex-local/docker-compose.yml` is already running at `http://127.0.0.1:3210`. Reusing it avoids standing up another service.

### Convex vs PostgreSQL

- **Operational weight** — Postgres is unnecessary for a single-user, single-device, low-write-volume MVP.
- **Over-engineering risk** — The `idea.md` explicitly calls out Postgres as "worth it later" only when multi-device, dashboards, or external analytics appear.
- **SQLite is sufficient** — Convex uses SQLite under the hood for self-hosted deployments. That is more than enough at this stage.

---

## Consequences

### Positive

- Schema pushes are automatic via `convex dev` / `convex deploy`
- No separate database migration tooling needed
- Convex powers both the ingest storage and (optionally) OpenClaw integration in the future
- Phase 2 can answer overview and time-series reads from Convex buckets without introducing a second database

### Negative

- Convex table definitions live in `convex/schema.ts` (TypeScript), which is a separate build system from the Python app
- The Python Convex client uses raw HTTP calls (no official Python SDK for self-hosted deployments — `convexleyball` targets cloud deployments)
- If Convex proves insufficient later, migration to Postgres will require a rewrite of `app/convex_client.py` and `convex/schema.ts`
- Rollup buckets are intentionally simple; if query dimensions or writer contention grow, this design will hit limits sooner than a dedicated analytics database

---

## Alternatives Considered

| Option | Why Not Chosen |
| ------ | -------------- |
| Raw SQLite + SQLAlchemy | More boilerplate, manual migrations, no query engine |
| PostgreSQL + Docker volume | Overkill for MVP; adds operational complexity |
| SQLite viaaiosqlite + raw SQL | No schema management, no type safety, manual migrations |

---

## Notes

The Convex backend must be reachable at `CONVEX_SELF_HOSTED_URL` for the Python app to function. The `convex/` directory is a sibling to `app/` and communicates via the backend at `http://127.0.0.1:3210/api` (not the site proxy at 3211).

Python client uses the official `ConvexHttpClient` from the `convex` Python package and calls functions using `module.js:functionName` paths (e.g., `mutations.js:storeRawDelivery`).

Convex function names are relative to the `convex.json` functions directory, not the full module path.

Phase 2 adds a `healthEventBuckets` table for `hour` and `day` rollups so the built-in dashboard and `/analytics/**` APIs can stay Convex-first.

Revisit Postgres when one or more of these become true:

- sustained concurrent writers cause repeated contention on bucket updates
- dashboard queries need joins or dimensions beyond `recordType`, time range, and optional `deviceId`
- analytics/export workloads stop fitting the current local-first operating model
