import { v } from "convex/values";
import { mutation } from "./_generatedServer";

export const storeRawDelivery = mutation({
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

export const storeHealthEvents = mutation({
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

export const checkDuplicateDelivery = mutation({
  args: { payloadHash: v.string() },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("rawDeliveries")
      .withIndex("by_payload_hash", (q) => q.eq("payloadHash", args.payloadHash))
      .first();
    return existing !== null;
  },
});