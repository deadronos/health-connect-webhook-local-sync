import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

export default defineSchema({
  rawDeliveries: defineTable({
    receivedAt: v.number(),
    sourceIp: v.string(),
    userAgent: v.optional(v.string()),
    payloadJson: v.string(),
    payloadHash: v.string(),
    status: v.union(v.literal("stored"), v.literal("error")),
    errorMessage: v.optional(v.string()),
    recordCount: v.number(),
  }).index("by_payload_hash", ["payloadHash"]),

  healthEvents: defineTable({
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
    .index("by_delivery", ["rawDeliveryId"])
    .index("by_payload_hash", ["payloadHash"])
    .index("by_fingerprint", ["recordType", "startTime", "valueNumeric", "unit"]),

  forwardAttempts: defineTable({
    rawDeliveryId: v.string(),
    targetName: v.string(),
    attemptedAt: v.number(),
    statusCode: v.optional(v.number()),
    success: v.boolean(),
    errorMessage: v.optional(v.string()),
  }).index("by_delivery", ["rawDeliveryId"]),
});