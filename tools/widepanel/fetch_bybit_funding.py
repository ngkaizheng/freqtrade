"""Download Bybit funding history for the downloaded symbols.

freqtrade's futures backtesting loads funding with `fail_without_data=True`
(`backtesting.py:428`), so a futures run without it CRASHES rather than
silently running unfunded - which is the right behaviour and the reason this
file exists rather than an approximation.

`RESEARCH_GOAL.md` 2.C and the prereg both forbid substituting a proxy for a
feed the design depends on. An unfunded book has a fabricated edge, so this
downloads the real thing or the run is BLOCKED.

3.5 years of 8-hourly settlements is ~3,800 rows per symbol; Bybit serves 200 per
page, so this is ~19 pages per symbol. Every page count and every gap is logged,
because a funding file that silently starts in 2024 would be a fabricated book
for the first year and nothing would say so.

Run:
    .venv\\Scripts\\python.exe tools\\widepanel\\fetch_bybit_funding.py
"""

from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "shark_data" / "bybit"
START = int(datetime(2022, 12, 1, tzinfo=timezone.utc).timestamp() * 1000)
WORKERS = 10

S = requests.Session()
S.headers.update({"User-Agent": "freqtrade-research/1.0"})


def page(sym: str, end: int | None) -> list[list]:
    p = {"category": "linear", "symbol": sym, "limit": "200"}
    if end is not None:
        p["end"] = str(end)
    for _ in range(4):
        try:
            r = S.get("https://api.bybit.com/v5/market/funding/history",
                      params=p, timeout=40)
            j = r.json()
            if j.get("retCode") == 0:
                return j.get("result", {}).get("list", [])
            time.sleep(1.0)
        except requests.RequestException:
            time.sleep(1.0)
    return []


def fetch(sym: str) -> dict:
    rows, end, pages = [], None, 0
    prev_oldest = None
    # ⚠ HARD GUARD. The first version had no progress check and spun forever:
    # if the `end` cursor is not honoured, every page returns the SAME 200 rows,
    # `oldest` never moves, and the loop runs until someone notices. Five
    # minutes and zero files is what that looked like. A paging loop that cannot
    # prove it is advancing is a paging loop that must stop.
    while pages < 60:
        d = page(sym, end)
        if not d:
            break
        rows.extend(d)
        pages += 1
        oldest = min(int(x["fundingRateTimestamp"]) for x in d)
        if prev_oldest is not None and oldest >= prev_oldest:
            return {"symbol": sym, "ok": False, "n": len(rows), "pages": pages,
                    "reason": f"cursor did not advance (stuck at "
                              f"{datetime.fromtimestamp(oldest/1000, timezone.utc).date()})"}
        prev_oldest = oldest
        if oldest <= START or len(d) < 200:
            break
        end = oldest - 1
        time.sleep(0.08)
    if not rows:
        return {"symbol": sym, "ok": False, "reason": "no funding rows", "n": 0}
    df = pd.DataFrame(rows)
    df["ts"] = df["fundingRateTimestamp"].astype("int64")
    df = (df[["ts", "fundingRate"]]
          .drop_duplicates("ts")
          .sort_values("ts").reset_index(drop=True))
    if df["ts"].min() > START + 90 * 86400 * 1000:
        return {"symbol": sym, "ok": False, "n": len(df), "pages": pages,
                "reason": f"history starts {datetime.fromtimestamp(df['ts'].min()/1000, timezone.utc).date()}, "
                          f"more than 90d after 2022-12-01"}
    d = OUT / "funding"
    d.mkdir(parents=True, exist_ok=True)
    df.to_csv(d / f"{sym}.csv.gz", index=False)
    return {"symbol": sym, "ok": True, "n": len(df), "pages": pages,
            "start": datetime.fromtimestamp(df["ts"].min() / 1000,
                                            timezone.utc).strftime("%Y-%m-%d"),
            "end": datetime.fromtimestamp(df["ts"].max() / 1000,
                                          timezone.utc).strftime("%Y-%m-%d")}


def main() -> int:
    # ⚠ `Path("X.csv.gz").stem` is "X.csv", NOT "X" - it strips only the LAST
    # suffix. This exact trap is already recorded in RESEARCH_STATE.md s9 (it
    # turned "104 klines + 104 funding" into "0 available, 0 dropped" there) and
    # it was hit AGAIN here: every symbol was requested as "XRPUSDT.csv", the
    # API returned no rows for all of them, and the log filled with
    # "no funding rows" while looking like a venue problem rather than a string
    # bug. `removesuffix` on the NAME, not `.stem` on the Path.
    syms = [p.name.removesuffix(".csv.gz") for p in (OUT / "klines_4h").glob("*.csv.gz")]
    print(f"funding needed for {len(syms)} symbols")
    print(f"   sample requested names: {syms[:3]}")
    assert all(not s.endswith(".csv") for s in syms), "symbol name still carries .csv"
    recs = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(fetch, s): s for s in syms}
        done = 0
        for f in as_completed(futs):
            done += 1
            try:
                recs.append(f.result())
            except Exception as e:  # noqa: BLE001
                recs.append({"symbol": futs[f], "ok": False, "n": 0,
                             "reason": f"{type(e).__name__}"})
            if done % 25 == 0:
                print(f"  {done}/{len(syms)}  ({time.time()-t0:.0f}s)", flush=True)
    df = pd.DataFrame(recs)
    df.to_csv(OUT / "funding_log.csv", index=False)
    ok = df[df["ok"]]
    print(f"\nfetched for {len(ok)}/{len(syms)} in {time.time()-t0:.0f}s")
    if len(ok):
        print(ok[["n", "pages"]].describe().to_string())
        print(f"\nstart dates: earliest {ok['start'].min()}, "
              f"latest start {ok['start'].max()}")
    bad = df[~df["ok"]]
    if len(bad):
        print(f"\nNOT USED ({len(bad)}), every reason recorded:")
        for r in bad.itertuples():
            print(f"   {r.symbol:<16} {r.reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
