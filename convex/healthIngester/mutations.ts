import { v } from "convex/values";
import { mutationGeneric } from "convex/server";

export const storeRawDelivery = mutationGeneric({
  args: {
    receivedAt: v.number(),
    sourceIp: v.string(),
    userAgent: v.optional(v.string()),
    payloadJson: v.string(),
    payloadHash: v.string(),
    status: v.union(v.literal("stored"), v.literal("error")),
    errorMessage: v.optional(v.string()),
    recordCount: v.number(),
  },
  handler: async (ctx, args) => {
    const id = await ctx.db.insert("rawDeliveries", args);
    return id;
  },
});

export const storeHealthEvents = mutationGeneric({
  args: {
    events: v.array(
      v.object({
        rawDeliveryId: v.string(),
        recordType: v.union(
          v.literal("steps"),
          v.literal("heart_rate"),
          v.literal("resting_heart_rate"),
          v.literal("weight")
        ),
        valueNumeric: v.number(),
        unit: v.string(),
        startTime: v.number(),
        endTime: v.number(),
        capturedAt: v.number(),
        externalId: v.optional(v.string()),
        payloadHash: v.string(),
        createdAt: v.number(),
      })
    ),
  },
  handler: async (ctx, args) => {
    const ids: string[] = [];
    for (const event of args.events) {
      const id = await ctx.db.insert("healthEvents", event);
      ids.push(id);
    }
    return ids;
  },
});

export const checkDuplicateDelivery = mutationGeneric({
  args: { payloadHash: v.string() },
  handler: async (ctx, args) => {
    // Scan all rawDeliveries to find matching hash (no index needed)
    const all = await ctx.db.query("rawDeliveries").take(1000);
    return all.some(d => d.payloadHash === args.payloadHash);
  },
});