"""Coinalyze adapter -- the first free source of historical liquidation volume.

    python -m shark_hunter.coinalyze probe          # retention depth
    python -m shark_hunter.coinalyze fetch --years 4
    python -m shark_hunter.coinalyze status

SHARK-07 and the liquidation leg of SHARK-08 were BLOCKED across the whole
study because no free source of historical per-print liquidation data
existed. Coinalyze documents a ``/liquidation-history`` endpoint that
separates long and short liquidation volume, with caller-supplied
``from``/``to``. If its retention reaches back years, the blocked hypothesis
becomes testable immediately and the forward-collection plan is unnecessary.

The API key is read from the environment or ``shark_hunter/.env`` and is
never written into a cache file, a manifest or a log line.

Coinalyze asks for attribution: the spec requires citing the data source, and
that obligation travels with the numbers.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

import pandas as pd

from . import config as C

BASE = "https://api.coinalyze.net/v1"
CACHE = C.DATA_DIR / "coinalyze"
CACHE.mkdir(parents=True, exist_ok=True)

# Coinalyze market ids differ from Binance symbols. Verified via /future-markets.
MARKET = "BTCUSDT_PERP.A"

SOURCE_NOTE = (
    "Liquidation data: Coinalyze (https://coinalyze.net), free API tier, "
    "retrieved via /liquidation-history. Cited as required by the provider's "
    "terms. Exchange-specific; NOT global market liquidation volume."
)


def _key() -> str | None:
    return C.api_key("COINALYZE_API_KEY")


def _get(path: str, params: dict) -> tuple[int, object]:
    import requests
    key = _key()
    if not key:
        return 401, {"message": "no API key configured"}
    headers = {"api_key": key}
    # Coinalyze rate-limits; stay well under it and never hammer on failure.
    for attempt in range(4):
        try:
            r = requests.get(BASE + path, params=params, headers=headers, timeout=45)
        except Exception as exc:                       # noqa: BLE001
            if attempt == 3:
                return 0, {"message": f"{type(exc).__name__}: {str(exc)[:120]}"}
            time.sleep(2 ** attempt)
            continue
        if r.status_code == 200:
            return 200, r.json()
        if r.status_code in (429, 418):
            time.sleep(5 * (attempt + 1))
            continue
        try:
            return r.status_code, r.json()
        except ValueError:
            return r.status_code, {"message": r.text[:200]}
    return 0, {"message": "exhausted retries"}


def _periods(from_ts: int, to_ts: int, interval: str):
    """Yield chunked (from, to) windows; Coinalyze caps a single response."""
    # 90 days per request keeps each response comfortably sized for 5m data.
    chunk = 90 * 86400
    cur = from_ts
    while cur < to_ts:
        nxt = min(cur + chunk, to_ts)
        yield cur, nxt
        cur = nxt


def probe(interval: str = "1hour") -> int:
    """Find the earliest date with data, by walking backwards in coarse steps."""
    key = _key()
    if not key:
        print("NO API KEY. Set COINALYZE_API_KEY in the environment or in "
              "shark_hunter/.env")
        return 2
    print(f"key present ({len(key)} chars). Probing retention for {MARKET}...\n")

    now = int(time.time())
    tests = [
        ("now - 7d", now - 7 * 86400),
        ("now - 90d", now - 90 * 86400),
        ("now - 1y", now - 365 * 86400),
        ("now - 2y", now - 2 * 365 * 86400),
        ("now - 3y", now - 3 * 365 * 86400),
        ("now - 4y", now - 4 * 365 * 86400),
        ("now - 5y", now - 5 * 365 * 86400),
    ]
    earliest = None
    for label, frm in tests:
        status, body = _get("/liquidation-history",
                            {"symbols": MARKET, "interval": interval,
                             "from": frm, "to": frm + 3 * 86400})
        if status == 200 and isinstance(body, list) and body:
            # The field is `history`, per the published OpenAPI schema. An
            # earlier version read `liquidation_per_interval`, which is not a
            # key this endpoint ever emits, so every request looked like a
            # successful empty response.
            data = body[0].get("history", [])
            if data:
                first = int(data[0]["t"])
                d = dt.datetime.fromtimestamp(first, dt.timezone.utc).date()
                print(f"  {label:<10} OK  first bar {d}  ({len(data)} bars)")
                if earliest is None:
                    earliest = d
            else:
                print(f"  {label:<10} OK  but EMPTY")
        else:
            msg = body.get("message") if isinstance(body, dict) else str(body)[:80]
            print(f"  {label:<10} status={status}  {msg}")
        time.sleep(1.2)

    if earliest:
        years = (dt.datetime.now(dt.timezone.utc).date() - earliest).days / 365.25
        print(f"\nRETENTION: data appears to reach back to about {earliest} "
              f"(~{years:.1f} years)")
        print(f"If that holds, the blocked liquidation experiments become testable")
        print(f"and the forward-collection plan is unnecessary.")
    else:
        print("\nNo data returned at any depth -- probe failed.")
    return 0


def fetch(years: float = 4.0, interval: str = "1hour",
          symbols: list[str] | None = None) -> int:
    symbols = symbols or [MARKET]
    to_ts = int(time.time())
    from_ts = to_ts - int(years * 365.25 * 86400)
    for sym in symbols:
        frames = []
        got = 0
        for frm, to in _periods(from_ts, to_ts, interval):
            status, body = _get("/liquidation-history",
                                {"symbols": sym, "interval": interval,
                                 "from": frm, "to": to, "convert_to_usd": "true"})
            if status == 200 and isinstance(body, list):
                for item in body:
                    frames.append(pd.DataFrame(item.get("history", [])))
                got += 1
            else:
                msg = body.get("message") if isinstance(body, dict) else str(body)[:80]
                print(f"  {sym} [{dt.datetime.fromtimestamp(frm, dt.timezone.utc).date()}] "
                      f"status={status} {msg}")
            time.sleep(1.1)
        if not frames:
            print(f"{sym}: no data")
            continue
        df = pd.concat(frames, ignore_index=True)
        df.columns = ["timestamp", "long_liquidation", "short_liquidation"]
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
        df = (df.drop_duplicates(subset="timestamp")
                .sort_values("timestamp")
                .set_index("timestamp"))
        for c in ("long_liquidation", "short_liquidation"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["total_liquidation"] = df["long_liquidation"] + df["short_liquidation"]
        path = CACHE / f"{sym.replace('/', '_')}_{interval}.csv.gz"
        df.to_csv(path, compression="gzip")
        span = (df.index.max() - df.index.min()).days if len(df) else 0
        print(f"{sym}: {len(df):,} bars  {df.index.min().date()} -> "
              f"{df.index.max().date()}  ({span} days)  -> {path.name}")
        if len(df):
            print(f"    total long ${df['long_liquidation'].sum()/1e6:,.1f}M  "
                  f"short ${df['short_liquidation'].sum()/1e6:,.1f}M  "
                  f"(source: {SOURCE_NOTE.split(':')[0]})")
    return 0


def status() -> int:
    files = sorted(CACHE.glob("*.csv.gz"))
    if not files:
        print("no Coinalyze cache yet -- run 'fetch'")
        return 0
    for f in files:
        df = pd.read_csv(f, index_col=0, parse_dates=True)
        print(f"{f.name:<34} {len(df):>8,} bars  "
              f"{df.index.min()} -> {df.index.max()}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Coinalyze liquidation history")
    ap.add_argument("what", choices=["probe", "fetch", "status"])
    ap.add_argument("--years", type=float, default=4.0)
    ap.add_argument("--interval", default="1hour")
    ap.add_argument("--symbols", nargs="*", default=None)
    a = ap.parse_args(argv)
    if a.what == "probe":
        return probe(a.interval)
    if a.what == "fetch":
        return fetch(a.years, a.interval, a.symbols)
    return status()


if __name__ == "__main__":
    sys.exit(main())
