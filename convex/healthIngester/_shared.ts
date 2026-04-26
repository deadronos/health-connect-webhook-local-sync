/**
 * Shared utility functions for health ingester Convex functions.
 *
 * These are extracted into a single module to avoid duplication across
 * mutations and queries. Import this module from any Convex function that
 * needs these helpers.
 */

type Period = "day" | "week" | "month";

export type PeriodBounds = {
  periodStart: number;
  periodEnd: number;
};

/**
 * Compute the start and end timestamps for the current period of a given type.
 *
 * - day:   00:00:00 UTC today to 00:00:00 UTC tomorrow
 * - week:  00:00 Monday UTC to 00:00 next Monday UTC
 * - month: 00:00 first day of current month UTC to 00:00 first day of next month UTC
 *
 * @param period  "day" | "week" | "month"
 * @param nowMs   Current time in Unix milliseconds (defaults to Date.now())
 * @returns PeriodBounds with periodStart and periodEnd
 */
export function getCurrentPeriodBounds(
  period: Period,
  nowMs: number = Date.now(),
): PeriodBounds {
  const now = new Date(nowMs);
  if (period === "day") {
    const start = new Date(now);
    start.setUTCHours(0, 0, 0, 0);
    const end = new Date(start);
    end.setUTCDate(end.getUTCDate() + 1);
    return { periodStart: start.getTime(), periodEnd: end.getTime() };
  }
  if (period === "week") {
    const start = new Date(now);
    const day = start.getUTCDay();
    const diff = day === 0 ? -6 : 1 - day;
    start.setUTCDate(start.getUTCDate() + diff);
    start.setUTCHours(0, 0, 0, 0);
    const end = new Date(start);
    end.setUTCDate(end.getUTCDate() + 7);
    return { periodStart: start.getTime(), periodEnd: end.getTime() };
  }
  // month — use UTC setters to avoid host local-timezone offset
  const year = now.getUTCFullYear();
  const month = now.getUTCMonth();
  const start = new Date(Date.UTC(year, month, 1, 0, 0, 0, 0));
  const end = new Date(Date.UTC(year, month + 1, 1, 0, 0, 0, 0));
  return { periodStart: start.getTime(), periodEnd: end.getTime() };
}

/**
 * Compute the period start timestamp for any historical event timestamp.
 *
 * Useful for grouping events by period when building rollups without needing
 * to know the current date.
 *
 * @param timestampMs  Unix milliseconds of the event
 * @param period       "day" | "week" | "month"
 * @returns Unix milliseconds of the period start
 */
export function getPeriodStart(timestampMs: number, period: Period): number {
  const date = new Date(timestampMs);
  if (period === "day") {
    date.setUTCHours(0, 0, 0, 0);
    return date.getTime();
  }
  if (period === "week") {
    const day = date.getUTCDay();
    const diff = day === 0 ? -6 : 1 - day;
    date.setUTCDate(date.getUTCDate() + diff);
    date.setUTCHours(0, 0, 0, 0);
    return date.getTime();
  }
  // month — use UTC setters so the start-of-month is always 00:00 UTC,
  // regardless of the host machine's local timezone
  date.setUTCDate(1);
  date.setUTCHours(0, 0, 0, 0);
  return date.getTime();
}