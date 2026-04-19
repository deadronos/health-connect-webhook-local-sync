import { mutationGeneric } from "convex/server";
import { v } from "convex/values";

const dataClassValidator = v.union(v.literal("valid"), v.literal("test"));

const recordTypeValidator = v.union(
  v.literal("steps"),
  v.literal("sleep"),
  v.literal("heart_rate"),
  v.literal("heart_rate_variability"),
  v.literal("distance"),
  v.literal("active_calories"),
  v.literal("total_calories"),
  v.literal("weight"),
  v.literal("height"),
  v.literal("oxygen_saturation"),
  v.literal("resting_heart_rate"),
  v.literal("exercise"),
  v.literal("nutrition"),
  v.literal("basal_metabolic_rate"),
  v.literal("body_fat"),
  v.literal("lean_body_mass"),
  v.literal("vo2_max")
);

const rawDeliveryValidator = {
  receivedAt: v.number(),
  sourceIp: v.string(),
  userAgent: v.optional(v.string()),
  payloadJson: v.string(),
  payloadHash: v.string(),
  status: v.union(v.literal("stored"), v.literal("error")),
  errorMessage: v.optional(v.string()),
  recordCount: v.number(),
  dataClass: v.optional(dataClassValidator),
  dataClassReason: v.optional(v.string()),
};

const healthEventValidator = v.object({
  rawDeliveryId: v.string(),
  recordType: recordTypeValidator,
  valueNumeric: v.number(),
  unit: v.string(),
  startTime: v.number(),
  endTime: v.number(),
  capturedAt: v.number(),
  deviceId: v.optional(v.string()),
  externalId: v.optional(v.string()),
  payloadHash: v.string(),
  fingerprint: v.string(),
  metadata: v.optional(v.any()),
  createdAt: v.number(),
});

type BucketSize = "hour" | "day";

type RawDelivery = {
  receivedAt: number;
  sourceIp: string;
  userAgent?: string;
  payloadJson: string;
  payloadHash: string;
  status: "stored" | "error";
  errorMessage?: string;
  recordCount: number;
  dataClass?: "valid" | "test";
  dataClassReason?: string;
};

type HealthEvent = {
  rawDeliveryId: string;
  recordType: string;
  valueNumeric: number;
  unit: string;
  startTime: number;
  endTime: number;
  capturedAt: number;
  deviceId?: string;
  externalId?: string;
  payloadHash: string;
  fingerprint: string;
  metadata?: unknown;
  createdAt: number;
};

const hasMissingIndexError = (error: unknown, indexName: string): boolean => {
  return error instanceof Error && error.message.includes(`Index ${indexName} not found.`);
};

const findExistingEventByFingerprint = async (ctx: any, fingerprint: string): Promise<any | null> => {
  try {
    const existing = await ctx.db
      .query("healthEvents")
      .withIndex("by_fingerprint", (q: any) => q.eq("fingerprint", fingerprint))
      .take(1);
    return existing[0] ?? null;
  } catch (error) {
    if (!hasMissingIndexError(error, "healthEvents.by_fingerprint")) {
      throw error;
    }

    const events = await ctx.db.query("healthEvents").collect();
    return events.find((event: any) => event.fingerprint === fingerprint) ?? null;
  }
};

const findExistingBucket = async (
  ctx: any,
  bucketSize: BucketSize,
  recordType: string,
  bucketStart: number,
): Promise<any | null> => {
  try {
    const existing = await ctx.db
      .query("healthEventBuckets")
      .withIndex("by_bucket", (q: any) =>
        q.eq("bucketSize", bucketSize).eq("recordType", recordType).eq("bucketStart", bucketStart)
      )
      .take(1);
    return existing[0] ?? null;
  } catch (error) {
    if (!hasMissingIndexError(error, "healthEventBuckets.by_bucket")) {
      throw error;
    }

    const buckets = await ctx.db.query("healthEventBuckets").collect();
    return (
      buckets.find(
        (bucket: any) =>
          bucket.bucketSize === bucketSize &&
          bucket.recordType === recordType &&
          bucket.bucketStart === bucketStart,
      ) ?? null
    );
  }
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

const upsertBucket = async (ctx: any, event: HealthEvent, bucketSize: BucketSize): Promise<void> => {
  const bucketStart = getBucketStart(event.capturedAt, bucketSize);
  const bucket = await findExistingBucket(ctx, bucketSize, event.recordType, bucketStart);
  if (bucket) {
    const isLatest = event.capturedAt >= bucket.latestAt;
    await ctx.db.patch(bucket._id, {
      count: bucket.count + 1,
      sum: bucket.sum + event.valueNumeric,
      min: Math.min(bucket.min, event.valueNumeric),
      max: Math.max(bucket.max, event.valueNumeric),
      latestValue: isLatest ? event.valueNumeric : bucket.latestValue,
      latestAt: isLatest ? event.capturedAt : bucket.latestAt,
    });
    return;
  }

  await ctx.db.insert("healthEventBuckets", {
    bucketSize,
    bucketStart,
    recordType: event.recordType,
    count: 1,
    sum: event.valueNumeric,
    min: event.valueNumeric,
    max: event.valueNumeric,
    latestValue: event.valueNumeric,
    latestAt: event.capturedAt,
  });
};

export const storeRawDelivery = mutationGeneric({
  args: rawDeliveryValidator,
  handler: async (ctx, args) => {
    const id = await ctx.db.insert("rawDeliveries", args as RawDelivery);
    return id;
  },
});

export const storeHealthEvents = mutationGeneric({
  args: {
    events: v.array(healthEventValidator),
  },
  handler: async (ctx, args) => {
    const ids: string[] = [];
    for (const event of args.events as HealthEvent[]) {
      const id = await ctx.db.insert("healthEvents", event);
      ids.push(id);
    }
    return ids;
  },
});

export const ingestNormalizedDelivery = mutationGeneric({
  args: {
    rawDelivery: v.object(rawDeliveryValidator),
    events: v.array(healthEventValidator),
  },
  handler: async (ctx, args) => {
    const deliveryId = await ctx.db.insert("rawDeliveries", args.rawDelivery as RawDelivery);
    const seenFingerprints = new Set<string>();
    let storedRecords = 0;

    for (const incomingEvent of args.events as HealthEvent[]) {
      if (seenFingerprints.has(incomingEvent.fingerprint)) {
        continue;
      }
      seenFingerprints.add(incomingEvent.fingerprint);

      const existing = await findExistingEventByFingerprint(ctx, incomingEvent.fingerprint);

      if (existing) {
        continue;
      }

      const event = {
        ...incomingEvent,
        rawDeliveryId: deliveryId,
      };

      await ctx.db.insert("healthEvents", event);
      storedRecords += 1;
      await upsertBucket(ctx, event, "hour");
      await upsertBucket(ctx, event, "day");
    }

    return {
      deliveryId,
      receivedRecords: args.events.length,
      storedRecords,
      duplicateRecords: args.events.length - storedRecords,
    };
  },
});

export const checkDuplicateDelivery = mutationGeneric({
  args: { payloadHash: v.string() },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("rawDeliveries")
      .withIndex("by_payload_hash", (q: any) => q.eq("payloadHash", args.payloadHash))
      .take(1);
    return existing.length > 0;
  },
});