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
    ),
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
  })
    .index("by_delivery", ["rawDeliveryId"])
    .index("by_payload_hash", ["payloadHash"])
    .index("by_fingerprint", ["fingerprint"]),

  healthEventBuckets: defineTable({
    bucketSize: v.union(v.literal("hour"), v.literal("day")),
    bucketStart: v.number(),
    recordType: v.string(),
    deviceId: v.optional(v.string()),
    count: v.number(),
    sum: v.number(),
    min: v.number(),
    max: v.number(),
    latestValue: v.number(),
    latestAt: v.number(),
  }).index("by_bucket", ["bucketSize", "recordType", "bucketStart"]),

  forwardAttempts: defineTable({
    rawDeliveryId: v.string(),
    targetName: v.string(),
    attemptedAt: v.number(),
    statusCode: v.optional(v.number()),
    success: v.boolean(),
    errorMessage: v.optional(v.string()),
  }).index("by_delivery", ["rawDeliveryId"]),
});