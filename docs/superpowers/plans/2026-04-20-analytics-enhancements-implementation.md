# Analytics Enhancements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement 5 new Convex-powered analytics queries and 1 mutation: trend analysis, anomaly detection, period summaries, goal tracking (with a new table), and correlation hints.

**Architecture:** All new queries live in `convex/healthIngester/queries.ts` using `queryGeneric`. The new `healthGoals` table is added to `convex/schema.ts`. The `setHealthGoal` mutation lives in `convex/healthIngester/mutations.ts`. The Python `ConvexClient` in `app/convex_client.py` gains new methods for all 6 new API surface items. Tests use `convex-test` + vitest.

**Tech Stack:** TypeScript (Convex), vitest, Python (FastAPI app + pytest)

---

## Files

- **Modify:** `convex/schema.ts` — add `healthGoals` table
- **Modify:** `convex/healthIngester/mutations.ts` — add `setHealthGoal` mutation
- **Modify:** `convex/healthIngester/queries.ts` — add all 5 queries
- **Modify:** `app/convex_client.py` — add 6 new client methods
- **Create:** `convex/healthIngester/queries.test.ts` — vitest tests for all 5 queries

---

## Task 1: Add healthGoals Table to schema.ts

**Files:**
- Modify: `convex/schema.ts:97` (after the `cleanupRuns` table definition)

- [ ] **Step 1: Add healthGoals table definition**

Insert this after the `cleanupRuns` table definition (before the closing `});` of `defineSchema`):

```typescript
  healthGoals: defineTable({
    userId: v.string(),
    recordType: v.string(),
    targetValue: v.number(),
    targetUnit: v.string(),
    period: v.union(v.literal("day"), v.literal("week"), v.literal("month")),
    createdAt: v.number(),
    updatedAt: v.number(),
  }).index("by_user_and_record", ["userId", "recordType"]),
```

- [ ] **Step 2: Verify schema is valid**

Run: `cd convex && npx convex codegen`
Expected: Generates `_generated/` files without error

- [ ] **Step 3: Commit**

