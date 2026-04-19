/// <reference types="vite/client" />

import { convexTest } from "convex-test";
import { expect, test } from "vitest";

import schema from "../schema";
import { api, internal } from "./_generated/api";
import { DEFAULT_TEST_DATA_RETENTION_MS } from "./cleanup";

const modules = import.meta.glob([
  "./_generated/*.js",
  "./cleanup.ts",
  "./mutations.ts",
  "./queries.ts",
]);

const apiAny = api as any;
const internalAny = internal as any;

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
  status: "stored" as const,
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

test("dry run cleanup reports candidates without deleting data", async () => {
  const t = convexTest(schema, modules);
  const receivedAt = 1710800000000;
  const nowMs = receivedAt + DEFAULT_TEST_DATA_RETENTION_MS + 60_000;

  await t.mutation(apiAny.mutations.ingestNormalizedDelivery, {
    rawDelivery: buildRawDelivery({ receivedAt, payloadHash: "dry-run", dataClass: "test" }),
    events: [buildEvent({ capturedAt: receivedAt, payloadHash: "dry-run", valueNumeric: 1000 })],
  });

  const result = await t.mutation(internalAny.cleanup.runScheduledTestDataCleanup, {
    nowMs,
    retentionMs: DEFAULT_TEST_DATA_RETENTION_MS,
    batchSize: 10,
    dryRun: true,
  });

  expect(result.mode).toBe("dry_run");
  expect(result.candidateDeliveryCount).toBe(1);
  expect(result.deletedDeliveryCount).toBe(0);
  expect(result.deletedEventCount).toBe(0);

  const deliveries = await t.query(apiAny.queries.listRecentDeliveries, { limit: 10 });
  expect(deliveries).toHaveLength(1);

  const runs = await t.query(internalAny.cleanup.listCleanupRuns, { limit: 1 });
  expect(runs[0].mode).toBe("dry_run");
  expect(runs[0].candidateEventCount).toBe(1);
});

test("scheduled cleanup deletes only old tagged test data and rebuilds buckets", async () => {
  const t = convexTest(schema, modules);
  const oldReceivedAt = 1710800000000;
  const recentReceivedAt = oldReceivedAt + DEFAULT_TEST_DATA_RETENTION_MS - 1;
  const nowMs = oldReceivedAt + DEFAULT_TEST_DATA_RETENTION_MS + 60_000;
  const bucketStart = new Date(oldReceivedAt);
  bucketStart.setUTCHours(0, 0, 0, 0);
  const fromMs = bucketStart.getTime();
  const toMs = fromMs + (24 * 60 * 60 * 1000) - 1;

  const oldTest = await t.mutation(apiAny.mutations.ingestNormalizedDelivery, {
    rawDelivery: buildRawDelivery({ receivedAt: oldReceivedAt, payloadHash: "old-test", dataClass: "test" }),
    events: [buildEvent({ capturedAt: oldReceivedAt, payloadHash: "old-test", valueNumeric: 1000 })],
  });

  const valid = await t.mutation(apiAny.mutations.ingestNormalizedDelivery, {
    rawDelivery: buildRawDelivery({ receivedAt: oldReceivedAt + 1000, payloadHash: "valid", dataClass: "valid" }),
    events: [buildEvent({ capturedAt: oldReceivedAt + 1000, payloadHash: "valid", valueNumeric: 400 })],
  });

  const recentTest = await t.mutation(apiAny.mutations.ingestNormalizedDelivery, {
    rawDelivery: buildRawDelivery({ receivedAt: recentReceivedAt, payloadHash: "recent-test", dataClass: "test" }),
    events: [buildEvent({ capturedAt: oldReceivedAt + 2000, payloadHash: "recent-test", valueNumeric: 250 })],
  });

  const before = await t.query(apiAny.queries.getAnalyticsTimeseries, {
    recordType: "steps",
    bucketSize: "day",
    fromMs,
    toMs,
  });
  expect(before[0].sum).toBe(1650);

  const cleanup = await t.mutation(internalAny.cleanup.runScheduledTestDataCleanup, {
    nowMs,
    retentionMs: DEFAULT_TEST_DATA_RETENTION_MS,
    batchSize: 10,
  });

  expect(cleanup.mode).toBe("delete");
  expect(cleanup.deletedDeliveryCount).toBe(1);
  expect(cleanup.deletedEventCount).toBe(1);
  expect(cleanup.rebuiltBucketCount).toBe(2);

  const deletedEvents = await t.query(apiAny.queries.getHealthEventsByDelivery, {
    rawDeliveryId: oldTest.deliveryId,
  });
  expect(deletedEvents).toHaveLength(0);

  const validEvents = await t.query(apiAny.queries.getHealthEventsByDelivery, {
    rawDeliveryId: valid.deliveryId,
  });
  expect(validEvents).toHaveLength(1);

  const recentTestEvents = await t.query(apiAny.queries.getHealthEventsByDelivery, {
    rawDeliveryId: recentTest.deliveryId,
  });
  expect(recentTestEvents).toHaveLength(1);

  const after = await t.query(apiAny.queries.getAnalyticsTimeseries, {
    recordType: "steps",
    bucketSize: "day",
    fromMs,
    toMs,
  });
  expect(after[0].sum).toBe(650);

  const runs = await t.query(internalAny.cleanup.listCleanupRuns, { limit: 1 });
  expect(runs[0].mode).toBe("delete");
  expect(runs[0].deletedEventCount).toBe(1);
});