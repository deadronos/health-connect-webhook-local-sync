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