```bash
git add convex/schema.ts
git commit -m "feat(schema): add healthGoals table for goal tracking

Adds healthGoals table with userId, recordType, targetValue, targetUnit,
period (day/week/month), and by_user_and_record index.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 2: Add setHealthGoal Mutation

**Files:**
- Modify: `convex/healthIngester/mutations.ts`

- [ ] **Step 1: Write failing test for setHealthGoal**

Add to `convex/healthIngester/queries.test.ts` (create if needed):

```typescript
test("setHealthGoal creates a new goal and getGoalProgress returns it", async () => {
  const t = convexTest(schema, modules);
  const userId = "user-123";

  await t.mutation(apiAny.mutations.setHealthGoal, {
    userId,
    recordType: "steps",
    targetValue: 10000,
    targetUnit: "count",
    period: "day",
  });

  const goals = await t.query(apiAny.queries.getGoalProgress, { userId });
  expect(goals.goals).toHaveLength(1);
  expect(goals.goals[0].recordType).toBe("steps");
  expect(goals.goals[0].targetValue).toBe(10000);
  expect(goals.goals[0].period).toBe("day");
});
```

Run: `cd convex && npx vitest run healthIngester/queries.test.ts`
Expected: FAIL — `setHealthGoal` and `getGoalProgress` not defined

- [ ] **Step 2: Write setHealthGoal mutation**

Add to the end of `convex/healthIngester/mutations.ts`:

```typescript
export const setHealthGoal = mutationGeneric({
  args: {
    userId: v.string(),
    recordType: v.string(),
    targetValue: v.number(),
    targetUnit: v.string(),
    period: v.union(v.literal("day"), v.literal("week"), v.literal("month")),
  },
  handler: async (ctx, args) => {
    const now = Date.now();
    const existing = await ctx.db
      .query("healthGoals")
      .withIndex("by_user_and_record", (q) =>
        q.eq("userId", args.userId).eq("recordType", args.recordType)
      )
      .first();

    if (existing) {
      await ctx.db.patch(existing._id, {
        targetValue: args.targetValue,
        targetUnit: args.targetUnit,
        period: args.period,
        updatedAt: now,
      });
      return existing._id;
    }

    return await ctx.db.insert("healthGoals", {
      userId: args.userId,
      recordType: args.recordType,
      targetValue: args.targetValue,
      targetUnit: args.targetUnit,
      period: args.period,
      createdAt: now,
      updatedAt: now,
    });
  },
});
```

- [ ] **Step 3: Run test to verify it passes**

Run: `cd convex && npx vitest run healthIngester/queries.test.ts`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add convex/healthIngester/mutations.ts convex/healthIngester/queries.test.ts
git commit -m "feat(convex): add setHealthGoal mutation with upsert logic

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 3: Add getTrend Query

**Files:**
- Modify: `convex/healthIngester/queries.ts`

- [ ] **Step 1: Write failing test for getTrend**

Add to `convex/healthIngester/queries.test.ts`:

```typescript
test("getTrend returns up direction when current > prior", async () => {
  const t = convexTest(schema, modules);
  const base = Date.UTC(2024, 2, 1, 0, 0, 0, 0);
  const deliveryId = await t.mutation(apiAny.mutations.storeRawDelivery, {
    receivedAt: base,
    sourceIp: "127.0.0.1",
    payloadJson: "{}",
    payloadHash: "trend-test",
    status: "completed",
    recordCount: 2,
  });

  await t.mutation(apiAny.mutations.ingestNormalizedEventsChunk, {
    rawDeliveryId: deliveryId,
    events: [
      buildEvent({ capturedAt: base, payloadHash: "trend-a", fingerprint: "ta", valueNumeric: 1000 }),
      buildEvent({ capturedAt: base + 60_000, payloadHash: "trend-b", fingerprint: "tb", valueNumeric: 2000 }),
    ],
  });

  await t.mutation(apiAny.mutations.ingestNormalizedEventsChunk, {
    rawDeliveryId: deliveryId,
    events: [
      buildEvent({ capturedAt: base + 7 * 24 * 60 * 60 * 1000, payloadHash: "trend-c", fingerprint: "tc", valueNumeric: 5000 }),
    ],
  });

  const fromMs = base;
  const toMs = base + (7 * 24 * 60 * 60 * 1000) - 1;

  const trend = await t.query(apiAny.queries.getTrend, {
    recordType: "steps",
    fromMs,
    toMs,
  });

  expect(trend.direction).toBe("up");
  expect(trend.currentValue).toBe(5000);
  expect(trend.priorValue).toBe(3000);
  expect(trend.percentChange).toBeCloseTo(66.67, 1);
});
```

Run: `cd convex && npx vitest run healthIngester/queries.test.ts`
Expected: FAIL — `getTrend` not defined

- [ ] **Step 2: Write getTrend query**

Add to `convex/healthIngester/queries.ts`. Place it after `checkDbHealth` at the end of the file:

```typescript
export const getTrend = queryGeneric({
  args: {
    recordType: v.string(),
    fromMs: v.optional(v.number()),
    toMs: v.optional(v.number()),
  },
  handler: async (ctx, args) => {
    const nowMs = Date.now();
    const fromMs = args.fromMs ?? nowMs - (7 * 24 * 60 * 60 * 1000);
    const toMs = args.toMs ?? nowMs;
    const windowMs = toMs - fromMs;
    const priorFromMs = fromMs - windowMs;
    const priorToMs = fromMs;

    const currentBuckets = await ctx.db
      .query("healthEventBuckets")
      .withIndex("by_bucket", (q) =>
        q.eq("bucketSize", "day").eq("recordType", args.recordType)
      )
      .collect();

    const filteredCurrent = currentBuckets.filter(
      (b) => b.bucketStart >= fromMs && b.bucketStart <= toMs
    );
    const filteredPrior = currentBuckets.filter(
      (b) => b.bucketStart >= priorFromMs && b.bucketStart < priorToMs
    );

    const currentValue = filteredCurrent.reduce((sum, b) => sum + b.sum, 0);
    const priorValue = filteredPrior.reduce((sum, b) => sum + b.sum, 0);

    let percentChange: number | null = null;
    let direction: "up" | "down" | "flat" = "flat";

    if (priorValue > 0) {
      percentChange = ((currentValue - priorValue) / priorValue) * 100;
      if (Math.abs(percentChange) < 1) {
        direction = "flat";
      } else {
        direction = percentChange > 0 ? "up" : "down";
      }
    }

    return {
      direction,
      percentChange,
      currentValue,
      priorValue,
      currentWindowMs: windowMs,
      priorWindowMs: windowMs,
    };
  },
});
```

- [ ] **Step 3: Run test to verify it passes**

Run: `cd convex && npx vitest run healthIngester/queries.test.ts`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add convex/healthIngester/queries.ts
git commit -m "feat(convex): add getTrend query for period-over-period comparison

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 4: Add detectAnomalies Query

**Files:**
- Modify: `convex/healthIngester/queries.ts`

- [ ] **Step 1: Write failing test for detectAnomalies**

Add to `convex/healthIngester/queries.test.ts`:

```typescript
test("detectAnomalies flags buckets exceeding 2 stddev", async () => {
  const t = convexTest(schema, modules);
  const base = Date.UTC(2024, 2, 1, 0, 0, 0, 0);
  const deliveryId = await t.mutation(apiAny.mutations.storeRawDelivery, {
    receivedAt: base,
    sourceIp: "127.0.0.1",
    payloadJson: "{}",
    payloadHash: "anomaly-test",
    status: "completed",
    recordCount: 4,
  });

  // 3 normal buckets of 1000 each, then one outlier of 10000
  await t.mutation(apiAny.mutations.ingestNormalizedEventsChunk, {
    rawDeliveryId: deliveryId,
    events: [
      buildEvent({ capturedAt: base, payloadHash: "an-a", fingerprint: "aa", valueNumeric: 1000 }),
      buildEvent({ capturedAt: base + 24 * 60 * 60 * 1000, payloadHash: "an-b", fingerprint: "ab", valueNumeric: 1000 }),
      buildEvent({ capturedAt: base + 2 * 24 * 60 * 60 * 1000, payloadHash: "an-c", fingerprint: "ac", valueNumeric: 1000 }),
      buildEvent({ capturedAt: base + 3 * 24 * 60 * 60 * 1000, payloadHash: "an-d", fingerprint: "ad", valueNumeric: 10000 }),
    ],
  });

  const fromMs = base;
  const toMs = base + (4 * 24 * 60 * 60 * 1000) - 1;

  const result = await t.query(apiAny.queries.detectAnomalies, {
    recordType: "steps",
    bucketSize: "day",
    fromMs,
    toMs,
    threshold: 2.0,
  });

  expect(result.anomalyCount).toBe(1);
  const anomaly = result.buckets.find((b: any) => b.isAnomaly);
  expect(anomaly).toBeDefined();
  expect(anomaly!.bucketStart).toBe(base + 3 * 24 * 60 * 60 * 1000);
});
```

Run: `cd convex && npx vitest run healthIngester/queries.test.ts`
Expected: FAIL — `detectAnomalies` not defined

- [ ] **Step 2: Write detectAnomalies query**

Add to `convex/healthIngester/queries.ts` after `getTrend`:

```typescript
export const detectAnomalies = queryGeneric({
  args: {
    recordType: v.string(),
    bucketSize: v.union(v.literal("hour"), v.literal("day")),
    fromMs: v.optional(v.number()),
    toMs: v.optional(v.number()),
    threshold: v.optional(v.number()),
  },
  handler: async (ctx, args) => {
    const nowMs = Date.now();
    const fromMs = args.fromMs ?? nowMs - (7 * 24 * 60 * 60 * 1000);
    const toMs = args.toMs ?? nowMs;
    const threshold = args.threshold ?? 2.0;

    const buckets = await ctx.db
      .query("healthEventBuckets")
      .withIndex("by_bucket", (q) =>
        q.eq("bucketSize", args.bucketSize).eq("recordType", args.recordType)
      )
      .collect();

    const filtered = buckets.filter(
      (b) => b.bucketStart >= fromMs && b.bucketStart <= toMs
    );

    if (filtered.length < 3) {
      return {
        buckets: filtered.map((b) => ({
          bucketStart: b.bucketStart,
          value: b.sum,
          zScore: 0,
          isAnomaly: false,
        })),
        mean: 0,
        stddev: 0,
        anomalyCount: 0,
      };
    }

    const values = filtered.map((b) => b.sum);
    const mean = values.reduce((s, v) => s + v, 0) / values.length;
    const variance = values.reduce((s, v) => s + (v - mean) ** 2, 0) / values.length;
    const stddev = Math.sqrt(variance);

    const bucketsWithScore = filtered.map((b) => {
      const zScore = stddev > 0 ? (b.sum - mean) / stddev : 0;
      return {
        bucketStart: b.bucketStart,
        value: b.sum,
        zScore,
        isAnomaly: Math.abs(zScore) > threshold,
      };
    });

    return {
      buckets: bucketsWithScore,
      mean,
      stddev,
      anomalyCount: bucketsWithScore.filter((b) => b.isAnomaly).length,
    };
  },
});
```

- [ ] **Step 3: Run test to verify it passes**

Run: `cd convex && npx vitest run healthIngester/queries.test.ts`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add convex/healthIngester/queries.ts
git commit -m "feat(convex): add detectAnomalies query with z-score flagging

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 5: Add getPeriodSummaries Query

**Files:**
- Modify: `convex/healthIngester/queries.ts`

- [ ] **Step 1: Write failing test for getPeriodSummaries**

Add to `convex/healthIngester/queries.test.ts`:

```typescript
test("getPeriodSummaries returns weekly rollups for two record types", async () => {
  const t = convexTest(schema, modules);
  const base = Date.UTC(2024, 2, 4, 0, 0, 0, 0); // Monday
  const deliveryId = await t.mutation(apiAny.mutations.storeRawDelivery, {
    receivedAt: base,
    sourceIp: "127.0.0.1",
    payloadJson: "{}",
    payloadHash: "period-test",
    status: "completed",
    recordCount: 4,
  });

  await t.mutation(apiAny.mutations.ingestNormalizedEventsChunk, {
    rawDeliveryId: deliveryId,
    events: [
      buildEvent({ capturedAt: base, payloadHash: "p-a", fingerprint: "pa", valueNumeric: 3000 }),
      buildEvent({ capturedAt: base + 1, payloadHash: "p-b", fingerprint: "pb", valueNumeric: 4000 }),
    ],
  });

  // Week 2
  const week2 = base + 7 * 24 * 60 * 60 * 1000;
  await t.mutation(apiAny.mutations.ingestNormalizedEventsChunk, {
    rawDeliveryId: deliveryId,
    events: [
      buildEvent({ capturedAt: week2, payloadHash: "p-c", fingerprint: "pc", valueNumeric: 5000 }),
    ],
  });

  const fromMs = base;
  const toMs = week2 + (7 * 24 * 60 * 60 * 1000) - 1;

  const result = await t.query(apiAny.queries.getPeriodSummaries, {
    recordTypes: ["steps"],
    period: "week",
    fromMs,
    toMs,
  });

  expect(result.summaries).toHaveLength(2);
  const week1 = result.summaries.find((s: any) => s.periodStart === base);
  expect(week1!.sum).toBe(7000);
  expect(week1!.count).toBe(2);
  expect(week1!.period).toBe("week");
});
```

Run: `cd convex && npx vitest run healthIngester/queries.test.ts`
Expected: FAIL — `getPeriodSummaries` not defined

- [ ] **Step 2: Write getPeriodSummaries query**

Add to `convex/healthIngester/queries.ts` after `detectAnomalies`. Uses helper functions `getPeriodStart` defined at the top of the handler or as module-level helpers:

```typescript
const getPeriodStart = (timestamp: number, period: "day" | "week" | "month"): number => {
  const date = new Date(timestamp);
  if (period === "day") {
    date.setUTCHours(0, 0, 0, 0);
    return date.getTime();
  }
  if (period === "week") {
    const day = date.getUTCDay();
    const diff = day === 0 ? -6 : 1 - day; // Monday
    date.setUTCDate(date.getUTCDate() + diff);
    date.setUTCHours(0, 0, 0, 0);
    return date.getTime();
  }
  // month
  date.setUTCDate(1);
  date.setUTCHours(0, 0, 0, 0);
  return date.getTime();
};

