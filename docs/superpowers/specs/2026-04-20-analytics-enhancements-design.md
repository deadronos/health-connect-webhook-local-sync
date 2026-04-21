# Analytics Enhancements Design

**Date:** 2026-04-20
**Status:** Approved for implementation

## Overview

Five new Convex queries that enrich the existing analytics layer with trend analysis, anomaly detection, period summaries, goal tracking, and correlation hints. All five read from existing tables (`healthEvents`, `healthEventBuckets`) and require only one new table (`healthGoals`). Implementation order: trend → anomaly → period summaries → goal tracking → correlation.

---

## 1. Trend Analysis

**Query:** `getTrend(recordType, fromMs, toMs)`

Compares the current time window against a prior window of equal length. For example, if querying the last 7 days, the prior window is the 7 days before that.

**Implementation:**
- Read buckets from `healthEventBuckets` filtered by `recordType`, `bucketSize=day`, `fromMs`, `toMs`.
- Compute `priorFromMs = fromMs - (toMs - fromMs)`, `priorToMs = fromMs`.
- Sum bucket values for current and prior windows.
- Compute `percentChange = (current - prior) / prior * 100` when prior > 0.

**Returns:**
```ts {
  direction: "up" | "down" | "flat",
  percentChange: number,   // NaN if prior is 0
  currentValue: number,
  priorValue: number,
  currentWindowMs: number,
  priorWindowMs: number,
}
```

**Notes:**
- `direction` is "flat" when `|percentChange| < 1`.
- Uses `sum` statistic by default (e.g., total steps, total calories).

---

## 2. Anomaly Detection

**Query:** `detectAnomalies(recordType, bucketSize, fromMs, toMs, threshold?)`

Computes mean and standard deviation of the requested statistic over the window, then flags buckets where the value exceeds `threshold` standard deviations from the mean.

**Parameters:**
- `threshold` (optional, default 2.0): Number of stddevs to consider anomalous.

**Implementation:**
- Read buckets from `healthEventBuckets` filtered by `recordType`, `bucketSize`, `fromMs`, `toMs`.
- Collect all `sum` values into an array.
- Compute `mean = sum / count`, `variance = sum((x - mean)^2) / count`, `stddev = sqrt(variance)`.
- For each bucket, compute `zScore = (bucket.sum - mean) / stddev` when stddev > 0.
- Flag bucket if `|zScore| > threshold`.

**Returns:**
```ts {
  buckets: {
    bucketStart: number,
    value: number,     // the sum for this bucket
    zScore: number,
    isAnomaly: boolean,
  }[],
  mean: number,
  stddev: number,
  anomalyCount: number,
}
```

**Notes:**
- Only flags values above the threshold, not below (relevant for metrics like heart rate where low values may also be anomalous — a future param could extend this).
- If fewer than 3 buckets exist, returns all buckets with `zScore: 0` and `isAnomaly: false`.

---

## 3. Period Summaries

**Query:** `getPeriodSummaries(recordTypes[], period, fromMs, toMs)`

Rolls up health events into day, week, or month buckets, returning per-period per-record-type aggregates.

**Parameters:**
- `recordTypes`: Array of record types to include (e.g., `["steps", "heart_rate"]`).
- `period`: `"day" | "week" | "month"`.
- `fromMs`, `toMs`: Time window.

**Implementation:**
- Read events from `healthEvents` filtered by `recordTypes`, `fromMs`, `toMs`.
- Group events by calendar period start (UTC midnight for day, Monday midnight for week, 1st-of-month midnight for month) and `recordType`.
- Compute count, sum, avg, min, max per group.

**Returns:**
```ts {
  summaries: {
    periodStart: number,   // Unix ms
    period: "day" | "week" | "month",
    recordType: string,
    count: number,
    sum: number,
    avg: number,
    min: number,
    max: number,
  }[]
}
```

**Notes:**
- Period start for `week` is the Monday of that week (UTC).
- If no events exist for a record type in a period, that record type is omitted for that period (no zero-fill).

---

## 4. Goal Tracking

**New table:** `healthGoals`
```ts defineTable({
  userId: v.string(),
  recordType: v.string(),
  targetValue: v.number(),
  targetUnit: v.string(),
  period: v.union(v.literal("day"), v.literal("week"), v.literal("month")),
  createdAt: v.number(),
  updatedAt: v.number(),
})
.index("by_user_and_record", ["userId", "recordType"])
```

