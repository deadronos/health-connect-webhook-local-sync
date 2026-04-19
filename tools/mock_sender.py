#!/usr/bin/env python3
"""Mock sender — sends fixture payloads to the ingest server for testing."""

import argparse
import json
import random
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import httpx


def jitter_timestamps(payload: dict, jitter_hours: int = 1) -> dict:
    """Shift all timestamps in a generic-format payload by a random offset.

    Applies a random positive or negative time shift to simulate payloads
    arriving at different times while maintaining relative ordering.

    Args:
        payload: The parsed JSON payload with a "records" list.
        jitter_hours: Maximum absolute offset in hours (default 1).

    Returns:
        The payload with all timestamp fields shifted by the random offset.
    """
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
    mark_test_data: bool = True,
    user_agent: str = "health-ingest-mock-sender/1.0",
) -> bool:
    """Send a fixture JSON file to the ingest endpoint.

    Loads a fixture payload and POSTs it to the specified URL with
    Bearer authentication. Optionally applies timestamp jitter and
    repeats the send multiple times.

    Args:
        fixture_path: Path to the JSON fixture file to send.
        url: Full URL of the ingest endpoint.
        token: Bearer token for authentication.
        jitter_hours: Maximum timestamp jitter in hours (0 disables jitter).
        repeat: Number of times to send the fixture (default 1).
        mark_test_data: If True, sets X-OpenClaw-Test-Data header (default True).
        user_agent: User-Agent string to send with the request.

    Returns:
        True if all requests succeeded (HTTP 2xx), False otherwise.
    """
    with open(fixture_path) as f:
        payload = json.load(f)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": user_agent,
        "X-OpenClaw-Test-Data": "true" if mark_test_data else "false",
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
    """CLI entry point for the mock sender tool.

    Parses command-line arguments and invokes send_fixture(). Exits with
    status 0 on success and 1 on any failure.
    """
    parser = argparse.ArgumentParser(description="Send mock Health Connect webhook payloads")
    parser.add_argument("--fixture", type=Path, required=True, help="Path to fixture JSON file")
    parser.add_argument("--url", default="http://127.0.0.1:8787/ingest/health/v1", help="Ingest endpoint URL")
    parser.add_argument("--token", default="replace_me", help="Bearer token")
    parser.add_argument("--repeat", type=int, default=1, help="Number of times to repeat")
    parser.add_argument("--jitter-hours", type=int, default=0, help="Random timestamp jitter in hours")
    parser.add_argument("--user-agent", default="health-ingest-mock-sender/1.0", help="User-Agent header")
    parser.set_defaults(mark_test_data=True)
    parser.add_argument(
        "--mark-test-data",
        dest="mark_test_data",
        action="store_true",
        help="Mark the delivery as test data eligible for scheduled cleanup (default)",
    )
    parser.add_argument(
        "--keep-data",
        dest="mark_test_data",
        action="store_false",
        help="Send the fixture without the scheduled-cleanup test-data marker",
    )
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
        mark_test_data=args.mark_test_data,
        user_agent=args.user_agent,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