export const getPeriodSummaries = queryGeneric({
  args: {
    recordTypes: v.array(v.string()),
    period: v.union(v.literal("day"), v.literal("week"), v.literal("month")),
    fromMs: v.optional(v.number()),
    toMs: v.optional(v.number()),
  },
  handler: async (ctx, args) => {
    const nowMs = Date.now();
    const fromMs = args.fromMs ?? nowMs - (30 * 24 * 60 * 60 * 1000);
    const toMs = args.toMs ?? nowMs;

    const events = await ctx.db.query("healthEvents").collect();
    const filtered = events.filter(
      (e) =>
        args.recordTypes.includes(e.recordType) &&
        e.capturedAt >= fromMs &&
        e.capturedAt <= toMs
    );

    const groups = new Map<string, { count: number; sum: number; min: number; max: number }>();

    for (const event of filtered) {
      const periodStart = getPeriodStart(event.capturedAt, args.period);
      const key = `${periodStart}:${event.recordType}`;
      const existing = groups.get(key);
      if (existing) {
        existing.count += 1;
        existing.sum += event.valueNumeric;
        existing.min = Math.min(existing.min, event.valueNumeric);
        existing.max = Math.max(existing.max, event.valueNumeric);
      } else {
        groups.set(key, {
          count: 1,
          sum: event.valueNumeric,
          min: event.valueNumeric,
          max: event.valueNumeric,
        });
      }
    }

    const summaries = Array.from(groups.entries()).map(([key, agg]) => {
      const [periodStartStr, recordType] = key.split(":");
      const periodStart = Number(periodStartStr);
      return {
        periodStart,
        period: args.period,
        recordType,
        count: agg.count,
        sum: agg.sum,
        avg: agg.sum / agg.count,
        min: agg.min,
        max: agg.max,
      };
    });

    return { summaries: summaries.sort((a, b) => a.periodStart - b.periodStart) };
  },
});
```

- [ ] **Step 3: Run test to verify it passes**

Run: `cd convex && npx vitest run healthIngester/queries.test.ts`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add convex/healthIngester/queries.ts
git commit -m "feat(convex): add getPeriodSummaries query for day/week/month rollups

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 6: Add getGoalProgress Query

**Files:**
- Modify: `convex/healthIngester/queries.ts`

- [ ] **Step 1: Write failing test for getGoalProgress**

The test was already added in Task 2 step 1. Run it to confirm it fails because `getGoalProgress` is not yet defined.

Run: `cd convex && npx vitest run healthIngester/queries.test.ts`
Expected: FAIL — `getGoalProgress` not defined

- [ ] **Step 2: Write getGoalProgress query**

Add to `convex/healthIngester/queries.ts` after `getPeriodSummaries`:

```typescript
export const getGoalProgress = queryGeneric({
  args: {
    userId: v.string(),
    recordType: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const nowMs = Date.now();
    const goalsQuery = ctx.db.query("healthGoals");
    let goals;
    if (args.recordType) {
      goals = await goalsQuery
        .withIndex("by_user_and_record", (q) =>
          q.eq("userId", args.userId).eq("recordType", args.recordType)
        )
        .collect();
    } else {
      goals = await goalsQuery.collect();
      goals = goals.filter((g) => g.userId === args.userId);
    }

    const result = [];

    for (const goal of goals) {
      const { periodStart, periodEnd } = getCurrentPeriodBounds(goal.period, nowMs);
      const events = await ctx.db.query("healthEvents").collect();
      const periodEvents = events.filter(
        (e) =>
          e.recordType === goal.recordType &&
          e.capturedAt >= periodStart &&
          e.capturedAt < periodEnd
      );
      const currentValue = periodEvents.reduce((s, e) => s + e.valueNumeric, 0);
      const elapsedMs = nowMs - periodStart;
      const periodTotalMs = periodEnd - periodStart;
      const percentComplete = (currentValue / goal.targetValue) * 100;
      const daysRemaining = Math.ceil((periodEnd - nowMs) / (24 * 60 * 60 * 1000));
      const isOnTrack = currentValue * periodTotalMs >= goal.targetValue * elapsedMs;

      result.push({
        recordType: goal.recordType,
        targetValue: goal.targetValue,
        targetUnit: goal.targetUnit,
        period: goal.period,
        currentValue,
        percentComplete,
        daysRemaining: Math.max(0, daysRemaining),
        isOnTrack,
        updatedAt: goal.updatedAt,
      });
    }

    return { goals: result };
  },
});

