"""GATE 0 for the open-interest line: does the feed exist, how deep is it, and can the
experiment conclude?

WHY THIS IS THE FIRST THING AND NOT THE STRATEGY
-------------------------------------------------
`docs-myself/GAP_ANALYSIS_2026-09-30.md` ranked Open Interest the #1 gap for a
reason that is strategic, not novelty: **the two delivered books are both pure
price/volume trend on the same 40 symbols.** A third book from the same family would
be the same bet twice, not diversification. OI is the one direction carrying
information price and volume cannot supply - "did new positions back this move".

Before any of that is worth a backtest, three things must be true, and all three
are cheap to check:
  1. the feed exists at a public URL,
  2. it is deep enough over ENOUGH of the deployed 40 to describe the universe,
  3. the resulting sample can distinguish a real effect from noise at all.

If any fails the line is recorded **INSUFFICIENT_DATA** and the round moves on. It is
not faked, and it is not approximated with a proxy.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\probe_oi_feed.py
"""

from __future__ import annotations

import io
import json
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
CFG = ROOT / "user_data" / "config_perp_forward_dry.json"
BASE = "https://data.binance.vision/data/futures/um/monthly/metrics"

# The window that matters is the one the delivered books were measured on, because a
# third book is only worth having if it can be compared with them over the same dates.
WINDOW = [f"{y}-{m:02d}" for y in (2023, 2024, 2025) for m in range(1, 13)] + \
         [f"2026-{m:02d}" for m in range(1, 9)]      # 2023-01 .. 2026-08 = 44 months
PROBE_MONTHS = ["2020-01", "2020-07", "2021-01", "2022-01", "2023-01",
                "2024-01", "2025-01", "2026-01"]      # 8 points across the whole era
MIN_SYMBOL_MONTHS = 25 * len(WINDOW) // 4            # 25 symbols over ~1/4 of the window


def archive_symbol(pair: str) -> str:
    base, _, rest = pair.partition("/")
    return f"{base}{rest.split(':')[0]}"


def url(sym: str, m: str) -> str:
    return f"{BASE}/{sym}/{sym}-metrics-{m}.zip"


def head(job: tuple[str, str]) -> tuple[str, str, int, int]:
    sym, m = job
    try:
        r = requests.head(url(sym, m), timeout=20, allow_redirects=True)
        return sym, m, r.status_code, int(r.headers.get("Content-Length", 0))
    except Exception:                                           # noqa: BLE001
        return sym, m, -1, 0


def main() -> int:
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    syms = [archive_symbol(p) for p in cfg["exchange"]["pair_whitelist"]]

    print("GATE 0  OPEN INTEREST - is the feed there, and is it deep enough?\n")
    print(f"deployed universe: {len(syms)} symbols")
    print(f"target window    : {WINDOW[0]} .. {WINDOW[-1]} ({len(WINDOW)} months)\n")

    # ---- 1. does it exist at all, and how far back? ------------------------
    print("1. EXISTENCE AND HISTORY (8 probe months x all symbols)")
    jobs = [(s, m) for s in syms for m in PROBE_MONTHS]
    with ThreadPoolExecutor(max_workers=8) as ex:
        res = list(ex.map(head, jobs))
    by_month: dict[str, int] = {}
    for _s, m, st, _n in res:
        if st == 200:
            by_month[m] = by_month.get(m, 0) + 1
    for m in PROBE_MONTHS:
        n = by_month.get(m, 0)
        print(f"   {m}  {n:>3}/{len(syms)} reachable   {'OK' if n >= 20 else 'SPARSE'}")
    if not by_month:
        print("\n   BLOCKED: nothing reachable at this URL pattern.")
        print("   Do NOT substitute a proxy feed and report it as open interest.")
        return 2

    # ---- 2. what is actually inside? ---------------------------------------
    print("\n2. SCHEMA - what columns does one archive carry?")
    sym = next((s for s, _m, st, _n in res if st == 200), syms[0])
    m = next(m for s, m, st, _n in res if st == 200 and s == sym)
    try:
        r = requests.get(url(sym, m), timeout=60)
        with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
            name = [n for n in zf.namelist() if n.endswith(".csv")][0]
            with zf.open(name) as fh:
                df = pd.read_csv(fh)
        print(f"   sample: {sym} {m}  rows={len(df)}")
        print(f"   columns: {list(df.columns)}")
        if "open_interest" in df.columns:
            oi = pd.to_numeric(df["open_interest"], errors="coerce")
            print(f"   open_interest: non-null {oi.notna().mean()*100:.1f}%  "
                  f"min {oi.min():,.0f}  max {oi.max():,.0f}  median {oi.median():,.0f}")
        else:
            print("   *** no `open_interest` column - this is NOT the feed we need ***")
    except Exception as e:                                       # noqa: BLE001
        print(f"   could not read the archive: {type(e).__name__}: {e}")

    # ---- 3. coverage over the window that matters --------------------------
    print(f"\n3. COVERAGE OVER THE MEASUREMENT WINDOW ({WINDOW[0]}..{WINDOW[-1]})")
    jobs = [(s, m) for s in syms for m in WINDOW]
    with ThreadPoolExecutor(max_workers=10) as ex:
        res2 = list(ex.map(head, jobs))
    got = [(s, m) for s, m, st, _n in res2 if st == 200]
    per_sym = {}
    for s, m in got:
        per_sym[s] = per_sym.get(s, 0) + 1
    full = [s for s, n in per_sym.items() if n == len(WINDOW)]
    print(f"   symbol-months available : {len(got):,} of {len(jobs):,}")
    print(f"   symbols with ALL 44 months : {len(full)} of {len(syms)}")
    if per_sym:
        n = sorted(per_sym.values())
        print(f"   per-symbol months: min {n[0]}  median {n[len(n)//2]}  max {n[-1]}")
    tot_mb = sum(nb for _s, _m, st, nb in res2 if st == 200) / 1e6
    print(f"   download size: {tot_mb:,.0f} MB")

    # ---- 4. can the experiment conclude? -----------------------------------
    print("\n4. POWER (AGENTS.md 1a) - can this line produce a verdict?")
    ok = len(got) >= MIN_SYMBOL_MONTHS
    print(f"   need >= {MIN_SYMBOL_MONTHS} symbol-months; have {len(got):,}")
    if not ok:
        print(f"   ** INSUFFICIENT_DATA. The line is closed as untestable, not as")
        print(f"      disproved, and NO number from it will be published. **")
        return 3
    print(f"   usable. {len(full)} symbols cover the whole window and the rest are")
    print(f"   partial; any symbol-count figure will state its own coverage.")
    print(f"\n   ⚠ THE SAMPLE IS THE SAME 4 CALENDAR YEARS (2023-2026) WITH 2 UP AND")
    print(f"   2 DOWN, and the final holdout is BURNED. A verdict here is n=4 regimes,")
    print(f"   not n=4 samples. The decision rule must be pre-registered BEFORE the")
    print(f"   download, or the next round is picking the best of four cells.")
    print(f"\nVERDICT: AVAILABLE. {len(got):,} symbol-months, {tot_mb:,.0f} MB. "
          f"Proceed to the preregistration.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
