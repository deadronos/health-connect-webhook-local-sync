# One Entry per Line

2026-05-08 Improve test coverage from 84% to 98%; add tests for normalizer helpers, Android record types, ConvexClient methods, browser auth security, ingest edge cases, analytics route validation, debug endpoint, and auth session persistence
2026-04-26 Add AGENTS.md note to activate `.venv` before running pytest or VS Code test discovery
2026-04-26 Add `getCurrentPeriodBounds` and `getPeriodStart` shared utilities, deduplicating identical code in mutations.ts and queries.ts
2026-04-26 Update ADR-004 to document that analytics queries perform full event scans; note `getGoalProgress` full-scan fallback when recordType is omitted
2026-04-26 Change `app_host` default from `127.0.0.1` to `0.0.0.0` to align with README quick-start and allow sandboxed agent access to `:8787`; add regression test
2026-04-26 Add regression test for `session_https_only` property (already existed in test_config.py, move `test_convex_site_url_property` up so `test_app_host_default_is_all_interfaces` comes first)
2026-04-26 Remove hardcoded session secret and ingest token defaults for improved security
2026-04-25 Add correlation analysis endpoint `GET /analytics/correlation` with Pearson correlation between pairs of record types, powered by `getCorrelationHints` Convex query
2026-04-25 Add health goals feature: `setHealthGoal` mutation to create/update targets and `GET /analytics/goals` endpoint to fetch current progress against targets via `getGoalProgress` Convex query
2026-04-25 Add `getPeriodSummaries` Convex query for weekly/monthly aggregations and `GET /analytics/period-summaries` endpoint
2026-04-25 Add anomaly detection with `detectAnomalies` Convex query and `GET /analytics/anomalies` endpoint using z-score thresholding
2026-04-25 Add trend analysis with `getTrend` Convex query and `GET /analytics/trend/{record_type}` endpoint; include percent change and direction
2026-04-24 Add ADR-006: scheduled test-data cleanup via Convex crons that delete expired test deliveries and rebuild affected analytics buckets
2026-04-24 Add `healthGoals` table to Convex schema with `by_user_and_record` index; add `setHealthGoal` mutation for creating and updating goal targets
2026-04-24 Add ADR-005: browser session auth for dashboard using signed HttpOnly session cookies; `GET /login` form exchanges INGEST_TOKEN for session, `/dashboard` and `/analytics/**` accept session cookie alongside bearer token
2026-04-24 Add API route reference documentation `docs/architecture/api-route-reference.md` listing all current endpoints, auth expectations, query params, and response shapes
2026-04-24 Add analytics phase-2 implementation plan and repo roadmap under `docs/plans/2026-04-19-phase-2-analytics-dashboard-plan.md` and `docs/plans/2026-04-19-dashboard-figma-alignment-plan.md`
2026-04-24 Add ADR-004: analytics read model using Convex rollup buckets for hour/day aggregates with fallback to direct event scans
2026-04-19 Reinforce timing attack protection in token verification using constant-time `hmac.compare_digest`
2026-04-19 Add /login and signed browser sessions for /dashboard and /analytics/** while keeping ingest and debug routes bearer-only
2026-04-19 Add phase-2 analytics/dashboard implementation plan and repo roadmap
2026-04-19 Expand canonical health events with device IDs, fingerprints, and optional metadata for analytics
2026-04-19 Make ingest idempotent with a single Convex mutation and hour/day rollup buckets
2026-04-19 Add authenticated analytics APIs and a built-in dashboard backed by Convex read queries
2026-04-19 Add API route reference documentation for current FastAPI routes and parameters
2026-04-19 Update documented dev server host to 0.0.0.0:8787 for sandboxed agent access
2026-04-19 Fix ingest writes when local Convex indexes lag schema updates by falling back to scan-based duplicate and bucket lookups
2026-04-19 Fix analytics events and CSV export for legacy rows missing stored fingerprints
2026-04-18 Expand to all 17 Android Health Connect data types: steps, sleep, heart_rate, heart_rate_variability, distance, active_calories, total_calories, weight, height, oxygen_saturation, resting_heart_rate, exercise, nutrition, basal_metabolic_rate, body_fat, lean_body_mass, vo2_max; add AndroidPayload schema and AndroidPayloadNormalizer; ingest endpoint auto-detects flat vs Android payload format
2026-04-18 Fix Convex function invocation: use mutations.js:funcName paths instead of healthIngester/module/funcName; fix schema.ts setIndex->index; update checkDuplicateDelivery to scan
2026-04-18 Add Health Connect webhook ingest MVP — FastAPI server with bearer auth, Convex storage, normalizer, mock sender, fixtures, and test suite
2026-04-18 Add ADR records for database (Convex), normalizer (strict if/else), and auth (bearer token) decisions
2026-04-18 Add comprehensive README with architecture diagram, API reference, quick start guide, and project structure
2026-04-18 Add AGENTS.md with doc/code sync rules and changelog policy
2026-04-26 Add error handling tests for Android normalizer timestamp parsing
2026-05-03 Optimize storeHealthEvents mutation with Promise.all for concurrent database inserts