**Query:** `getGoalProgress(userId, recordType?)`

If `recordType` is omitted, returns progress for all goals for that user.

**Implementation:**
- Read goal(s) from `healthGoals` by `userId` (and optionally `recordType`).
- For each goal, compute the current period's aggregate from `healthEvents` filtered by `recordType` and the current period's time range.
- Compute `percentComplete = (current / targetValue) * 100`.
- Compute `daysRemaining` based on period type (days left in current day/week/month).

**Returns:**
```ts {
  goals: {
    recordType: string,
    targetValue: number,
    targetUnit: string,
    period: "day" | "week" | "month",
    currentValue: number,
    percentComplete: number,
    daysRemaining: number,
    isOnTrack: boolean,    // true if currentValue / elapsed >= targetValue / total
    updatedAt: number,
  }[]
}
```

**Notes:**
- `isOnTrack` uses a simple linear projection: `isOnTrack = currentValue * periodTotalMs > targetValue * elapsedMs`.
- Goals are user-scoped via `userId`. The `userId` field is opaque to Convex — callers are responsible for passing the correct identity.

**Mutation:** `setHealthGoal` — inserts or updates a goal for a user.
```ts mutationGeneric({
  args: {
    userId: v.string(),
    recordType: v.string(),
    targetValue: v.number(),
    targetUnit: v.string(),
    period: v.union(v.literal("day"), v.literal("week"), v.literal("month")),
  },
  handler: async (ctx, args) => {
    // upsert via existing goal lookup + db.patch or db.insert
  }
})
```

---

## 5. Correlation Hints

**Query:** `getCorrelationHints(fromMs, toMs, recordTypes[])`

Computes Pearson correlation coefficient between each pair of record types over the given window. Surfaces pairs with moderate-to-strong correlation as "hints" for further analysis.

**Parameters:**
- `fromMs`, `toMs`: Time window.
- `recordTypes`: Array of record types to analyze (max 10, min 2).

**Implementation:**
- Read events from `healthEvents` filtered by `recordTypes`, `fromMs`, `toMs`.
- Group events by UTC day and `recordType`, computing `sum` per group per day.
- For each pair (A, B), build arrays of daily sums aligned by day (only days where both have data).
- Compute Pearson r: `r = sum((x-x̄)(y-ȳ)) / sqrt(sum((x-x̄)²) * sum((y-ȳ)²))`.
- Classify: `|r| >= 0.7` → "strong", `|r| >= 0.4` → "moderate", `|r| >= 0.2` → "weak", else "none".

**Returns:**
```ts {
  hints: {
    recordTypeA: string,
    recordTypeB: string,
    correlation: number,    // -1 to 1
    strength: "strong" | "moderate" | "weak" | "none",
    dataPointCount: number, // number of aligned days used
  }[],
  windowMs: number,
}
```

**Notes:**
- Only returns pairs with `strength !== "none"`. Pairs with no correlation are omitted to keep response small.
- Requires at least 5 aligned data points to compute a correlation; otherwise returns `strength: "none"`.
- This is a hint, not a statistical guarantee — agents should treat moderate/strong correlations as investigatory signals, not causal claims.

---

## File Structure

```
convex/healthIngester/
  queries.ts       # add: getTrend, detectAnomalies, getPeriodSummaries, getGoalProgress
  mutations.ts     # add: setHealthGoal
  goals.ts         # NEW: healthGoals table definition (or add to schema.ts)

convex/schema.ts   # add: healthGoals table
```

**Note on schema.ts:** All tables are currently defined in `convex/schema.ts`. The `healthGoals` table should be added there following the existing pattern.

---

## Implementation Order

1. **Trend Analysis** — simplest new query, establishes pattern
2. **Anomaly Detection** — similar structure, adds statistical computation
3. **Period Summaries** — builds on existing bucket logic
4. **Goal Tracking** — adds new table + upsert mutation
5. **Correlation Hints** — most complex, uses raw events, optional/last

---

## Backward Compatibility

All new queries are additive. Existing queries in `queries.ts` are unchanged. No existing mutations or table schemas are modified.

## Error Handling

- Queries that find no data return empty arrays (not errors).
- Division by zero (e.g., prior period sum = 0 in trend) returns `percentChange: null` and `direction: "flat"`.
- Correlation with insufficient data points returns `strength: "none"` and is excluded from the hints array.
