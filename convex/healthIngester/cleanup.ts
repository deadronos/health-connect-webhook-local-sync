import { internalMutationGeneric, internalQueryGeneric } from "convex/server";
import { v } from "convex/values";

const DEFAULT_BATCH_SIZE = 50;
export const DEFAULT_TEST_DATA_RETENTION_MS = 24 * 60 * 60 * 1000;
const BUCKET_SIZES = ["hour", "day"] as const;

type BucketSize = (typeof BUCKET_SIZES)[number];

type BucketKey = {
  bucketSize: BucketSize;
  bucketStart: number;
  recordType: string;
};

type BucketAggregate = {
  count: number;
  sum: number;
  min: number;
  max: number;
  latestValue: number;
  latestAt: number;
};

const hasMissingIndexError = (error: unknown, indexName: string): boolean => {
  return error instanceof Error && error.message.includes(`Index ${indexName} not found.`);
};

const encodeBucketKey = (key: BucketKey): string => `${key.bucketSize}:${key.recordType}:${key.bucketStart}`;

const decodeBucketKey = (value: string): BucketKey => {
  const [bucketSize, recordType, bucketStart] = value.split(":");
  return {
    bucketSize: bucketSize as BucketSize,
    recordType,
    bucketStart: Number(bucketStart),
  };
};

const getBucketStart = (timestamp: number, bucketSize: BucketSize): number => {
  const date = new Date(timestamp);
  if (bucketSize === "hour") {
    date.setUTCMinutes(0, 0, 0);
  } else {
    date.setUTCHours(0, 0, 0, 0);
  }
  return date.getTime();
};

const addAffectedBucketKeys = (bucketKeys: Set<string>, event: any) => {
  for (const bucketSize of BUCKET_SIZES) {
    bucketKeys.add(
      encodeBucketKey({
        bucketSize,
        recordType: event.recordType,
        bucketStart: getBucketStart(event.capturedAt, bucketSize),
      }),
    );
  }
};

const getCleanupCandidates = async (ctx: any, cutoffReceivedAt: number, batchSize: number): Promise<any[]> => {
  try {
    return await ctx.db
      .query("rawDeliveries")
      .withIndex("by_data_class_and_received_at", (q: any) =>
        q.eq("dataClass", "test").lt("receivedAt", cutoffReceivedAt),
      )
      .order("asc")
      .take(batchSize);
  } catch (error) {
    if (!hasMissingIndexError(error, "rawDeliveries.by_data_class_and_received_at")) {
      throw error;
    }

    const deliveries = await ctx.db.query("rawDeliveries").collect();
    return deliveries
      .filter((delivery: any) => delivery.dataClass === "test" && delivery.receivedAt < cutoffReceivedAt)
      .sort((left: any, right: any) => left.receivedAt - right.receivedAt)
      .slice(0, batchSize);
  }
};

const getEventsByDelivery = async (ctx: any, rawDeliveryId: string): Promise<any[]> => {
  return await ctx.db
    .query("healthEvents")
    .withIndex("by_delivery", (q: any) => q.eq("rawDeliveryId", rawDeliveryId))
    .collect();
};

const getForwardAttemptsByDelivery = async (ctx: any, rawDeliveryId: string): Promise<any[]> => {
  return await ctx.db
    .query("forwardAttempts")
    .withIndex("by_delivery", (q: any) => q.eq("rawDeliveryId", rawDeliveryId))
    .collect();
};

const buildAffectedBucketAggregates = (events: any[], affectedKeys: Set<string>): Map<string, BucketAggregate> => {
  const aggregates = new Map<string, BucketAggregate>();

  for (const event of events) {
    for (const bucketSize of BUCKET_SIZES) {
      const encodedKey = encodeBucketKey({
        bucketSize,
        recordType: event.recordType,
        bucketStart: getBucketStart(event.capturedAt, bucketSize),
      });

      if (!affectedKeys.has(encodedKey)) {
        continue;
      }

      const existing = aggregates.get(encodedKey);
      if (existing) {
        existing.count += 1;
        existing.sum += event.valueNumeric;
        existing.min = Math.min(existing.min, event.valueNumeric);
        existing.max = Math.max(existing.max, event.valueNumeric);
        if (event.capturedAt >= existing.latestAt) {
          existing.latestAt = event.capturedAt;
          existing.latestValue = event.valueNumeric;
        }
        continue;
      }

      aggregates.set(encodedKey, {
        count: 1,
        sum: event.valueNumeric,
        min: event.valueNumeric,
        max: event.valueNumeric,
        latestValue: event.valueNumeric,
        latestAt: event.capturedAt,
      });
    }
  }

  return aggregates;
};

