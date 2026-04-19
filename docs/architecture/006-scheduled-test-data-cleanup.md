# ADR-006: Scheduled Cleanup for Explicitly Tagged Test Data

**Date:** 2026-04-19
**Status:** Accepted
**Deciders:** deadronos

---

## Context

The project uses realistic fixtures and `tools/mock_sender.py` to exercise the ingest pipeline locally. Those deliveries are useful during development, but once analytics and dashboards exist they can pollute totals, time series, and recent-delivery views if they remain indefinitely.

The cleanup mechanism needs to be safe:

- it must not guess aggressively and delete legitimate health data
- it must keep `healthEventBuckets` consistent with the surviving `healthEvents`
- it should run inside Convex so maintenance stays close to the source of truth

---

## Decision

Use **explicit ingest-time tagging plus scheduled Convex cleanup** for test data.

Specifically:

- classify raw deliveries as `test` or `valid` at ingest time
- treat `X-OpenClaw-Test-Data: true` and the mock-sender user agent as test-data markers
- allow `X-OpenClaw-Test-Data: false` to override the mock-sender default when fixture data should be kept
- run a daily Convex cron to delete expired `test` deliveries
- delete linked `healthEvents` and `forwardAttempts` for those deliveries
- rebuild only the affected `hour` and `day` buckets from surviving events
- record each cleanup pass in `cleanupRuns`

The initial retention window is 24 hours.

---

## Reasons

### Safety first

The cleanup job only removes explicitly tagged test data. This avoids heuristic-only deletion of valid health records.

### Keep maintenance inside Convex

The cleanup logic operates on `rawDeliveries`, `healthEvents`, and `healthEventBuckets` directly, so Convex is the right place to own the schedule and the data repair.

### Correct rollups matter

Deleting an event can invalidate bucket `min`, `max`, `latestValue`, and `latestAt`. Rebuilding affected buckets from surviving rows is safer than trying to decrement counters in place.

### Development ergonomics

Mock data should be easy to send and easy to forget. Defaulting the mock sender to test-tagged data keeps local experimentation convenient without permanently contaminating analytics.

---

## Consequences

### Positive

- fixture and mock-sender traffic can clean itself up automatically
- valid ingest data stays untouched unless it is explicitly marked as test data
- analytics buckets remain consistent after cleanup
- cleanup activity is auditable via `cleanupRuns`

### Negative

- old untagged fixture data is not retroactively identifiable by this mechanism
- Convex now owns a recurring maintenance job in addition to ingest and analytics reads
- developers must use `--keep-data` or `X-OpenClaw-Test-Data: false` when they want mock payloads to persist

---

## Notes

- cleanup is batched to keep each run modest in scope
- the current schedule runs daily at `03:00 UTC`
- the current retention window is 24 hours
- future changes to the retention policy or classification signals should update this ADR, `README.md`, and `CHANGELOG.md`