const getCurrentPeriodBounds = (
  period: "day" | "week" | "month",
  nowMs: number
): { periodStart: number; periodEnd: number } => {
  const now = new Date(nowMs);
  if (period === "day") {
    const start = new Date(now);
    start.setUTCHours(0, 0, 0, 0);
    const end = new Date(start);
    end.setUTCDate(end.getUTCDate() + 1);
    return { periodStart: start.getTime(), periodEnd: end.getTime() };
  }
  if (period === "week") {
    const start = new Date(now);
    const day = start.getUTCDay();
    const diff = day === 0 ? -6 : 1 - day;
    start.setUTCDate(start.getUTCDate() + diff);
    start.setUTCHours(0, 0, 0, 0);
    const end = new Date(start);
    end.setUTCDate(end.getUTCDate() + 7);
    return { periodStart: start.getTime(), periodEnd: end.getTime() };
  }
  // month
  const start = new Date(now.getUTCFullYear(), now.getUTCMonth(), 1);
  const end = new Date(now.getUTCFullYear(), now.getUTCMonth() + 1, 1);
  return { periodStart: start.getTime(), periodEnd: end.getTime() };
};
```

- [ ] **Step 3: Run test to verify it passes**

Run: `cd convex && npx vitest run healthIngester/queries.test.ts`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add convex/healthIngester/queries.ts
git commit -m "feat(convex): add getGoalProgress query with isOnTrack calculation

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 7: Add getCorrelationHints Query

**Files:**
- Modify: `convex/healthIngester/queries.ts`

- [ ] **Step 1: Write failing test for getCorrelationHints**

Add to `convex/healthIngester/queries.test.ts`:

```typescript
test("getCorrelationHints returns strong positive correlation between two record types", async () => {
  const t = convexTest(schema, modules);
  const base = Date.UTC(2024, 2, 1, 12, 0, 0, 0);

  const d1 = await t.mutation(apiAny.mutations.storeRawDelivery, {
    receivedAt: base, sourceIp: "127.0.0.1", payloadJson: "{}",
    payloadHash: "corr-test", status: "completed", recordCount: 2,
  });

  const makeEvent = (day: number, type: string, val: number, fp: string) => ({
    rawDeliveryId: d1,
    recordType: type,
    valueNumeric: val,
    unit: type === "heart_rate" ? "bpm" : "count",
    startTime: base + day * 24 * 60 * 60 * 1000,
    endTime: base + day * 24 * 60 * 60 * 1000,
    capturedAt: base + day * 24 * 60 * 60 * 1000,
    payloadHash: `ph-${fp}`,
    fingerprint: fp,
    createdAt: base,
  });

  await t.mutation(apiAny.mutations.ingestNormalizedEventsChunk, {
    rawDeliveryId: d1,
    events: [
      makeEvent(0, "steps", 5000, "s0"),
      makeEvent(0, "active_calories", 500, "c0"),
      makeEvent(1, "steps", 7000, "s1"),
      makeEvent(1, "active_calories", 700, "c1"),
      makeEvent(2, "steps", 9000, "s2"),
      makeEvent(2, "active_calories", 900, "c2"),
      makeEvent(3, "steps", 6000, "s3"),
      makeEvent(3, "active_calories", 600, "c3"),
      makeEvent(4, "steps", 8000, "s4"),
      makeEvent(4, "active_calories", 800, "c4"),
    ],
  });

  const fromMs = base;
  const toMs = base + (5 * 24 * 60 * 60 * 1000) - 1;

  const result = await t.query(apiAny.queries.getCorrelationHints, {
    fromMs,
    toMs,
    recordTypes: ["steps", "active_calories"],
  });

  const pair = result.hints.find(
    (h: any) =>
      (h.recordTypeA === "steps" && h.recordTypeB === "active_calories") ||
      (h.recordTypeA === "active_calories" && h.recordTypeB === "steps")
  );
  expect(pair).toBeDefined();
  expect(pair!.strength).toBe("strong");
  expect(pair!.correlation).toBeGreaterThan(0.9);
});
```

Run: `cd convex && npx vitest run healthIngester/queries.test.ts`
Expected: FAIL — `getCorrelationHints` not defined

- [ ] **Step 2: Write getCorrelationHints query**

Add to `convex/healthIngester/queries.ts` after `getGoalProgress`. Uses the same `getPeriodStart` helper from Task 5 with period `"day"`:

```typescript
export const getCorrelationHints = queryGeneric({
  args: {
    fromMs: v.optional(v.number()),
    toMs: v.optional(v.number()),
    recordTypes: v.array(v.string()),
  },
  handler: async (ctx, args) => {
    const nowMs = Date.now();
    const fromMs = args.fromMs ?? nowMs - (30 * 24 * 60 * 60 * 1000);
    const toMs = args.toMs ?? nowMs;

    if (args.recordTypes.length < 2 || args.recordTypes.length > 10) {
      throw new Error("recordTypes must have between 2 and 10 elements");
    }

    const events = await ctx.db.query("healthEvents").collect();
    const filtered = events.filter(
      (e) =>
        args.recordTypes.includes(e.recordType) &&
        e.capturedAt >= fromMs &&
        e.capturedAt <= toMs
    );

    // Build daily sums per record type
    const dailySums = new Map<string, Map<number, number>>(); // recordType -> dayStart -> sum
    for (const event of filtered) {
      const dayStart = getPeriodStart(event.capturedAt, "day");
      if (!dailySums.has(event.recordType)) {
        dailySums.set(event.recordType, new Map());
      }
      const dayMap = dailySums.get(event.recordType)!;
      dayMap.set(dayStart, (dayMap.get(dayStart) ?? 0) + event.valueNumeric);
    }

    const hints = [];
    for (let i = 0; i < args.recordTypes.length; i++) {
      for (let j = i + 1; j < args.recordTypes.length; j++) {
        const typeA = args.recordTypes[i];
        const typeB = args.recordTypes[j];
        const mapA = dailySums.get(typeA);
        const mapB = dailySums.get(typeB);

        if (!mapA || !mapB) continue;

        // Align by day
        const aligned: [number, number][] = [];
        for (const [day, valA] of mapA) {
          const valB = mapB.get(day);
          if (valB !== undefined) {
            aligned.push([valA, valB]);
          }
        }

        if (aligned.length < 5) {
          hints.push({
            recordTypeA: typeA,
            recordTypeB: typeB,
            correlation: 0,
            strength: "none",
            dataPointCount: aligned.length,
          });
          continue;
        }

        const n = aligned.length;
        const sumX = aligned.reduce((s, [x]) => s + x, 0);
        const sumY = aligned.reduce((s, [, y]) => s + y, 0);
        const meanX = sumX / n;
        const meanY = sumY / n;
        const num = aligned.reduce((s, [x, y]) => s + (x - meanX) * (y - meanY), 0);
        const denX = aligned.reduce((s, [x]) => s + (x - meanX) ** 2, 0);
        const denY = aligned.reduce((s, [, y]) => s + (y - meanY) ** 2, 0);
        const den = Math.sqrt(denX * denY);
        const r = den === 0 ? 0 : num / den;
        const absR = Math.abs(r);
        const strength =
          absR >= 0.7 ? "strong" : absR >= 0.4 ? "moderate" : absR >= 0.2 ? "weak" : "none";

        hints.push({
          recordTypeA: typeA,
          recordTypeB: typeB,
          correlation: r,
          strength,
          dataPointCount: n,
        });
      }
    }

    return {
      hints: hints.filter((h) => h.strength !== "none"),
      windowMs: toMs - fromMs,
    };
  },
});
```

- [ ] **Step 3: Run test to verify it passes**

Run: `cd convex && npx vitest run healthIngester/queries.test.ts`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add convex/healthIngester/queries.ts
git commit -m "feat(convex): add getCorrelationHints query with Pearson r computation

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 8: Add Python ConvexClient Methods

**Files:**
- Modify: `app/convex_client.py`

- [ ] **Step 1: Add 6 new methods to ConvexClient**

Add these methods to the `ConvexClient` class in `app/convex_client.py`:

```python
def get_trend(self, record_type: str, from_ms: int | None = None, to_ms: int | None = None) -> dict:
    """Fetch trend analysis for a record type.

    Args:
        record_type: Type of health record (e.g., "steps").
        from_ms: Start of current window in Unix ms.
        to_ms: End of current window in Unix ms.

    Returns:
        dict with direction, percentChange, currentValue, priorValue.
    """
    try:
        result = self._client.query("queries.js:getTrend", self._conv_to_json({
            "recordType": record_type,
            "fromMs": from_ms,
            "toMs": to_ms,
        }))
        return result if isinstance(result, dict) else {}
    except ConvexError as e:
        raise Exception(f"Convex error: {e}") from e