const rebuildAffectedBuckets = async (ctx: any, affectedKeys: Set<string>): Promise<number> => {
  if (affectedKeys.size === 0) {
    return 0;
  }

  const survivingEvents = await ctx.db.query("healthEvents").collect();
  const aggregates = buildAffectedBucketAggregates(survivingEvents, affectedKeys);
  const existingBuckets = await ctx.db.query("healthEventBuckets").collect();
  const existingByKey = new Map<string, any>();

  for (const bucket of existingBuckets) {
    const encodedKey = encodeBucketKey({
      bucketSize: bucket.bucketSize,
      recordType: bucket.recordType,
      bucketStart: bucket.bucketStart,
    });
    if (affectedKeys.has(encodedKey)) {
      existingByKey.set(encodedKey, bucket);
    }
  }

  let rebuiltBucketCount = 0;
  for (const encodedKey of affectedKeys) {
    const key = decodeBucketKey(encodedKey);
    const aggregate = aggregates.get(encodedKey);
    const existing = existingByKey.get(encodedKey);

    if (!aggregate) {
      if (existing) {
        await ctx.db.delete(existing._id);
        rebuiltBucketCount += 1;
      }
      continue;
    }

    const bucketPatch = {
      count: aggregate.count,
      sum: aggregate.sum,
      min: aggregate.min,
      max: aggregate.max,
      latestValue: aggregate.latestValue,
      latestAt: aggregate.latestAt,
    };

    if (existing) {
      await ctx.db.patch(existing._id, bucketPatch);
    } else {
      await ctx.db.insert("healthEventBuckets", {
        bucketSize: key.bucketSize,
        bucketStart: key.bucketStart,
        recordType: key.recordType,
        ...bucketPatch,
      });
    }

    rebuiltBucketCount += 1;
  }

  return rebuiltBucketCount;
};

export const runScheduledTestDataCleanup = internalMutationGeneric({
  args: {
    nowMs: v.optional(v.number()),
    retentionMs: v.optional(v.number()),
    batchSize: v.optional(v.number()),
    dryRun: v.optional(v.boolean()),
  },
  handler: async (ctx, args) => {
    const nowMs = args.nowMs ?? Date.now();
    const retentionMs = args.retentionMs ?? DEFAULT_TEST_DATA_RETENTION_MS;
    const cutoffReceivedAt = nowMs - retentionMs;
    const batchSize = args.batchSize ?? DEFAULT_BATCH_SIZE;
    const dryRun = args.dryRun ?? false;
    const candidateDeliveries = await getCleanupCandidates(ctx, cutoffReceivedAt, batchSize);

    let candidateEventCount = 0;
    let deletedDeliveryCount = 0;
    let deletedEventCount = 0;
    let deletedForwardAttemptCount = 0;
    const affectedBucketKeys = new Set<string>();

    for (const delivery of candidateDeliveries) {
      const events = await getEventsByDelivery(ctx, delivery._id);
      const attempts = await getForwardAttemptsByDelivery(ctx, delivery._id);
      candidateEventCount += events.length;

      if (dryRun) {
        continue;
      }

      for (const event of events) {
        addAffectedBucketKeys(affectedBucketKeys, event);
        await ctx.db.delete(event._id);
        deletedEventCount += 1;
      }

      for (const attempt of attempts) {
        await ctx.db.delete(attempt._id);
        deletedForwardAttemptCount += 1;
      }

      await ctx.db.delete(delivery._id);
      deletedDeliveryCount += 1;
    }

    const rebuiltBucketCount = dryRun ? 0 : await rebuildAffectedBuckets(ctx, affectedBucketKeys);
    const mode = dryRun ? "dry_run" : "delete";
    const cleanupRunId = await ctx.db.insert("cleanupRuns", {
      startedAt: nowMs,
      finishedAt: nowMs,
      mode,
      retentionMs,
      cutoffReceivedAt,
      candidateDeliveryCount: candidateDeliveries.length,
      candidateEventCount,
      deletedDeliveryCount,
      deletedEventCount,
      deletedForwardAttemptCount,
      rebuiltBucketCount,
    });

    return {
      cleanupRunId,
      mode,
      cutoffReceivedAt,
      candidateDeliveryCount: candidateDeliveries.length,
      candidateEventCount,
      deletedDeliveryCount,
      deletedEventCount,
      deletedForwardAttemptCount,
      rebuiltBucketCount,
    };
  },
});

export const listCleanupRuns = internalQueryGeneric({
  args: { limit: v.optional(v.number()) },
  handler: async (ctx, args) => {
    const limit = args.limit ?? 10;
    const runs = await ctx.db.query("cleanupRuns").collect();
    return runs
      .sort((left: any, right: any) => right.startedAt - left.startedAt)
      .slice(0, limit)
      .map((run: any) => ({
        cleanupRunId: run._id,
        startedAt: run.startedAt,
        finishedAt: run.finishedAt,
        mode: run.mode,
        retentionMs: run.retentionMs,
        cutoffReceivedAt: run.cutoffReceivedAt,
        candidateDeliveryCount: run.candidateDeliveryCount,
        candidateEventCount: run.candidateEventCount,
        deletedDeliveryCount: run.deletedDeliveryCount,
        deletedEventCount: run.deletedEventCount,
        deletedForwardAttemptCount: run.deletedForwardAttemptCount,
        rebuiltBucketCount: run.rebuiltBucketCount,
      }));
  },
});