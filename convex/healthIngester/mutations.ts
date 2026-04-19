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

type MutationLookupState = {
  existingEventsByFingerprint?: Map<string, any>;
  existingBucketsByKey?: Map<string, any>;
};

type IngestMutationResult = {
  receivedRecords: number;
  storedRecords: number;
  duplicateRecords: number;
};

const hasMissingIndexError = (error: unknown, indexName: string): boolean => {
  return error instanceof Error && error.message.includes(`Index ${indexName} not found.`);
};

const getBucketKey = (bucketSize: BucketSize, recordType: string, bucketStart: number): string => {
  return `${bucketSize}:${recordType}:${bucketStart}`;
};

const loadEventLookup = async (ctx: any, lookupState?: MutationLookupState): Promise<Map<string, any>> => {
  if (!lookupState) {
    const events = await ctx.db.query("healthEvents").collect();
    return new Map(events.map((event: any) => [event.fingerprint, event]));
  }

  if (!lookupState.existingEventsByFingerprint) {
    const events = await ctx.db.query("healthEvents").collect();
    lookupState.existingEventsByFingerprint = new Map(events.map((event: any) => [event.fingerprint, event]));
  }

  return lookupState.existingEventsByFingerprint;
};

const loadBucketLookup = async (ctx: any, lookupState?: MutationLookupState): Promise<Map<string, any>> => {
  if (!lookupState) {
    const buckets = await ctx.db.query("healthEventBuckets").collect();
    return new Map(
      buckets.map((bucket: any) => [getBucketKey(bucket.bucketSize, bucket.recordType, bucket.bucketStart), bucket]),
    );
  }

  if (!lookupState.existingBucketsByKey) {
    const buckets = await ctx.db.query("healthEventBuckets").collect();
    lookupState.existingBucketsByKey = new Map(
      buckets.map((bucket: any) => [getBucketKey(bucket.bucketSize, bucket.recordType, bucket.bucketStart), bucket]),
    );
  }

  return lookupState.existingBucketsByKey;
};

const findExistingEventByFingerprint = async (
  ctx: any,
  fingerprint: string,
  lookupState?: MutationLookupState,
): Promise<any | null> => {
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

    const eventsByFingerprint = await loadEventLookup(ctx, lookupState);
    return eventsByFingerprint.get(fingerprint) ?? null;
  }
};

const findExistingBucket = async (
  ctx: any,
  bucketSize: BucketSize,
  recordType: string,
  bucketStart: number,
  lookupState?: MutationLookupState,
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

    const bucketsByKey = await loadBucketLookup(ctx, lookupState);
    return bucketsByKey.get(getBucketKey(bucketSize, recordType, bucketStart)) ?? null;
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

const upsertBucket = async (
  ctx: any,
  event: HealthEvent,
  bucketSize: BucketSize,
  lookupState?: MutationLookupState,
): Promise<void> => {
  const bucketStart = getBucketStart(event.capturedAt, bucketSize);
  const bucketKey = getBucketKey(bucketSize, event.recordType, bucketStart);
  const bucket = await findExistingBucket(ctx, bucketSize, event.recordType, bucketStart, lookupState);
  if (bucket) {
    const isLatest = event.capturedAt >= bucket.latestAt;
    const nextBucket = {
      count: bucket.count + 1,
      sum: bucket.sum + event.valueNumeric,
      min: Math.min(bucket.min, event.valueNumeric),
      max: Math.max(bucket.max, event.valueNumeric),
      latestValue: isLatest ? event.valueNumeric : bucket.latestValue,
      latestAt: isLatest ? event.capturedAt : bucket.latestAt,
    };
    await ctx.db.patch(bucket._id, nextBucket);
    if (lookupState?.existingBucketsByKey) {
      lookupState.existingBucketsByKey.set(bucketKey, {
        ...bucket,
        ...nextBucket,
      });
    }
    return;
  }

  const nextBucket = {
    bucketSize,
    bucketStart,
    recordType: event.recordType,
    count: 1,
    sum: event.valueNumeric,
    min: event.valueNumeric,
    max: event.valueNumeric,
    latestValue: event.valueNumeric,
    latestAt: event.capturedAt,
  };

  const bucketId = await ctx.db.insert("healthEventBuckets", nextBucket);
  if (lookupState?.existingBucketsByKey) {
    lookupState.existingBucketsByKey.set(bucketKey, {
      _id: bucketId,
      ...nextBucket,
    });
  }
};

const ingestEventsIntoDelivery = async (
  ctx: any,
  rawDeliveryId: string,
  incomingEvents: HealthEvent[],
): Promise<IngestMutationResult> => {
  const seenFingerprints = new Set<string>();
  const lookupState: MutationLookupState = {};
  let storedRecords = 0;

  for (const incomingEvent of incomingEvents) {
    if (seenFingerprints.has(incomingEvent.fingerprint)) {
      continue;
    }
    seenFingerprints.add(incomingEvent.fingerprint);

    const existing = await findExistingEventByFingerprint(ctx, incomingEvent.fingerprint, lookupState);

    if (existing) {
      continue;
    }

    const event = {
      ...incomingEvent,
      rawDeliveryId,
    };

    const eventId = await ctx.db.insert("healthEvents", event);
    if (lookupState.existingEventsByFingerprint) {
      lookupState.existingEventsByFingerprint.set(event.fingerprint, {
        _id: eventId,
        ...event,
      });
    }
    storedRecords += 1;
    await upsertBucket(ctx, event, "hour", lookupState);
    await upsertBucket(ctx, event, "day", lookupState);
  }

  return {
    receivedRecords: incomingEvents.length,
    storedRecords,
    duplicateRecords: incomingEvents.length - storedRecords,
  };
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
    const ingestResult = await ingestEventsIntoDelivery(ctx, deliveryId, args.events as HealthEvent[]);

    return {
      deliveryId,
      ...ingestResult,
    };
  },
});

export const ingestNormalizedEventsChunk = mutationGeneric({
  args: {
    rawDeliveryId: v.string(),
    events: v.array(healthEventValidator),
  },
  handler: async (ctx, args) => {
    return ingestEventsIntoDelivery(ctx, args.rawDeliveryId, args.events as HealthEvent[]);
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