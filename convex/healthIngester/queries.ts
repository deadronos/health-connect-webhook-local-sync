import { v } from "convex/values";
import { queryGeneric } from "convex/server";

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