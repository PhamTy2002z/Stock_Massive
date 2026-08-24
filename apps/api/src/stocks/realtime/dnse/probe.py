"""Guarded read-only DNSE S1 conformance probe; emits sanitized JSON only."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .auth import DnseCredentials, RestSigner, WebSocketSigner
from .rest import DnseRestClient
from .websocket import DnseWebSocketClient, Subscription


_PROBE_CHANNELS = (
    ("tick_extra.G1.json", True),
    ("top_price.G1.json", True),
    ("foreign.G1.json", True),
    ("expected_price.G1.json", True),
    ("security_definition.G1.json", True),
    ("ohlc_closed.1.json", True),
    ("market_index.VNINDEX.json", False),
    ("session.STOCK.G1.json", False),
)


def _credentials(env_file: Path | None) -> DnseCredentials | None:
    values = dict(os.environ)
    if env_file and env_file.exists():
        for line in env_file.read_text().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            values.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    api_key = values.get("DNSE_API_KEY") or values.get("API_KEY")
    api_secret = (
        values.get("DNSE_API_SECRET")
        or values.get("API_SECRET")
        or values.get("API_SECRECT")
    )
    if not api_key or not api_secret:
        return None
    return DnseCredentials(api_key, api_secret)


def _is_market_hours(now: datetime) -> bool:
    if now.weekday() >= 5:
        return False
    minutes = now.hour * 60 + now.minute
    return 9 * 60 <= minutes <= 11 * 60 + 30 or 13 * 60 <= minutes <= 15 * 60


async def _websocket_probe(
    credentials: DnseCredentials,
    symbol: str,
    *,
    market_hours: bool,
    duration_seconds: float,
) -> dict[str, object]:
    client = DnseWebSocketClient(WebSocketSigner(credentials))
    report: dict[str, object] = {
        "authentication": "unverified",
        "subscriptions": "unverified",
        "channels_requested": len(_PROBE_CHANNELS),
        "payloads_observed": 0,
    }
    try:
        await client.connect()
        report["authentication"] = "ok"
        for channel, needs_symbol in _PROBE_CHANNELS:
            await client.subscribe(
                Subscription(channel, (symbol,) if needs_symbol else ())
            )
        report["subscriptions"] = "ok"
        report["subscription_lower_bound"] = len(_PROBE_CHANNELS)
        if not market_hours:
            report["payload_status"] = "skipped_outside_market_hours"
            return report

        counts: Counter[str] = Counter()
        started = time.monotonic()
        stream = client.stream()
        try:
            while True:
                remaining = duration_seconds - (time.monotonic() - started)
                if remaining <= 0:
                    break
                try:
                    payload = await asyncio.wait_for(anext(stream), timeout=remaining)
                except (TimeoutError, StopAsyncIteration):
                    break
                counts[str(payload.get("T", "unknown"))] += 1
        finally:
            await stream.aclose()
        elapsed = max(time.monotonic() - started, 0.001)
        total = sum(counts.values())
        report["payloads_observed"] = total
        report["event_family_counts"] = dict(sorted(counts.items()))
        report["observation_seconds"] = round(elapsed, 3)
        report["events_per_second"] = round(total / elapsed, 3)
        report["payload_status"] = "observed" if total else "no_payload_observed"
        return report
    except Exception as exc:
        report["status"] = "failed"
        report["error_type"] = type(exc).__name__
        return report
    finally:
        await client.close()


async def run(
    symbol: str,
    env_file: Path | None,
    *,
    duration_seconds: float = 20,
) -> dict[str, object]:
    now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
    market_hours = _is_market_hours(now)
    report: dict[str, object] = {
        "probe": "dnse-s1-read-only",
        "observed_at": now.isoformat(),
        "symbol": symbol,
        "market_hours": market_hours,
        "credentials_present": False,
        "rest": {},
        "websocket_market_payloads": "unverified",
        "throughput": "unverified",
        "subscription_limits": "unverified",
        "reconnect_gap": "unverified",
    }
    credentials = _credentials(env_file)
    if credentials is None:
        report["status"] = "skipped_missing_credentials"
        return report
    report["credentials_present"] = True
    async with DnseRestClient(RestSigner(credentials)) as client:
        checks = {
            "instruments": await client.instruments(symbol=symbol, limit=1),
            "security_definition": await client.security_definition(symbol),
            "trading_session": await client.trading_session(),
            "working_dates": await client.working_dates(),
        }
        report["rest"] = {
            name: "ok" if result.data is not None else result.outcome.kind.value
            for name, result in checks.items()
        }
        report["metrics"] = dict(client.metrics.snapshot().counters)
    websocket = await _websocket_probe(
        credentials,
        symbol,
        market_hours=market_hours,
        duration_seconds=duration_seconds,
    )
    report["websocket"] = websocket
    report["websocket_market_payloads"] = websocket.get(
        "payload_status", "unverified"
    )
    report["subscription_limits"] = (
        f"at_least_{websocket['subscription_lower_bound']}_channels"
        if "subscription_lower_bound" in websocket
        else "unverified"
    )
    report["throughput"] = (
        websocket.get("events_per_second", "unverified")
        if market_hours
        else "unverified"
    )
    report["status"] = (
        "transport_observed_market_hours_pending"
        if not market_hours
        else "market_hours_observed"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default="FPT")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--duration", type=float, default=20)
    args = parser.parse_args()
    if not 1 <= args.duration <= 120:
        parser.error("--duration must be between 1 and 120 seconds")
    print(
        json.dumps(
            asyncio.run(
                run(args.symbol, args.env_file, duration_seconds=args.duration)
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
