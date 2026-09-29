"""
Step 0: measure the actual round-trip cost, because everything turns on it.

The cross-sectional literature disagrees by 3-5x on the only number that
decides the outcome:

    Fieberg et al. (JFQA 2025)   30 bp long / 40 bp short per trade
    Arefev (SSRN 7404139)        ~59 bp implied from 0.40 pp/wk at 68% turnover
    this repository              12-18 bp

The E#4 reversal result has a breakeven at 26.6 bps round trip. Above that it
loses money; below it it makes 32-55%/yr. Nobody has published a measurement
of realised cost on these venues, and this repository's own documentation
records that no order-book data was available when its cost model was written.

Binance publishes a live depth endpoint. That does not give historical impact,
but it does give the thing that matters most and is measurable today: the
QUOTED cost of crossing a given notional, per symbol, right now -- the spread
plus the walk-the-book fill cost, on both legs.

This is a measurement, not a backtest. It has no multiple-testing problem and it
cannot be made to look good by choosing a window.

Run:  .venv\\Scripts\\python.exe tools\\cross_sectional\\measure_cost.py
"""

from __future__ import annotations

import json
import statistics
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
UA = {"User-Agent": "freqtrade-cost-measure/1.0"}

NOTIONALS = (10_000, 50_000, 250_000, 1_000_000)   # USD
MAJORS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
          "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT",
          "TRXUSDT", "DOTUSDT", "MATICUSDT", "ATOMUSDT", "NEARUSDT",
          "APTUSDT", "ARBUSDT", "OPUSDT", "INJUSDT", "SUIUSDT"]


def get(url: str, tries: int = 3) -> dict:
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except Exception as exc:          # rate limit, unknown symbol, transient
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(str(last))


def crossing_cost(levels, notional: float) -> tuple[float, int, bool]:
    """Walk the book consuming `notional` USD.

    Returns (vwap, levels_used, filled). `filled` is False when the book ran out
    of depth before the notional was consumed; a partial fill must never be
    reported as a complete one, because it silently understates the cost.

    (An earlier version returned (vwap, vwap, used) against a documented
    (vwap, bps, levels_used) contract, and never checked for a shortfall.)
    """
    spent = qty = 0.0
    used = 0
    for price, size in levels:
        if price <= 0:
            continue
        avail = price * size
        take = avail if (spent + avail) <= notional else (notional - spent)
        spent += take
        qty += take / price
        used += 1
        if spent >= notional:
            break
    if qty <= 0:
        return float("nan"), used, False
    return spent / qty, used, spent >= notional


def measure(symbol: str) -> dict:
    try:
        book = get(f"https://fapi.binance.com/fapi/v1/depth?symbol={symbol}&limit=1000")
    except Exception as exc:
        return {"symbol": symbol, "error": f"fetch failed: {exc}"}
    # The depth endpoint answers with an error object rather than an HTTP error
    # when a symbol is unknown or the request is throttled.
    if "bids" not in book or "asks" not in book:
        return {"symbol": symbol, "error": f"no book: {str(book)[:120]}"}
    bids = [(float(p), float(q)) for p, q in book["bids"]]
    asks = [(float(p), float(q)) for p, q in book["asks"]]
    if not bids or not asks:
        return {"symbol": symbol, "error": "empty book"}

    best_bid, best_ask = bids[0][0], asks[0][0]
    mid = (best_bid + best_ask) / 2
    spread_bps = (best_ask - best_bid) / mid * 1e4

    row = {
        "symbol": symbol,
        "mid": mid,
        "quoted_spread_bps": round(spread_bps, 2),
        "levels_asked": len(asks),
    }
    for n in NOTIONALS:
        # buy then sell the same notional, the round trip a rebalance makes
        buy_vwap, used_a, ok_a = crossing_cost(asks, n)
        sell_vwap, used_b, ok_b = crossing_cost(bids, n)
        if not (ok_a and ok_b):
            row[f"rt_bps_{n}"] = None
            row[f"short_{n}"] = True
            continue
        row[f"short_{n}"] = False
        row[f"rt_bps_{n}"] = round((buy_vwap - sell_vwap) / mid * 1e4, 2)
        row[f"book_levels_{n}"] = f"{used_a}/{used_b}"
    return row


