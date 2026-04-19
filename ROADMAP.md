# Roadmap

This repo exists to be a local ingest and normalization boundary between Android Health Connect payloads and everything downstream. It should accept webhook data, validate it, normalize it into a stable internal shape, store both raw and canonical records durably, and make that data easy to inspect, test, replay, and later automate against.

## Current State

- The MVP works today: FastAPI ingest, bearer-token auth, Convex-backed persistence, health/debug routes, fixtures, mock sender, and pytest coverage.
- Phase 2 is now shipped: idempotent ingest writes, fingerprinted canonical events, hour/day rollup buckets, authenticated `/analytics/**` APIs, and a built-in `/dashboard` page.
- The stack is intentionally local-first and lightweight: one Python service, one Convex backend, no queue, no separate frontend build pipeline, and no Postgres.

## Next Likely Focus

With the built-in analytics pass complete, the next work should focus on sharpening the edges rather than adding another major surface area.

- Improve device-aware analytics if per-device filtering needs dedicated rollups instead of event scans.
- Decide whether dashboard charts need richer dimensions before adding more route-specific queries.
- Keep Convex as the default until real contention or query complexity justifies migration pressure.

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
