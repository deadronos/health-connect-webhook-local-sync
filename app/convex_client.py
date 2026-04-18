import hashlib
import json
from datetime import datetime, UTC
from typing import Optional

import httpx


class ConvexClient:
    def __init__(self, convex_url: str, admin_key: str):
        self.site_url = f"{convex_url}/api/site"
        self.admin_key = admin_key

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.admin_key}",
            "Content-Type": "application/json",
        }

    def _post(self, path: str, args: dict) -> dict:
        payload = {"path": path, "args": args}
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                self.site_url,
                json=payload,
                headers=self._headers(),
            )
        resp.raise_for_status()
        data = resp.json()
        if data.get("error"):
            raise Exception(f"Convex error: {data['error']}")
        return data

    def mutation(self, mutation_name: str, args: dict) -> dict:
        result = self._post(f"healthIngester/mutations/{mutation_name}", args)
        return result

    def query(self, query_name: str, args: dict) -> dict:
        result = self._post(f"healthIngester/queries/{query_name}", args)
        return result

    def store_raw_delivery(
        self,
        source_ip: str,
        user_agent: Optional[str],
        payload_json: str,
        record_count: int,
        status: str = "stored",
        error_message: Optional[str] = None,
    ) -> str:
        payload_hash = hashlib.sha256(payload_json.encode()).hexdigest()
        received_at = int(datetime.now(UTC).timestamp() * 1000)
        result = self.mutation("storeRawDelivery", {
            "receivedAt": received_at,
            "sourceIp": source_ip,
            "userAgent": user_agent,
            "payloadJson": payload_json,
            "payloadHash": payload_hash,
            "status": status,
            "errorMessage": error_message,
            "recordCount": record_count,
        })
        return result.get("value", "")

    def store_health_events(self, events: list[dict]) -> list[str]:
        if not events:
            return []
        result = self.mutation("storeHealthEvents", {"events": events})
        return result.get("value", [])

    def check_duplicate(self, payload_hash: str) -> bool:
        result = self.mutation("checkDuplicateDelivery", {"payloadHash": payload_hash})
        return result.get("value", False)

    def list_recent_deliveries(self, limit: int = 10) -> list[dict]:
        result = self.query("listRecentDeliveries", {"limit": limit})
        return result.get("value", [])

    def check_db_health(self) -> dict:
        result = self.query("checkDbHealth", {})
        return result.get("value", {})