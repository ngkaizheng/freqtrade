"""Download Bybit 4h klines for the Binance top-N universe.

`PREREG_VENUE_COST_2026-09-29.md` chose Bybit on MEASURED FEASIBILITY, not
preference: 1000 bars per page against OKX's 100, and two more pages to reach
2023-01-01 against OKX's 76.

Two things this refuses to do silently:
  * a symbol that 404s or comes back empty is RECORDED and counted, never dropped
    quietly - the Bybit listing universe is smaller than Binance's and that fact
    is part of what is being measured;
  * the warmup bar count is reported per symbol, and a symbol below the
    strategy's 420-bar requirement is REPORTED rather than silently removed,
    because the newest Bybit listings are exactly the cohort under test.

Run:
    .venv\\Scripts\\python.exe tools\\widepanel\\fetch_bybit.py
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
BAR_MS = 4 * 3600 * 1000
START = int(datetime(2022, 12, 1, tzinfo=timezone.utc).timestamp() * 1000)
END = int(datetime(2026, 9, 27, tzinfo=timezone.utc).timestamp() * 1000)
TOPN = 200          # the Binance liquidity ranking, truncated - see below
WORKERS = 8

S = requests.Session()
S.headers.update({"User-Agent": "freqtrade-research/1.0"})


def fetch_page(sym: str, end: int | None) -> list[list]:
    p = {"category": "linear", "symbol": sym, "interval": "240", "limit": "1000"}
    if end is not None:
        p["end"] = str(end)
    for _ in range(4):
        try:
            r = S.get("https://api.bybit.com/v5/market/kline", params=p, timeout=40)
            j = r.json()
            if j.get("retCode") == 0:
                return j.get("result", {}).get("list", [])
            if j.get("retCode") in (10001, 10029, 110001):
                return []          # instrument or data genuinely absent
            time.sleep(1.0)
        except requests.RequestException:
            time.sleep(1.0)
    return []


def fetch_symbol(sym_binance: str, sym_bybit: str) -> dict:
    rows, end = [], END
    while True:
        d = fetch_page(sym_bybit, end)
        if not d:
            break
        rows.extend(d)
        oldest = min(int(x[0]) for x in d)
        if oldest <= START or len(d) < 1000:
            break
        end = oldest - 1
        time.sleep(0.1)
    if not rows:
        return {"binance": sym_binance, "bybit": sym_bybit, "ok": False,
                "reason": "no rows", "bars": 0}
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close",
                                     "volume", "turnover"])
    df["date"] = pd.to_datetime(df["ts"].astype("int64"), unit="ms", utc=True)
    df = (df[["date", "open", "high", "low", "close", "turnover"]]
          .rename(columns={"turnover": "quote_volume"})
          .drop_duplicates("date").sort_values("date").reset_index(drop=True))
    if len(df) < 420:
        return {"binance": sym_binance, "bybit": sym_bybit, "ok": False,
                "reason": f"only {len(df)} bars (<420 warmup)", "bars": len(df)}
    d = OUT / "klines_4h"
    d.mkdir(parents=True, exist_ok=True)
    df.to_csv(d / f"{sym_bybit}.csv.gz", index=False)
    return {"binance": sym_binance, "bybit": sym_bybit, "ok": True,
            "bars": len(df), "start": str(df["date"].iloc[0])[:19],
            "end": str(df["date"].iloc[-1])[:19]}


def main() -> int:
    # the Bybit universe, so symbols that do not exist there are known in advance
    r = S.get("https://api.bybit.com/v5/market/instruments-info"
              "?category=linear&limit=1000", timeout=60)
    inst = {x["symbol"] for x in r.json().get("result", {}).get("list", [])
            if x.get("quoteCoin") == "USDT" and x.get("status") == "Trading"}
    print(f"Bybit USDT linear instruments listed: {len(inst)}")

    liq = pd.read_csv(ROOT / "user_data" / "perp_short_out" / "liquidity_515.csv")
    liq = liq.head(TOPN)
    jobs, absent = [], []
    for b in liq["symbol"]:
        base = b[:-4] if b.endswith("USDT") else b
        cand = base + "USDT"
        if cand in inst:
            jobs.append((b, cand))
        else:
            absent.append((b, cand))
    print(f"Binance top-{TOPN}: {len(jobs)} exist on Bybit, "
          f"{len(absent)} do not (recorded, not dropped)")
    print(f"of the {len(liq)} requested, downloading {len(jobs)}\n")

    recs = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(fetch_symbol, b, c) for b, c in jobs]
        done = 0
        for f in as_completed(futs):
            done += 1
            try:
                recs.append(f.result())
            except Exception as e:  # noqa: BLE001
                recs.append({"ok": False, "reason": f"{type(e).__name__}",
                             "bybit": "?"})
            if done % 25 == 0:
                print(f"  {done}/{len(jobs)}  ({time.time()-t0:.0f}s)", flush=True)

    df = pd.DataFrame(recs)
    (OUT).mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / "download_log.csv", index=False)
    with (OUT / "absent_on_bybit.json").open("w") as f:
        json.dump(absent, f, indent=1)
    ok = df[df["ok"]]
    print(f"\ndownloaded {len(ok)}/{len(jobs)} in {time.time()-t0:.0f}s")
    if len(ok):
        print(ok["bars"].describe().to_string())
    bad = df[~df["ok"]]
    if len(bad):
        print(f"\nNOT USED ({len(bad)}), every reason recorded:")
        for r in bad.head(25).itertuples():
            print(f"   {getattr(r,'bybit','?'):<16} {r.reason}")
    print(f"\nabsent on Bybit entirely: {len(absent)} -> shark_data/bybit/absent_on_bybit.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
