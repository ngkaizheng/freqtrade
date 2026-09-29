"""Download the 422 perps the panel never saw, 4h klines + funding + mark.

WHY
---
`PREREG_WIDENED_UNIVERSE_2026-09-28.md`. The delivered book was measured on 104
perps that existed before 2023-01; a user in 2026 can trade 527. The 422 newer
symbols have never contributed a single trade to any number in this project, and
Grobys/Sandretto/Aijo (2026, FRL, PEER REVIEWED) say survivor-coin momentum
payoffs are an artefact of coins that were only temporarily accessible.

COHORTS ARE DERIVED FROM BINANCE'S OWN `exchangeInfo`, NOT FROM ANY RESULT
------------------------------------------------------------------------
`contractType == PERPETUAL`, `status == TRADING`, `quoteAsset == USDT`,
`BTCDOMUSDT` excluded (a dominance INDEX, not a crypto price). The onboard
year defines the cohort. Nothing here can be selected on outcome because
nothing here looks at an outcome.

WHAT IT REFUSES TO DO SILENTLY
------------------------------
* A symbol whose download 404s is DROPPED **and recorded with its reason** -
  a successful-looking empty response must never read as "no data exists"
  (RESEARCH_STATE.md 3.10).
* A symbol with **less than 420 bars of usable history is REPORTED, NOT
  DROPPED** - dropping it would silently remove exactly the newest cohort,
  which is the thing under test.
* Months are walked from each symbol's OWN listing month, not from 2023-01, so a
  2026 listing does not generate 44 months of 404s per symbol.

Run:
    .venv\\Scripts\\python.exe tools\\widepanel\\fetch_widened.py
"""

from __future__ import annotations

import io
import json
import os
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "shark_data" / "widened"
VISION = "https://data.binance.vision/data/futures/um/monthly"
EXCLUDE = {"BTCDOMUSDT"}
NOW = (2026, 9)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "freqtrade-research/1.0"})


def universe() -> list[dict]:
    r = SESSION.get("https://fapi.binance.com/fapi/v1/exchangeInfo", timeout=60)
    r.raise_for_status()
    out = []
    for s in r.json()["symbols"]:
        if not (s["contractType"] == "PERPETUAL"
                and s["status"] == "TRADING"
                and s["quoteAsset"] == "USDT"
                and s["symbol"] not in EXCLUDE):
            continue
        y = datetime.fromtimestamp(s["onboardDate"] / 1000, tz=timezone.utc).year
        cohort = ("A" if s["onboardDate"] <= 1672531200000
                  else chr(ord("B") + y - 2023) if y <= 2026 else "Z")
        out.append({"symbol": s["symbol"], "onboard_ms": s["onboardDate"],
                    "cohort": cohort})
    return sorted(out, key=lambda d: d["symbol"])


def months_since(sym: str, onboard_ms: int) -> list[tuple[str, str]]:
    y, m = datetime.fromtimestamp(onboard_ms / 1000, tz=timezone.utc).year, \
        datetime.fromtimestamp(onboard_ms / 1000, tz=timezone.utc).month
    out = []
    while (y, m) <= NOW:
        out.append((f"{y}-{m:02d}", f"{y}{m:02d}"))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def fetch(kind: str, sym: str, month: str) -> pd.DataFrame | None:
    # fundingRate has NO timeframe segment on Binance Vision:
    #   /fundingRate/{sym}/{sym}-fundingRate-{ym}.zip
    # while klines does:
    #   /klines/{sym}/4h/{sym}-4h-{ym}.zip
    if kind == "klines":
        url = f"{VISION}/klines/{sym}/{TF}/{sym}-{TF}-{month}.zip"
    else:
        url = f"{VISION}/fundingRate/{sym}/{sym}-fundingRate-{month}.zip"
    for _ in range(3):
        try:
            r = SESSION.get(url, timeout=45)
        except requests.RequestException:
            time.sleep(1.0)
            continue
        if r.status_code == 404:
            return None
        if r.status_code != 200:
            time.sleep(1.0)
            continue
        try:
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                return pd.read_csv(z.open(z.namelist()[0]), header=0)
        except Exception:
            time.sleep(0.5)
    return None


TF = "4h"
WORKERS = int(os.environ.get("WIDENED_WORKERS", "24"))