def detect_anomalies(
    self,
    record_type: str,
    bucket_size: str,
    from_ms: int | None = None,
    to_ms: int | None = None,
    threshold: float | None = None,
) -> dict:
    """Detect anomalous buckets for a record type.

    Args:
        record_type: Type of health record.
        bucket_size: "hour" or "day".
        from_ms: Start of window in Unix ms.
        to_ms: End of window in Unix ms.
        threshold: Number of stddevs to flag (default 2.0).

    Returns:
        dict with buckets, mean, stddev, anomalyCount.
    """
    try:
        result = self._client.query("queries.js:detectAnomalies", self._conv_to_json({
            "recordType": record_type,
            "bucketSize": bucket_size,
            "fromMs": from_ms,
            "toMs": to_ms,
            "threshold": threshold,
        }))
        return result if isinstance(result, dict) else {}
    except ConvexError as e:
        raise Exception(f"Convex error: {e}") from e

def get_period_summaries(
    self,
    record_types: list[str],
    period: str,
    from_ms: int | None = None,
    to_ms: int | None = None,
) -> dict:
    """Fetch period summaries for multiple record types.

    Args:
        record_types: List of record types to include.
        period: "day", "week", or "month".
        from_ms: Start of window in Unix ms.
        to_ms: End of window in Unix ms.

    Returns:
        dict with summaries array.
    """
    try:
        result = self._client.query("queries.js:getPeriodSummaries", self._conv_to_json({
            "recordTypes": record_types,
            "period": period,
            "fromMs": from_ms,
            "toMs": to_ms,
        }))
        return result if isinstance(result, dict) else {}
    except ConvexError as e:
        raise Exception(f"Convex error: {e}") from e

