/// <reference types="vite/client" />

import { convexTest } from "convex-test";
import { expect, test } from "vitest";

import schema from "../schema";
import { api } from "./_generated/api";

const modules = import.meta.glob([
  "./_generated/*.js",
  "./mutations.ts",
  "./queries.ts",
]);

const apiAny = api as any;

const buildRawDelivery = ({
  receivedAt,
  payloadHash,
  dataClass,
}: {
  receivedAt: number;
  payloadHash: string;
  dataClass: "valid" | "test";
}) => ({
  receivedAt,
  sourceIp: "127.0.0.1",
  userAgent: "pytest",
  payloadJson: `{"payloadHash":"${payloadHash}"}`,
  payloadHash,
  status: "completed" as const,
  recordCount: 1,
  dataClass,
  ...(dataClass === "test" ? { dataClassReason: "header:x-openclaw-test-data" } : {}),
});

const buildEvent = ({
  capturedAt,
  payloadHash,
  valueNumeric,
}: {
  capturedAt: number;
  payloadHash: string;
  valueNumeric: number;
}) => ({
  rawDeliveryId: "placeholder",
  recordType: "steps",
  valueNumeric,
  unit: "count",
  startTime: capturedAt,
  endTime: capturedAt,
  capturedAt,
  payloadHash,
  fingerprint: `fp-${payloadHash}`,
  createdAt: capturedAt,
});

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

test("getTrend returns up direction when current > prior", async () => {
  const t = convexTest(schema, modules);
  const base = Date.UTC(2024, 2, 1, 0, 0, 0, 0); // March 1
  const deliveryId = await t.mutation(apiAny.mutations.storeRawDelivery, {
    receivedAt: base,
    sourceIp: "127.0.0.1",
    payloadJson: "{}",
    payloadHash: "trend-test",
    status: "completed",
    recordCount: 2,
  });

  // Prior window: Feb 23 (7 days before March 1)
  const priorEventTime = base - 7 * 24 * 60 * 60 * 1000;
  await t.mutation(apiAny.mutations.ingestNormalizedEventsChunk, {
    rawDeliveryId: deliveryId,
    events: [
      buildEvent({ capturedAt: priorEventTime, payloadHash: "trend-a", fingerprint: "ta", valueNumeric: 1000 }),
      buildEvent({ capturedAt: priorEventTime + 60_000, payloadHash: "trend-b", fingerprint: "tb", valueNumeric: 2000 }),
    ],
  });

  // Current window: March 8 (just after the current window starts)
  const currentEventTime = base + 7 * 24 * 60 * 60 * 1000;
  await t.mutation(apiAny.mutations.ingestNormalizedEventsChunk, {
    rawDeliveryId: deliveryId,
    events: [
      buildEvent({ capturedAt: currentEventTime, payloadHash: "trend-c", fingerprint: "tc", valueNumeric: 5000 }),
    ],
  });

  const fromMs = base;
  const toMs = base + (8 * 24 * 60 * 60 * 1000) - 1;

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

test("detectAnomalies flags buckets exceeding 2 stddev", async () => {
  const t = convexTest(schema, modules);
  const base = Date.UTC(2024, 2, 1, 0, 0, 0, 0);
  const deliveryId = await t.mutation(apiAny.mutations.storeRawDelivery, {
    receivedAt: base,
    sourceIp: "127.0.0.1",
    payloadJson: "{}",
    payloadHash: "anomaly-test",
    status: "completed",
    recordCount: 6,
  });

  // 5 normal buckets of 1000 each, then one outlier of 1000000
  // With 5 normal buckets + 1 outlier, z-score limit = sqrt(5) ≈ 2.236 > 2.0
  await t.mutation(apiAny.mutations.ingestNormalizedEventsChunk, {
    rawDeliveryId: deliveryId,
    events: [
      buildEvent({ capturedAt: base, payloadHash: "an-a", fingerprint: "aa", valueNumeric: 1000 }),
      buildEvent({ capturedAt: base + 1 * 24 * 60 * 60 * 1000, payloadHash: "an-b", fingerprint: "ab", valueNumeric: 1000 }),
      buildEvent({ capturedAt: base + 2 * 24 * 60 * 60 * 1000, payloadHash: "an-c", fingerprint: "ac", valueNumeric: 1000 }),
      buildEvent({ capturedAt: base + 3 * 24 * 60 * 60 * 1000, payloadHash: "an-d", fingerprint: "ad", valueNumeric: 1000 }),
      buildEvent({ capturedAt: base + 4 * 24 * 60 * 60 * 1000, payloadHash: "an-e", fingerprint: "ae", valueNumeric: 1000 }),
      buildEvent({ capturedAt: base + 5 * 24 * 60 * 60 * 1000, payloadHash: "an-f", fingerprint: "af", valueNumeric: 1000000 }),
    ],
  });

  const fromMs = base;
  const toMs = base + (6 * 24 * 60 * 60 * 1000) - 1;

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
  expect(anomaly!.bucketStart).toBe(base + 5 * 24 * 60 * 60 * 1000);
});

test("getPeriodSummaries returns weekly rollups", async () => {
  const t = convexTest(schema, modules);
  const base = Date.UTC(2024, 2, 4, 0, 0, 0, 0); // Monday March 4
  const deliveryId = await t.mutation(apiAny.mutations.storeRawDelivery, {
    receivedAt: base,
    sourceIp: "127.0.0.1",
    payloadJson: "{}",
    payloadHash: "period-test",
    status: "completed",
    recordCount: 2,
  });

  await t.mutation(apiAny.mutations.ingestNormalizedEventsChunk, {
    rawDeliveryId: deliveryId,
    events: [
      buildEvent({ capturedAt: base, payloadHash: "p-a", fingerprint: "pa", valueNumeric: 3000 }),
      buildEvent({ capturedAt: base + 1, payloadHash: "p-b", fingerprint: "pb", valueNumeric: 4000 }),
    ],
  });

  // Week 2 (March 11)
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