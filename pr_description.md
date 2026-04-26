🎯 **What:**
Added unit tests for the previously untested `ConvexClient.list_recent_deliveries` method. The tests mock the underlying Convex query `queries.js:listRecentDeliveries` and verify the correct passing of the `limit` parameter, as well as handling of non-list return types and `ConvexError`s.

📊 **Coverage:**
*   Happy path (default limit)
*   Happy path (custom limit)
*   Edge case (non-list result)
*   Error path (ConvexError raised)

✨ **Result:**
Improved test coverage for `app/convex_client.py`, specifically adding deterministic, fast unit tests for the `list_recent_deliveries` method. The entire test suite passes.
