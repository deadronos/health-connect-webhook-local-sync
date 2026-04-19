import { v } from "convex/values";
import { queryGeneric } from "convex/server";

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

const bucketSizeValidator = v.union(v.literal("hour"), v.literal("day"));

type BucketSize = "hour" | "day";

type AnalyticsFilters = {
  fromMs?: number;
  toMs?: number;
  recordTypes?: string[];
  deviceId?: string;
};

const filterEvents = (events: any[], filters: AnalyticsFilters): any[] => {
  return events.filter((event) => {
    if (filters.fromMs !== undefined && event.capturedAt < filters.fromMs) {
      return false;
    }
    if (filters.toMs !== undefined && event.capturedAt > filters.toMs) {
      return false;
    }
    if (filters.recordTypes && filters.recordTypes.length > 0 && !filters.recordTypes.includes(event.recordType)) {
      return false;
    }
    if (filters.deviceId !== undefined && event.deviceId !== filters.deviceId) {
      return false;
    }
    return true;
  });
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

const getBucketEnd = (timestamp: number, bucketSize: BucketSize): number => {
  const bucketStart = getBucketStart(timestamp, bucketSize);
  if (bucketSize === "hour") {
    return bucketStart + (60 * 60 * 1000) - 1;
  }
  return bucketStart + (24 * 60 * 60 * 1000) - 1;
};

const isExactBucketWindow = (
  fromMs: number | undefined,
  toMs: number | undefined,
  bucketSize: BucketSize,
): boolean => {
  const alignedFrom = fromMs === undefined || getBucketStart(fromMs, bucketSize) === fromMs;
  const alignedTo = toMs === undefined || getBucketEnd(toMs, bucketSize) === toMs;
  return alignedFrom && alignedTo;
};

const aggregateEventsIntoBuckets = (events: any[], bucketSize: BucketSize): any[] => {
  const buckets = new Map<number, any>();

  for (const event of events) {
    const bucketStart = getBucketStart(event.capturedAt, bucketSize);
    const existing = buckets.get(bucketStart);
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

    buckets.set(bucketStart, {
      bucketStart,
      count: 1,
      sum: event.valueNumeric,
      min: event.valueNumeric,
      max: event.valueNumeric,
      latestValue: event.valueNumeric,
      latestAt: event.capturedAt,
    });
  }

  return Array.from(buckets.values())
    .sort((left, right) => left.bucketStart - right.bucketStart)
    .map((bucket) => ({
      ...bucket,
      avg: bucket.count > 0 ? bucket.sum / bucket.count : null,
    }));
};

const eventFingerprint = (event: any): string => {
  return event.fingerprint ?? event.payloadHash;
};

export const listRecentDeliveries = queryGeneric({
  args: { limit: v.optional(v.number()) },
  handler: async (ctx, args) => {
    const limit = args.limit ?? 10;
    const deliveries = await ctx.db
      .query("rawDeliveries")
      .order("desc")
      .take(limit);
    return deliveries.map((d) => ({
      deliveryId: d._id,
      receivedAt: d.receivedAt,
      recordCount: d.recordCount,
      status: d.status,
    }));
  },
});

export const getDeliveryById = queryGeneric({
  args: { deliveryId: v.string() },
  handler: async (ctx, args) => {
    const delivery = await ctx.db.get(args.deliveryId as any);
    return delivery;
  },
});

export const getHealthEventsByDelivery = queryGeneric({
  args: { rawDeliveryId: v.string() },
  handler: async (ctx, args) => {
    const events = await ctx.db
      .query("healthEvents")
      .withIndex("by_delivery", (q) => q.eq("rawDeliveryId", args.rawDeliveryId))
      .collect();
    return events;
  },
});

export const getAnalyticsOverview = queryGeneric({
  args: {
    fromMs: v.optional(v.number()),
    toMs: v.optional(v.number()),
    recordTypes: v.optional(v.array(recordTypeValidator)),
    deviceId: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const events = await ctx.db.query("healthEvents").collect();
    const filtered = filterEvents(events, args);
    const cards = new Map<string, any>();

    for (const event of filtered) {
      const existing = cards.get(event.recordType);
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

      cards.set(event.recordType, {
        recordType: event.recordType,
        count: 1,
        min: event.valueNumeric,
        max: event.valueNumeric,
        sum: event.valueNumeric,
        latestValue: event.valueNumeric,
        latestAt: event.capturedAt,
      });
    }

    return Array.from(cards.values())
      .sort((left, right) => left.recordType.localeCompare(right.recordType))
      .map((card) => ({
        ...card,
        avg: card.count > 0 ? card.sum / card.count : null,
      }));
  },
});

export const getAnalyticsTimeseries = queryGeneric({
  args: {
    recordType: recordTypeValidator,
    bucketSize: bucketSizeValidator,
    fromMs: v.optional(v.number()),
    toMs: v.optional(v.number()),
    deviceId: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    if (args.deviceId || !isExactBucketWindow(args.fromMs, args.toMs, args.bucketSize)) {
      const events = await ctx.db.query("healthEvents").collect();
      const filtered = filterEvents(events, {
        fromMs: args.fromMs,
        toMs: args.toMs,
        recordTypes: [args.recordType],
        deviceId: args.deviceId,
      });
      return aggregateEventsIntoBuckets(filtered, args.bucketSize);
    }

    const buckets = await ctx.db.query("healthEventBuckets").collect();
    return buckets
      .filter((bucket) => {
        if (bucket.bucketSize !== args.bucketSize) {
          return false;
        }
        if (bucket.recordType !== args.recordType) {
          return false;
        }
        if (args.fromMs !== undefined && bucket.bucketStart < args.fromMs) {
          return false;
        }
        if (args.toMs !== undefined && bucket.bucketStart > args.toMs) {
          return false;
        }
        return true;
      })
      .sort((left, right) => left.bucketStart - right.bucketStart)
      .map((bucket) => ({
        bucketStart: bucket.bucketStart,
        count: bucket.count,
        sum: bucket.sum,
        min: bucket.min,
        max: bucket.max,
        avg: bucket.count > 0 ? bucket.sum / bucket.count : null,
        latestValue: bucket.latestValue,
        latestAt: bucket.latestAt,
      }));
  },
});

export const listAnalyticsEvents = queryGeneric({
  args: {
    fromMs: v.optional(v.number()),
    toMs: v.optional(v.number()),
    recordTypes: v.optional(v.array(recordTypeValidator)),
    deviceId: v.optional(v.string()),
    limit: v.optional(v.number()),
  },
  handler: async (ctx, args) => {
    const limit = args.limit ?? 100;
    const events = await ctx.db.query("healthEvents").collect();
    return filterEvents(events, args)
      .sort((left, right) => right.capturedAt - left.capturedAt)
      .slice(0, limit)
      .map((event) => ({
        rawDeliveryId: event.rawDeliveryId,
        recordType: event.recordType,
        valueNumeric: event.valueNumeric,
        unit: event.unit,
        startTime: event.startTime,
        endTime: event.endTime,
        capturedAt: event.capturedAt,
        deviceId: event.deviceId,
        externalId: event.externalId,
        payloadHash: event.payloadHash,
        fingerprint: eventFingerprint(event),
        metadata: event.metadata,
      }));
  },
});

export const checkDbHealth = queryGeneric({
  args: {},
  handler: async (ctx) => {
    try {
      await ctx.db.query("rawDeliveries").take(1);
      return { ok: true, db: "ok" };
    } catch {
      return { ok: false, db: "error" };
    }
  },
});

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