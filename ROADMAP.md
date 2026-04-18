# Roadmap

This repo exists to be a local ingest and normalization boundary between Android Health Connect payloads and everything downstream. It should accept webhook data, validate it, normalize it into a stable internal shape, store both raw and canonical records durably, and make that data easy to inspect, test, replay, and later automate against.

## Current State

- The MVP works today: FastAPI ingest, bearer-token auth, Convex-backed persistence, health/debug routes, fixtures, mock sender, and pytest coverage.
- The stack is intentionally local-first and lightweight: one Python service, one Convex backend, no queue, no separate frontend app, no Postgres.
- The service is still primarily an ingest/debug layer rather than a full analytics product.

## Next

The next committed phase is a Convex-first analytics and dashboard pass.

- Keep Convex as the system of record for now.
- Harden ingest for a few devices and moderate retry bursts with better idempotency and duplicate handling.
- Add rollup buckets and analytics read APIs for overview, time series, recent events, and CSV export.
- Add a built-in FastAPI-served dashboard instead of spinning up a separate frontend stack.
- Keep auth simple: bearer token on `/analytics/**` and `/dashboard`, just like the existing protected routes.

## Future Possible Enhancements

### Analytics and Dashboard

- richer KPI views per record type
- saved filters and presets
- longer-range rollups and comparative views
- better export paths for notebooks or BI tooling

### Write Path and Scale

- stronger event fingerprints
- background recomputation or batch rollup refresh
- queue-backed ingest if write bursts become normal
- cleaner multi-device attribution

### Automation and OpenClaw

- config-gated downstream forwarding
- summarized events instead of raw event spam
- retry tracking in `forwardAttempts`
- local automation hooks after successful persistence

### Security and Auth

- HMAC request signatures
- per-device tokens
- stricter environment-based gating for debug and dashboard routes

### Developer Experience and Operations

- better fixture generation
- load-testing harnesses for duplicate and burst scenarios
- fully Dockerized local stack
- cleaner hosted deployment story if the project moves beyond one machine

### Data Model Expansion

- richer metadata for sleep, exercise, and nutrition
- better derived metrics
- backfill/replay workflows for historical payloads

## When to Revisit Postgres

Convex self-hosted remains the default until real pressure justifies something heavier. Revisit Postgres when one or more of these become true:

- multiple users or many devices become normal
- dashboard queries need more complex joins or dimensions than rollups handle cleanly
- frequent concurrent writes become a real bottleneck
- external analytics tooling becomes a first-class requirement
- the project needs hosted deployment beyond a single-machine local setup
- operational maturity around SQL migrations, BI connectors, or database tooling becomes more valuable than the current simplicity

## Source of Truth

- `docs/architecture/` is authoritative for accepted architecture decisions.
- `README.md` explains the current implementation and how to run it.
- `ROADMAP.md` is directional. It describes likely next steps and possible future enhancements, not already-shipped behavior.
