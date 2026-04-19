# OpenClaw External API Smoke Test

Date: 2026-04-19

This document records the current external API route verification status for `health-connect-webhook-local-sync`.

## Verified routes

| Route | Status | Notes |
| --- | --- | --- |
| GET /healthz | ✅ 200 | `{"ok": true, "db": "ok"}` |
| GET /debug/recent | ✅ 200 | 3 deliveries, latest is 01:08 UTC today |
| GET /analytics/overview | ✅ 200 | 6 record types, all stats present |
| GET /analytics/timeseries | ✅ 200 | Returns bucket data with sum/avg/min/max |
| GET /analytics/events | ✅ 200 | Full event records with `fingerprint`, `metadata`, `device_id` fields |
| POST /ingest/health/v1 | ✅ 200 | `received_records: 1`, `stored_records: 1` |
| GET /analytics/export.csv | ✅ 200 | Proper CSV with headers + 3 rows |
| GET /dashboard | ✅ 200 | HTML dashboard loading |

## Notes

- The `/analytics/events` route now returns enriched event records with fingerprint, metadata, and device ID fields.
- All documented routes are currently passing and returning the expected response shapes.
