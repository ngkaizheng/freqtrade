"""
Rebuild the cross-sectional universe.

The blocker on the cross-sectional line was never the research, it was the
data: 5 perpetuals in `binance_v2` and 9 in `shark_data`. A quantile sort on
5 names is a 2-vs-2 spread. The adversarial review is right that breadth --
not diversification -- is what a cross-section needs, and diversification
saturates by ~20 names, so 150 is ample and 500 buys nothing.

This downloads daily klines for the widest USD-M perpetual universe Binance
serves, which is the resolution a weekly-rebalanced cross-sectional design
needs and the cheapest to store.

Survivorship is a known, uncorrectable bias here: `exchangeInfo` only returns
currently-listed contracts. Both TRADING and SETTLING are included so the
universe is as wide as the venue will admit, and the bias is recorded rather
than hidden.

Run:  .venv\\Scripts\\python.exe tools\\universe\\build_universe.py --top 200
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "user_data/universe"
BASE = "https://data.binance.vision/data/futures/um/monthly/klines"
UA = {"User-Agent": "freqtrade-universe-builder/1.0"}


def http(url: str, tries: int = 3) -> bytes:
    last = None
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"{url}: {last}")


def universe(limit: int) -> pd.DataFrame:
    info = json.loads(http("https://fapi.binance.com/fapi/v1/exchangeInfo"))
    rows = []
    for s in info["symbols"]:
        if s["contractType"] != "PERPETUAL" or s["quoteAsset"] != "USDT":
            continue
        if s["status"] not in ("TRADING", "SETTLING"):
            continue
        rows.append({
            "symbol": s["symbol"],
            "status": s["status"],
            "onboard_date": pd.to_datetime(s.get("onboardDate"), unit="ms", utc=True).date()
            if s.get("onboardDate") else None,
        })
    df = pd.DataFrame(rows)
    df = df.sort_values("onboard_date").reset_index(drop=True)
    if limit and len(df) > limit:
        # Oldest listings first: they have the longest usable history, which is
        # what a cross-sectional panel needs. Survivorship bias is recorded,
        # not corrected -- there is no delisted-symbol registry to correct it
        # with.
        df = df.head(limit)
    return df


def months_from(start: date, end: date):
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield f"{y:04d}-{m:02d}"
        m += 1
        if m == 13:
            y, m = y + 1, 1


def _one_month(symbol: str, ym: str):
    url = f"{BASE}/{symbol}/1d/{symbol}-1d-{ym}.zip"
    try:
        raw = http(url, tries=2)
    except RuntimeError:
        return None                       # not listed that month
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            with z.open(z.namelist()[0]) as fh:
                df = pd.read_csv(io.BytesIO(fh.read()), header=None)
    except (zipfile.BadZipFile, KeyError, pd.errors.EmptyDataError):
        return None
    if df.iloc[0, 0] == "open_time":
        df = df.iloc[1:]
    # Binance kline layout: 0 open_time, 1 open, 2 high, 3 low, 4 close,
    # 5 base volume, 6 close_time, 7 QUOTE volume, 8 trades. Column 7 is
    # quote asset volume, not a trade count.
    return df[[0, 1, 2, 3, 4, 5, 7]].copy()


def fetch_daily(symbol: str, months, month_workers: int = 8) -> pd.DataFrame:
    """Fetch one symbol's daily klines.

    The months are fetched concurrently. Fetching them serially costs ~265 s
    per symbol because each archive is a separate HTTPS round trip, which for
    200 symbols is 15 hours; concurrently it is a few seconds, and the whole
    build finishes inside the time it takes to read it.
    """
    parts = []
    with ThreadPoolExecutor(max_workers=month_workers) as ex:
        for res in ex.map(lambda ym: _one_month(symbol, ym), list(months)):
            if res is not None:
                parts.append(res)
    if not parts:
        return pd.DataFrame()
    out = pd.concat(parts, ignore_index=True)
    out.columns = ["open_time", "open", "high", "low", "close", "volume", "quote_volume"]
    # Force the types explicitly. Mixing a header row into one archive leaves
    # the concat as object dtype, and `pd.to_datetime` then parses the integer
    # epoch as a *string* and raises OutOfBoundsDatetime. This is the same
    # pandas-3.0 trap recorded in AGENTS.md section 4.
    for c in ["open_time", "open", "high", "low", "close", "volume", "quote_volume"]:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    out = out.dropna(subset=["open_time", "close"])
    out["open_time"] = out["open_time"].astype("int64")
    out["date"] = pd.to_datetime(
        pd.Series(out["open_time"].to_numpy(), index=out.index), unit="ms", utc=True
    ).dt.date
    return out[["date", "open", "high", "low", "close", "volume", "quote_volume"]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=200)
    ap.add_argument("--workers", type=int, default=16)
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    uni = universe(args.top)
    print(f"universe: {len(uni)} perpetuals  "
          f"({(uni['status'] == 'TRADING').sum()} trading, "
          f"{(uni['status'] == 'SETTLING').sum()} settling)")
    print(f"  earliest listing {uni['onboard_date'].min()}, "
          f"latest {uni['onboard_date'].max()}")
    print("  SURVIVORSHIP: exchangeInfo returns only currently-listed contracts.")
    print("  There is no delisted-symbol registry, so this panel is survivor-only.\n")

    started = datetime.now(timezone.utc)
    today = started.date()
    raw_dir = OUT / "raw_daily"
    raw_dir.mkdir(exist_ok=True)

    def work(row):
        sym = row["symbol"]
        target = raw_dir / f"{sym}_1d.csv.gz"
        if target.exists():
            return sym, "cached", 0
        months = list(months_from(row["onboard_date"], today))
        df = fetch_daily(sym, months)
        if df.empty:
            return sym, "empty", 0
        df = df.drop_duplicates("date").sort_values("date").reset_index(drop=True)
        df.to_csv(target, index=False, compression="gzip")
        return sym, "ok", len(df)

    done = failed = cached = 0
    rows = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(work, r): r["symbol"] for _, r in uni.iterrows()}
        for fut in as_completed(futs):
            sym = futs[fut]
            try:
                sym, status, n = fut.result()
                rows.append({"symbol": sym, "status": status, "rows": n})
                if status == "cached":
                    cached += 1
                else:
                    done += 1
            except Exception as exc:
                failed += 1
                rows.append({"symbol": sym, "status": f"error: {exc}", "rows": 0})
            if (done + cached + failed) % 25 == 0:
                print(f"  {done + cached + failed}/{len(uni)}  ok={done} cached={cached} failed={failed}",
                      flush=True)

    summary = pd.DataFrame(rows)
    summary.to_csv(OUT / "universe_build_summary.csv", index=False)
    manifest = {
        "run_utc": started.isoformat(timespec="seconds"),
        "requested": int(args.top),
        "universe_size": int(len(uni)),
        "downloaded": done,
        "cached": cached,
        "failed": failed,
        "interval": "1d",
        "survivorship_bias": "survivor-only; exchangeInfo exposes no delisted registry",
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\ndone: {done} downloaded, {cached} cached, {failed} failed")
    print(f"manifest -> {(OUT / 'manifest.json').relative_to(ROOT)}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