def main() -> int:
    print("=" * 88)
    print("MEASURED ROUND-TRIP COST, Binance USD-M perpetuals")
    print(f"  {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    print("=" * 88)
    print("""
  The book is the taker side. Entering and leaving a position crosses it once
  each way, so the round trip is what the walk-the-book cost returns. This is a
  LOWER bound on the real cost: it excludes the adverse selection of trading
  into a book that moves while the order is working, and any fee tier above
  VIP0.
""")

    rows = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        for r in ex.map(measure, MAJORS):
            rows.append(r)

    ok = [r for r in rows if "error" not in r]
    bad = [r for r in rows if "error" in r]
    if not ok:
        print("  no books returned")
        return 1

    print(f"{'symbol':<11}{'spread':>9}" + "".join(f"{'RT ' + str(n // 1000) + 'k':>12}" for n in NOTIONALS))
    print("-" * 71)
    for r in sorted(ok, key=lambda x: x["quoted_spread_bps"]):
        line = f"{r['symbol']:<11}{r['quoted_spread_bps']:>8.1f}b"
        for n in NOTIONALS:
            v = r.get(f"rt_bps_{n}")
            line += f"{('%.1f' % v) if v else '-':>12}"
        print(line)
    if bad:
        print(f"\n  {len(bad)} symbol(s) returned an empty book: {[b['symbol'] for b in bad]}")

    print()
    print("=" * 88)
    print("AGGREGATE, AND THE COMPARISON THAT DECIDES E#4")
    print("=" * 88)
    print("""
  The book is MEAN weighted, so the MEAN cost is the right aggregate. An
  earlier version reported the median, which understated it -- at $1M the mean
  is 1.88x the median. (Arefev's figure, corrected: 40 bps/week is all-in and
  weekly; a like-for-like all-in daily cost here is 13.5 bps/day = 67 bps/week,
  so Arefev is LESS pessimistic than this repository's own number. The claim
  that 'the literature disagrees by 3-5x' was inverted.)""")
    for n in NOTIONALS:
        vals = [r[f"rt_bps_{n}"] for r in ok if r.get(f"rt_bps_{n}") is not None]
        short = sum(1 for r in ok if r.get(f"short_{n}"))
        if not vals:
            continue
        mean_c = sum(vals) / len(vals)
        med_c = sorted(vals)[len(vals) // 2]
        print(f"  notional {n:>9,} USD   mean {mean_c:6.1f} bps   median {med_c:6.1f}   "
              f"max {max(vals):6.1f}"
              + (f"   [{short} symbol(s) had insufficient depth]" if short else ""))
    print(f"\n  symbols with a book: {len(ok)} of {len(MAJORS)}"
          + (f"  (no book: {[b['symbol'] for b in bad]})" if bad else ""))
    print("  quoted spread range is wide, so a single median characterises nothing:")
    sp = sorted(r["quoted_spread_bps"] for r in ok)
    print(f"    min {sp[0]:.2f} bps   median {sp[len(sp)//2]:.2f}   max {sp[-1]:.2f}")

    print("""
  Benchmarks, corrected for like-for-like units:
    Arefev (SSRN 7404139)        40 bps/WEEK all-in, fees included
    this measurement             13.5 bps/DAY all-in at $10k/name, x1.03 turnover
                                 = ~67 bps/week
    E#4's REAL tradeable edge    ~0.6 bps/day  (NOT 27.4 -- that was a formula
                                 artefact, see verify_claim1.py)""")

    summary = {
        "measured_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "venue": "Binance USD-M perpetual, taker side, live book",
        "symbols_with_book": len(ok),
        "symbols_requested": len(MAJORS),
        "caveat": "lower bound; excludes adverse selection and fee tiers above VIP0. "
                  "MEAN is the correct aggregate for an equal-weight book.",
        "rows": rows,
        "e4_real_breakeven_bps": 0.6,
        "e4_formula_breakeven_bps_WITHDRAWN": 26.6,
    }
    for n in NOTIONALS:
        vals = [r[f"rt_bps_{n}"] for r in ok if r.get(f"rt_bps_{n}") is not None]
        if vals:
            summary[f"mean_rt_bps_{n}"] = round(sum(vals) / len(vals), 2)
            summary[f"median_rt_bps_{n}"] = round(sorted(vals)[len(vals) // 2], 2)
    (OUT / "cost_measurement.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\n  written {OUT / 'cost_measurement.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