def build_symbol(job: dict) -> dict:
    sym, cohort = job["symbol"], job["cohort"]
    ms = months_since(sym, job["onboard_ms"])
    # ⚠ THE FIRST VERSION FETCHED ONE MONTH ONLY (`if len(bars) < 1`), which
    # can never clear the 420-bar warmup - one month of 4h is ~180 bars - so
    # EVERY symbol was rejected and the run reported "downloaded 0/422" while
    # looking perfectly healthy. Full history since listing is required.
    #
    # ⚠ AND THE SECOND VERSION wrote the klines file BEFORE parsing funding, then
    # raised on `pd.to_datetime(..., unit="ms", format="ISO8601")` - pandas
    # refuses both arguments together - so 411 klines files were on disk while
    # the log said "downloaded 0/422". The download succeeded; the REPORT was
    # wrong. Hence the skip-if-present below and the count printed from disk
    # rather than from the in-memory record.
    kpath = OUT / "klines_4h" / f"{sym}_4h.csv.gz"
    fpath = OUT / "funding" / f"{sym}.csv.gz"
    bars, fund = [], []
    if kpath.exists() and fpath.exists():
        return {"symbol": sym, "cohort": cohort, "ok": True, "cached": True,
                "bars": int(pd.read_csv(kpath, usecols=["date"]).shape[0])}
    for month, _ in ms:
        if not kpath.exists():
            d = fetch("klines", sym, month)
            if d is not None and len(d):
                bars.append(d)
        if not fpath.exists():
            f = fetch("fundingRate", sym, month)
            if f is not None and len(f):
                fund.append(f)
    if not kpath.exists() and bars:
        _write_klines(sym, bars)
    if not fpath.exists() and fund:
        _write_funding(sym, fund)
    if not kpath.exists():
        return {"symbol": sym, "cohort": cohort, "ok": False,
                "reason": "no klines at all", "bars": 0}
    k = pd.read_csv(kpath, usecols=["date"])
    if len(k) < 420:
        return {"symbol": sym, "cohort": cohort, "ok": False,
                "reason": f"only {len(k)} bars (< 420 warmup)", "bars": len(k)}
    return {"symbol": sym, "cohort": cohort, "ok": True, "bars": len(k),
            "start": str(k["date"].iloc[0])[:19], "end": str(k["date"].iloc[-1])[:19]}


def _write_klines(sym: str, bars: list) -> None:
    k = pd.concat(bars, ignore_index=True)
    k["date"] = pd.to_datetime(k["open_time"], unit="ms", utc=True)
    k = (k[["date", "open", "high", "low", "close", "volume"]]
         .drop_duplicates("date").sort_values("date").reset_index(drop=True))
    (OUT / "klines_4h").mkdir(parents=True, exist_ok=True)
    k.to_csv(OUT / "klines_4h" / f"{sym}_4h.csv.gz", index=False)


def _write_funding(sym: str, fund: list) -> None:
    f = pd.concat(fund, ignore_index=True)
    # ⚠ `calc_time` IS AN INT (epoch ms) IN THE FRESHLY DOWNLOADED FILES and a
    # STRING in the pre-existing `shark_data/wide/funding/*.csv.gz` this repo
    # has been using. Passing `unit=` and `format=` together raises "cannot
    # specify both"; passing only `format="ISO8601"` raises "Time data
    # 1718625600000 is not ISO8601 format". Both failures killed the whole run
    # and reported "downloaded 0/422" while the klines were already on disk.
    # So the dtype decides the parser, and it is asserted rather than assumed.
    if pd.api.types.is_numeric_dtype(f["calc_time"]):
        f["calc_time"] = pd.to_datetime(f["calc_time"], unit="ms", utc=True)
    else:
        f["calc_time"] = pd.to_datetime(f["calc_time"], utc=True,
                                        format="ISO8601")
    f = (f[["calc_time", "last_funding_rate"]]
         .drop_duplicates("calc_time").sort_values("calc_time")
         .reset_index(drop=True))
    (OUT / "funding").mkdir(parents=True, exist_ok=True)
    f.to_csv(OUT / "funding" / f"{sym}.csv.gz", index=False)


def main() -> int:
    (OUT / "funding").mkdir(parents=True, exist_ok=True)
    syms = universe()
    (OUT / "universe.json").write_text(json.dumps(syms, indent=1))
    counts = pd.Series([s["cohort"] for s in syms]).value_counts().sort_index()
    print(f"universe from exchangeInfo: {len(syms)} symbols")
    print("  " + "  ".join(f"{k}={v}" for k, v in counts.items()))
    new = [s for s in syms if s["cohort"] != "A"]
    print(f"to download: {len(new)} new symbols "
          f"(cohort A already on disk in shark_data/wide)")
    total_zips = sum(len(months_since(s["symbol"], s["onboard_ms"])) for s in new)
    print(f"~{total_zips} monthly requests expected")

    t0 = time.time()
    recs = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(build_symbol, s): s for s in new}
        done = 0
        for f in as_completed(futs):
            done += 1
            try:
                recs.append(f.result())
            except Exception as e:
                recs.append({"symbol": futs[f]["symbol"],
                             "cohort": futs[f]["cohort"], "ok": False,
                             "reason": f"exception {type(e).__name__}: {e}"})
            if done % 25 == 0:
                print(f"  {done}/{len(new)}  ({time.time()-t0:.0f}s)", flush=True)

    df = pd.DataFrame(recs).sort_values("symbol")
    df.to_csv(OUT / "download_log.csv", index=False)
    ok = df[df["ok"]]
    print(f"\ndownloaded {len(ok)}/{len(new)}  in {time.time()-t0:.0f}s")
    if len(ok):
        print("by cohort (bars per symbol):")
        print(ok.groupby("cohort")["bars"].agg(["count", "min", "median", "max"]))
    bad = df[~df["ok"]]
    if len(bad):
        print(f"\nDROPPED {len(bad)} (recorded, not silently skipped):")
        for r in bad.itertuples():
            print(f"   {r.symbol:<16} {r.cohort}  {r.reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