def get_goal_progress(self, user_id: str, record_type: str | None = None) -> dict:
    """Fetch goal progress for a user.

    Args:
        user_id: User identifier.
        record_type: Optional specific record type (omit for all goals).

    Returns:
        dict with goals array.
    """
    try:
        result = self._client.query("queries.js:getGoalProgress", self._conv_to_json({
            "userId": user_id,
            "recordType": record_type,
        }))
        return result if isinstance(result, dict) else {}
    except ConvexError as e:
        raise Exception(f"Convex error: {e}") from e

def set_health_goal(
    self,
    user_id: str,
    record_type: str,
    target_value: float,
    target_unit: str,
    period: str,
) -> str:
    """Create or update a health goal.

    Args:
        user_id: User identifier.
        record_type: Type of health record.
        target_value: Target value to reach.
        target_unit: Unit of the target.
        period: "day", "week", or "month".

    Returns:
        Goal ID string.
    """
    try:
        result = self._client.mutation("mutations.js:setHealthGoal", self._conv_to_json({
            "userId": user_id,
            "recordType": record_type,
            "targetValue": target_value,
            "targetUnit": target_unit,
            "period": period,
        }))
        return str(result) if result else ""
    except ConvexError as e:
        raise Exception(f"Convex error: {e}") from e

