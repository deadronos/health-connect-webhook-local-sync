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
  recordCount,
}: {
  receivedAt: number;
  payloadHash: string;
  recordCount: number;
}) => ({
  receivedAt,
  sourceIp: "127.0.0.1",
  userAgent: "vitest",
  payloadJson: `{"payloadHash":"${payloadHash}"}`,
  payloadHash,
  status: "stored" as const,
  recordCount,
  dataClass: "valid" as const,
});

const buildEvent = ({
  capturedAt,
  payloadHash,
  fingerprint,
  valueNumeric,
}: {
  capturedAt: number;
  payloadHash: string;
  fingerprint: string;
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
  fingerprint,
  createdAt: capturedAt,
});

test("ingestNormalizedEventsChunk keeps one delivery and dedupes across chunk boundaries", async () => {
  const t = convexTest(schema, modules);
  const capturedAt = Date.UTC(2024, 2, 19, 10, 0, 0, 0);
  const fromDate = new Date(capturedAt);
  fromDate.setUTCHours(0, 0, 0, 0);
  const fromMs = fromDate.getTime();
  const toMs = fromMs + (24 * 60 * 60 * 1000) - 1;

  const deliveryId = await t.mutation(apiAny.mutations.storeRawDelivery, buildRawDelivery({
    receivedAt: capturedAt,
    payloadHash: "buffered-delivery",
    recordCount: 4,
  }));

  const firstChunk = await t.mutation(apiAny.mutations.ingestNormalizedEventsChunk, {
    rawDeliveryId: deliveryId,
    events: [
      buildEvent({
        capturedAt,
        payloadHash: "buffered-a",
        fingerprint: "fp-a",
        valueNumeric: 1000,
      }),
      buildEvent({
        capturedAt: capturedAt + 60_000,
        payloadHash: "buffered-b",
        fingerprint: "fp-b",
        valueNumeric: 500,
      }),
    ],
  });

  const secondChunk = await t.mutation(apiAny.mutations.ingestNormalizedEventsChunk, {
    rawDeliveryId: deliveryId,
    events: [
      buildEvent({
        capturedAt: capturedAt + 120_000,
        payloadHash: "buffered-b-duplicate",
        fingerprint: "fp-b",
        valueNumeric: 500,
      }),
      buildEvent({
        capturedAt: capturedAt + 180_000,
        payloadHash: "buffered-c",
        fingerprint: "fp-c",
        valueNumeric: 250,
      }),
    ],
  });

  expect(firstChunk.receivedRecords).toBe(2);
  expect(firstChunk.storedRecords).toBe(2);
  expect(firstChunk.duplicateRecords).toBe(0);

  expect(secondChunk.receivedRecords).toBe(2);
  expect(secondChunk.storedRecords).toBe(1);
  expect(secondChunk.duplicateRecords).toBe(1);

  const deliveries = await t.query(apiAny.queries.listRecentDeliveries, { limit: 10 });
  expect(deliveries).toHaveLength(1);
  expect(deliveries[0].deliveryId).toBe(deliveryId);
  expect(deliveries[0].recordCount).toBe(4);

  const events = await t.query(apiAny.queries.getHealthEventsByDelivery, {
    rawDeliveryId: deliveryId,
  });
  expect(events).toHaveLength(3);
  expect(events.every((event: any) => event.rawDeliveryId === deliveryId)).toBe(true);

  const series = await t.query(apiAny.queries.getAnalyticsTimeseries, {
    recordType: "steps",
    bucketSize: "day",
    fromMs,
    toMs,
  });
  expect(series).toHaveLength(1);
  expect(series[0].count).toBe(3);
  expect(series[0].sum).toBe(1750);
  expect(series[0].latestValue).toBe(250);
  expect(series[0].latestAt).toBe(capturedAt + 180_000);
});
