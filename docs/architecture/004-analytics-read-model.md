# ADR-004: Use Convex Rollup Buckets for the Phase-2 Analytics Read Model

**Date:** 2026-04-19
**Status:** Accepted
**Deciders:** deadronos

---

## Context

Phase 2 adds three new needs on top of the ingest MVP:

- overview analytics per record type
- time-series reads for a built-in dashboard
- moderate-burst ingest hardening with event-level idempotency

The service already uses Convex self-hosted as the system of record for raw deliveries and normalized health events. The question for Phase 2 was whether to:

1. stay Convex-first and add a small read model there
2. move the analytics/read path to PostgreSQL now
3. defer analytics entirely until a second database exists

The project is still local-first, single-user, and intentionally lightweight. Introducing a second database just to unlock the first dashboard would increase operational overhead before the workload proves it is necessary.

---

## Decision

Keep **Convex self-hosted** as the system of record for Phase 2 and add a lightweight analytics read model there.

Specifically:

- use a single ingest mutation to store the raw delivery, dedupe normalized events by `fingerprint`, insert only new events, and update rollup buckets
- store analytics rollups in `healthEventBuckets`
- support `hour` and `day` bucket sizes first
- expose authenticated `/analytics/**` APIs from FastAPI
- serve the first dashboard from FastAPI with Jinja2 templates and vanilla JavaScript

Postgres remains deferred until the workload creates a concrete need for it.

---

## Reasons

### Reuse the existing source of truth

Raw deliveries and canonical events already live in Convex. Keeping the first analytics layer in the same system avoids cross-store synchronization work, separate migrations, and new operational moving parts.

### Rollups solve the immediate dashboard problem

The dashboard needs fast-enough summary reads and simple time-series data. Hour/day buckets provide that without building a second analytics stack.

### Idempotency and analytics fit the same write path

Once events have a stable `fingerprint`, the same ingest mutation can both reject duplicates and update read-model buckets. That keeps the Phase-2 write path coherent.

### Postgres should be triggered by real pressure, not anticipation

A Postgres migration makes sense later if the read model needs richer joins, more dimensions, or stronger concurrency guarantees. Those pressures are possible, but they are not yet required to ship the first analytics experience.

---

## Consequences

### Positive

- phase-2 analytics ships without introducing a second database
- ingest remains local-first and operationally simple
- the dashboard can be built directly on authenticated FastAPI routes
- rollup buckets provide a clear stepping stone toward a future migration if one becomes necessary

### Negative

- bucket updates can become hot writes under heavier concurrency
- some analytics queries may still need event scans when bucket dimensions are not sufficient
- the read model is intentionally modest and not a replacement for a full analytics database

---

## Migration Triggers

Revisit PostgreSQL when one or more of these become true:

- repeated writer contention on bucket updates becomes normal
- dashboard queries need dimensions or joins beyond `recordType`, time range, and optional `deviceId`
- export and analytics workloads no longer fit the local-first Convex operating model cleanly
- multiple users or many devices become the common case rather than an edge case

---

## Notes

This ADR does not claim Convex is the final analytics destination. It records that **for Phase 2**, Convex rollup buckets are the smallest architecture that satisfies the current dashboard and analytics requirements while keeping the project easy to run locally.