def get_correlation_hints(
    self,
    record_types: list[str],
    from_ms: int | None = None,
    to_ms: int | None = None,
) -> dict:
    """Fetch correlation hints between record type pairs.

    Args:
        record_types: List of 2-10 record types to correlate.
        from_ms: Start of window in Unix ms.
        to_ms: End of window in Unix ms.

    Returns:
        dict with hints array and windowMs.
    """
    try:
        result = self._client.query("queries.js:getCorrelationHints", self._conv_to_json({
            "recordTypes": record_types,
            "fromMs": from_ms,
            "toMs": to_ms,
        }))
        return result if isinstance(result, dict) else {}
    except ConvexError as e:
        raise Exception(f"Convex error: {e}") from e
```

- [ ] **Step 2: Run Python tests**

Run: `cd /Users/openclaw/Github/health-connect-webhook-local-sync && python -m pytest tests/test_convex_client.py -v`
Expected: PASS (existing tests) + no new failures

- [ ] **Step 3: Commit**

```bash
git add app/convex_client.py
git commit -m "feat(client): add 6 new ConvexClient methods for analytics enhancements

Adds get_trend, detect_anomalies, get_period_summaries, get_goal_progress,
set_health_goal, and get_correlation_hints.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Spec Coverage Checklist

| Spec Requirement | Task |
|---|---|
| `healthGoals` table with `by_user_and_record` index | Task 1 |
| `setHealthGoal` mutation with upsert | Task 2 |
| `getTrend` — direction, percentChange, current/prior values | Task 3 |
| `detectAnomalies` — z-score, threshold, mean, stddev, anomalyCount | Task 4 |
| `getPeriodSummaries` — day/week/month rollups per record type | Task 5 |
| `getGoalProgress` — current vs target, pctComplete, daysRemaining, isOnTrack | Task 6 |
| `getCorrelationHints` — Pearson r, strength classification, min 5 data points | Task 7 |
| Python `ConvexClient` methods for all 6 new API surface items | Task 8 |

## Type Consistency Check

- `recordType` (singular) used in all queries/mutations — consistent
- `fromMs`/`toMs` optional with defaults — consistent across all queries
- `bucketSize` union type `"hour" | "day"` — consistent with existing schema
- `period` union type `"day" | "week" | "month"` — consistent
- `userId` string — consistent across `healthGoals` and `setHealthGoal`/`getGoalProgress`
- All return types match spec: `direction` enum, `strength` enum, `percentComplete` as number
