# One Entry per Line

2026-04-19 Add phase-2 analytics/dashboard implementation plan and repo roadmap
2026-04-19 Expand canonical health events with device IDs, fingerprints, and optional metadata for analytics
2026-04-19 Make ingest idempotent with a single Convex mutation and hour/day rollup buckets
2026-04-19 Add authenticated analytics APIs and a built-in dashboard backed by Convex read queries
2026-04-19 Add API route reference documentation for current FastAPI routes and parameters
2026-04-19 Update documented dev server host to 0.0.0.0:8787 for sandboxed agent access
2026-04-18 Expand to all 17 Android Health Connect data types: steps, sleep, heart_rate, heart_rate_variability, distance, active_calories, total_calories, weight, height, oxygen_saturation, resting_heart_rate, exercise, nutrition, basal_metabolic_rate, body_fat, lean_body_mass, vo2_max; add AndroidPayload schema and AndroidPayloadNormalizer; ingest endpoint auto-detects flat vs Android payload format
2026-04-18 Fix Convex function invocation: use mutations.js:funcName paths instead of healthIngester/module/funcName; fix schema.ts setIndex->index; update checkDuplicateDelivery to scan
2026-04-18 Add Health Connect webhook ingest MVP — FastAPI server with bearer auth, Convex storage, normalizer, mock sender, fixtures, and test suite
2026-04-18 Add ADR records for database (Convex), normalizer (strict if/else), and auth (bearer token) decisions
2026-04-18 Add comprehensive README with architecture diagram, API reference, quick start guide, and project structure
2026-04-18 Add AGENTS.md with doc/code sync rules and changelog policy
