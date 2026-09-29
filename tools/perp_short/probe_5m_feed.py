"""GATE 0: is 5m futures kline data actually obtainable for the deployed universe?

WHY THIS PROBE COMES FIRST
--------------------------
Section 35 built a pre-screen that closes a whole mechanism family from ARITHMETIC
before any research is spent, and section 38d established that the ONE family it
could not close honestly - the 5m liquidation-cascade family - was closed on an
EXTRAPOLATION wearing a measurement's label. Extrapolating an ATR from a coarser
horizon is a square root of time; section 39 measured that the real 1h/4h scaling
is 5 % flatter than that, which is small at 4x and may not be small at 60x.

**A missing data feed is BLOCKED, not FAILED, and a probe that tests the wrong feed
is not a test.** The repo already paid for that lesson once: the venue-cost probe
tested OKX's funding endpoint, which answers, instead of the bulk-archive path,
which does not - and concluded "the venue is closed" when the real answer was "the
route is closed". So this probe tests the EXACT thing the experiment needs:

  * 5m klines, USD-M futures, MONTHLY zips from Binance Vision;
  * for a symbol from the DEPLOYED whitelist, not a major;
  * in BOTH a calm month and a COVID month, because the family is a CRASH family
    and a calm-only ATR would be the wrong number to close it on.

It also measures how many of the deployed 40 are reachable at all, which is the
power question: the quantity is a median ATR% over symbols, and a median over 8
symbols is not a median over the deployed universe.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\probe_5m_feed.py
"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
CFG = ROOT / "user_data" / "config_perp_forward_dry.json"
BASE = "https://data.binance.vision/data/futures/um/monthly/klines"

# A calm month and a COVID month. The family's whole thesis is that it fires in
# crashes, so a calm-only measurement cannot close it.
MONTHS = {
    "calm": ["2024-03", "2024-09"],
    "covid": ["2020-03", "2020-07"],
    "recent": ["2025-11", "2026-01"],
}


def url(sym: str, m: str) -> str:
    return f"{BASE}/{sym}/5m/{sym}-5m-{m}.zip"


def head(sym: str, m: str) -> tuple[str, str, int, int]:
    """HEAD a single archive. Returns (sym, month, status, bytes)."""
    try:
        r = requests.head(url(sym, m), timeout=20, allow_redirects=True)
        return sym, m, r.status_code, int(r.headers.get("Content-Length", 0))
    except Exception as e:                                    # noqa: BLE001
        return sym, m, -1, 0


def archive_symbol(pair: str) -> str:
    """`BTC/USDT:USDT` -> `BTCUSDT`.

    ⚠ THE FIRST VERSION OF THIS PROBE REPORTED **0 of 40 SYMBOLS REACHABLE IN EVERY
    MONTH** - a clean, confident, completely wrong "the feed is BLOCKED". The cause
    was here: it did `pair.replace("/", "_").replace(":", "_").split("_")[0]`,
    which turns `BTC/USDT:USDT` into **`BTC`**, and Binance Vision's USD-M futures
    path is `BTCUSDT`. Every URL was well formed and every one of them 404'd.

    **The lesson is not "check your string surgery", it is that a 0 % or 100 %
    success rate is a BUG SIGNATURE, not a data result.** Real venues are messy;
    they do not fail perfectly. `main()` now refuses to report a data verdict on an
    all-or-nothing outcome and says the probe is broken instead.
    """
    base, _, rest = pair.partition("/")
    quote = rest.split(":")[0]
    return f"{base}{quote}"


def main() -> int:
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    wl = cfg["exchange"]["pair_whitelist"]
    pairs = [archive_symbol(p) for p in wl]
    print(f"5m FEED PROBE (Gate 0) - Binance Vision USD-M monthly klines\n")
    print(f"deployed symbols: {len(pairs)}   (e.g. {', '.join(pairs[:6])})")
    assert all(p.isalnum() and p.endswith(("USDT", "USDC", "BUSD")) for p in pairs), \
        f"symbol extraction looks wrong: {pairs[:5]}"

    jobs = [(s, m) for s in pairs for ms in MONTHS.values() for m in ms]
    with ThreadPoolExecutor(max_workers=8) as ex:
        res = list(ex.map(lambda a: head(*a), jobs))

    print(f"\ntesting {len(jobs)} archive URLs\n")
    print(f"{'month':<9}{'reachable':>11}{'404':>7}{'other':>7}"
          f"{'median MB':>11}   verdict")
    total_bytes = 0
    by_month: dict[str, list[tuple[int, int, int]]] = {}
    for sym, m, st, nb in res:
        by_month.setdefault(m, []).append((st, nb, 0))
        total_bytes += nb

    for label, ms in MONTHS.items():
        for m in ms:
            rows = by_month.get(m, [])
            ok = [r for r in rows if r[0] == 200]
            nf = [r for r in rows if r[0] == 404]
            other = [r for r in rows if r[0] not in (200, 404)]
            mb = sorted(r[1] for r in ok)
            med = mb[len(mb) // 2] / 1e6 if mb else 0.0
            verdict = "OK" if len(ok) >= 20 else ("PARTIAL" if ok else "UNUSABLE")
            print(f"{m:<9}{len(ok):>7}/{len(rows):<3}{len(nf):>7}{len(other):>7}"
                  f"{med:>10.1f}M   {verdict}")

    per_sym_ok = {}
    for sym, m, st, nb in res:
        per_sym_ok[sym] = per_sym_ok.get(sym, 0) + (1 if st == 200 else 0)
    n_months = len(jobs) // len(pairs)
    full = sorted(s for s, n in per_sym_ok.items() if n == n_months)
    print(f"\nsymbols with EVERY probed month reachable: {len(full)} of {len(pairs)}")
    print(f"projected download for the calm+covid set (4 months x {len(full)} syms): "
          f"{total_bytes/1e9:.2f} GB")
    print(f"projected download for ONE calm month x 40 syms: "
          f"{sum(nb for _, m, st, nb in res if st == 200 and m == '2024-03')/1e6:.0f} MB")

    # ---- THE ALL-OR-NOTHING GUARD -------------------------------------------
    # A real venue fails partially. A reach rate of exactly 0 % or exactly 100 %
    # across every month is a bug in the probe, not a fact about the data, and
    # reporting it as one is how this project produced a confident "BLOCKED" on a
    # feed that is fully available. See `archive_symbol`'s docstring.
    reach = [sum(1 for s, m, st, _ in res if m == mm and st == 200) / len(pairs)
             for mm in by_month]
    if all(r == 0.0 for r in reach) or all(r == 1.0 for r in reach):
        print("\nVERDICT: THE PROBE IS BROKEN, NOT THE FEED.")
        print("  Every month came back at exactly 0 % (or exactly 100 %) reachable.")
        print("  Real data sources fail partially; an all-or-nothing result is the")
        print("  signature of a wrong URL, a wrong symbol, or a method the host does")
        print("  not serve. **Do not report this as the feed being unavailable.**")
        print("  (It was exactly this failure: the archive symbol was `BTC`, not")
        print("   `BTCUSDT`.)")
        return 3

    print("\nVERDICT")
    if len(full) >= 20:
        print("  AVAILABLE. A 5m ATR% measured on these symbols is a MEASUREMENT, not")
        print("  an extrapolation, and it is the one input the pre-screen still lacks.")
        return 0
    print("  BLOCKED. Fewer than 20 of the deployed symbols have 5m archives in the")
    print("  probed months, so a median ATR% over them would not describe the")
    print("  deployed universe, and the pre-screen's 5m row must stay an")
    print("  extrapolation and be quoted as one. Do NOT substitute a major-only")
    print("  panel and report it as the deployed universe's number.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
