import { defineSchema } from "convex/schema";
import { authTables } from "convex/server";

export default defineSchema({
  rawDeliveries: defineTable({
    receivedAt: v.number(),           // Unix timestamp ms
    sourceIp: v.string(),
    userAgent: v.optional(v.string()),
    payloadJson: v.string(),          // Raw JSON text
    payloadHash: v.string(),          // SHA-256
    status: v.union(v.literal("stored"), v.literal("error")),
    errorMessage: v.optional(v.string()),
    recordCount: v.number(),
  }).setIndex("by_payload_hash", ["payloadHash"]),

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
    startTime: v.number(),            // Unix timestamp ms
    endTime: v.number(),
    capturedAt: v.number(),
    externalId: v.optional(v.string()),
    payloadHash: v.string(),
    createdAt: v.number(),
  })
    .setIndex("by_delivery", ["rawDeliveryId"])
    .setIndex("by_payload_hash", ["payloadHash"])
    .setIndex("by_fingerprint", ["recordType", "startTime", "valueNumeric", "unit"]),

  forwardAttempts: defineTable({
    rawDeliveryId: v.string(),
    targetName: v.string(),
    attemptedAt: v.number(),
    statusCode: v.optional(v.number()),
    success: v.boolean(),
    errorMessage: v.optional(v.string()),
  }).setIndex("by_delivery", ["rawDeliveryId"]),
});