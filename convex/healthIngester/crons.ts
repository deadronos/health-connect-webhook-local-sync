import { cronJobs } from "convex/server";

import { internal } from "./_generated/api";

const crons = cronJobs();
const internalFunctions = internal as any;

crons.daily(
  "cleanup tagged test data",
  { hourUTC: 3, minuteUTC: 0 },
  internalFunctions.cleanup.runScheduledTestDataCleanup,
  {},
);

export default crons;