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