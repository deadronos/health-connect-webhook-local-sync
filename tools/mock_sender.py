#!/usr/bin/env python3
"""Mock sender — sends fixture payloads to the ingest server."""

import argparse
import json
import random
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import httpx


def jitter_timestamps(payload: dict, jitter_hours: int = 1) -> dict:
    """Shift all timestamps by a random offset within jitter_hours."""
    offset_ms = random.randint(-jitter_hours, jitter_hours) * 3600 * 1000
    records = payload.get("records", [])
    for record in records:
        for field in ("start_time_ms", "end_time_ms", "captured_at_ms"):
            if field in record:
                record[field] += offset_ms
    return payload


def send_fixture(
    fixture_path: Path,
    url: str,
    token: str,
    jitter_hours: int = 0,
    repeat: int = 1,
) -> bool:
    with open(fixture_path) as f:
        payload = json.load(f)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=30.0) as client:
        for i in range(repeat):
            p = jitter_timestamps(payload, jitter_hours) if jitter_hours > 0 else payload
            try:
                resp = client.post(url, json=p, headers=headers)
                resp.raise_for_status()
                print(f"[{i+1}/{repeat}] OK: {resp.json()}")
            except httpx.HTTPStatusError as e:
                print(f"[{i+1}/{repeat}] ERROR {e.response.status_code}: {e.response.text}", file=sys.stderr)
                return False
            except Exception as e:
                print(f"[{i+1}/{repeat}] ERROR: {e}", file=sys.stderr)
                return False
    return True


def main():
    parser = argparse.ArgumentParser(description="Send mock Health Connect webhook payloads")
    parser.add_argument("--fixture", type=Path, required=True, help="Path to fixture JSON file")
    parser.add_argument("--url", default="http://127.0.0.1:8787/ingest/health/v1", help="Ingest endpoint URL")
    parser.add_argument("--token", default="replace_me", help="Bearer token")
    parser.add_argument("--repeat", type=int, default=1, help="Number of times to repeat")
    parser.add_argument("--jitter-hours", type=int, default=0, help="Random timestamp jitter in hours")
    args = parser.parse_args()

    if not args.fixture.exists():
        print(f"Fixture not found: {args.fixture}", file=sys.stderr)
        sys.exit(1)

    success = send_fixture(
        fixture_path=args.fixture,
        url=args.url,
        token=args.token,
        jitter_hours=args.jitter_hours,
        repeat=args.repeat,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()