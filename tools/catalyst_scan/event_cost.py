"""Event-trade execution cost, funding drag, and break-even move.

The user reframed the catalyst scan: they want EVENT ARBITRAGE with a hold of
under 30 days, and they will use leverage. That changes which number decides the
trade. For a multi-week event trade on a $500 account:

  1. the round trip is no longer a rounding error - it is a fixed toll on the
     target move, and it is the same in dollars whether the account is $500 or
     $500,000, so leverage multiplies its bite;
  2. FUNDING is a second, larger, and completely separate toll that only exists
     because they asked for leverage. Over 30 days at 10x it can exceed the
     entire round trip;
  3. what actually decides the trade is the BREAK-EVEN MOVE: how far the price
     must travel to clear (1) + (2). If that is large next to the realistic
     event move, there is no trade regardless of how good the catalyst looks.

This measures all three from live Binance USD-M books. The book walk is
borrowed from tools/cross_sectional/measure_cost.py, which is this repository's
existing, already-audited implementation (including its partial-fill guard).

NOT a backtest. It is a measurement of today's quoted cost with no dependence on
a window and nothing to overfit.
"""
from __future__ import annotations

import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent / "out"
UA = {"User-Agent": "freqtrade-event-cost/1.0"}

# $500 account at 1x/5x/10x, plus one institutional-ish size for calibration
NOTIONALS = (500, 2_500, 5_000, 10_000, 50_000)

# The event-trade shortlist: the only dated catalyst, and the dated SUPPLY events
# that the long framework rejected as VETO-5 but that a short-horizon book can
# actually trade.
SYMBOLS = {
    "AEROUSDT": "LONG candidate - seven-chain launch 2026-10-21 20:00 EDT (primary src)",
    "ENAUSDT":  "SHORT candidate - ~1.5B ENA (~14.3% of float) unlock 2026-10-05",
    "SEIUSDT":  "SHORT candidate - 113.0M SEI (~$5.53M) unlock 10-15 and 11-15",
    "2ZUSDT":   "SHORT candidate - 47.7% of float unlock 2026-10-02",
    "KNTQUSDT": "LONG candidate - Elysium mainnet ~10-20 (L4, no primary date)",
    "LITUSDT":  "SHORT candidate - weekly unlock 1.28% of float per week",
    "AVAUSDT":  "LONG candidate - monthly buyback, no discrete event date",
    "BTCUSDT":  "reference - the benchmark for what a liquid book looks like",
}
HOLD_DAYS = 30


def get(url: str, tries: int = 3):
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(str(last))


def crossing_cost(levels, notional: float):
    """Walk the book for `notional` USD. Returns (vwap, levels, filled)."""
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


def measure(sym: str) -> dict:
    row = {"symbol": sym, "note": SYMBOLS.get(sym, "")}
    try:
        book = get(f"https://fapi.binance.com/fapi/v1/depth?symbol={sym}&limit=1000")
    except Exception as exc:  # noqa: BLE001
        row["error"] = f"depth fetch failed: {exc}"
        return row
    if "bids" not in book or "asks" not in book:
        row["error"] = f"no book (unknown symbol or throttled): {str(book)[:100]}"
        return row
    bids = [(float(p), float(q)) for p, q in book["bids"]]
    asks = [(float(p), float(q)) for p, q in book["asks"]]
    best_bid, best_ask = bids[0][0], asks[0][0]
    mid = (best_bid + best_ask) / 2
    row["mid"] = mid
    row["spread_bps"] = round((best_ask - best_bid) / mid * 1e4, 2)

    for n in NOTIONALS:
        bv, ua, oka = crossing_cost(asks, n)
        sv, ub, okb = crossing_cost(bids, n)
        if not (oka and okb):
            # A partial fill must never be reported as a complete one: it
            # silently understates the cost, which is the exact failure this
            # repo has been bitten by before.
            row[f"rt_bps_{n}"] = None
            row[f"book_depth_{n}"] = f"INSUFFICIENT (asked {ua}, bid {ub} levels)"
            continue
        row[f"rt_bps_{n}"] = round((bv - sv) / mid * 1e4, 2)
        row[f"book_depth_{n}"] = f"{ua}/{ub}"

    # --- funding: the toll that exists ONLY because of leverage -------------
    try:
        prem = get(f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={sym}")
        rate = float(prem.get("lastFundingRate", 0) or 0)
        row["funding_8h_pct"] = rate * 100
        # 3 funding periods per day
        row["funding_30d_pct_notional"] = rate * 3 * HOLD_DAYS * 100
        for lev in (5, 10):
            row[f"funding_30d_pct_margin_L{lev}"] = rate * 3 * HOLD_DAYS * 100 * lev
    except Exception as exc:  # noqa: BLE001
        row["funding_error"] = str(exc)

    # --- the number that actually decides the trade -------------------------
    # UNIT DISCIPLINE: round trip arrives in BPS, funding arrives in PERCENT.
    # Adding them directly produced a break-even ~9x too large on the first
    # version of this file - the same "a comparison silently became a different
    # one" family AGENTS.md section 3 records. Convert to percent first.
    TAKER_RT_PCT = 0.10  # VIP0 = 5 bps/side = 10 bps round trip
    rt = row.get("rt_bps_5000")
    if rt is not None and "funding_30d_pct_notional" in row:
        rt_pct = rt / 100.0
        row["rt_pct_5000"] = round(rt_pct, 4)
        row["fees_pct"] = TAKER_RT_PCT
        # funding is positive => longs pay shorts
        row["be_long_pct"] = round(rt_pct + max(row["funding_30d_pct_notional"], 0.0)
                                   + TAKER_RT_PCT, 3)
        row["be_short_pct"] = round(rt_pct + max(-row["funding_30d_pct_notional"], 0.0)
                                    + TAKER_RT_PCT, 3)
    return row


def main() -> None:
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with ThreadPoolExecutor(max_workers=4) as ex:
        rows = list(ex.map(measure, SYMBOLS))

    lines = [
        "=" * 108,
        "EVENT-TRADE EXECUTION COST, Binance USD-M perpetuals (live book)",
        f"  {stamp}   hold assumption: {HOLD_DAYS} days",
        "=" * 108,
        "",
        "  Round trip = walk-the-book cost to enter AND exit the same notional.",
        "  It EXCLUDES taker fees (VIP0 = 5 bps/side = 10 bps round trip, added below)",
        "  and excludes adverse selection while the order works.",
        "",
    ]
    hdr = (f"{'symbol':<10s}{'spread':>8s}" + "".join(
        f"{'RT@$' + format(n, ','):>10s}" for n in NOTIONALS)
        + f"{'fund8h%':>9s}{'fund30d%':>10s}{'L10x%':>8s}{'BE long%':>10s}{'BE short%':>11s}")
    lines += [hdr, "-" * len(hdr)]
    for r in rows:
        if "error" in r:
            lines.append(f"{r['symbol']:<10s}  ERROR: {r['error'][:70]}")
            continue
        cells = f"{r['symbol']:<10s}{r.get('spread_bps', float('nan')):>8.2f}"
        for n in NOTIONALS:
            v = r.get(f"rt_bps_{n}")
            cells += f"{('n/a' if v is None else format(v, '.1f')):>10s}"
        cells += (f"{r.get('funding_8h_pct', float('nan')):>9.4f}"
                  f"{r.get('funding_30d_pct_notional', float('nan')):>10.3f}"
                  f"{r.get('funding_30d_pct_margin_L10', float('nan')):>8.2f}"
                  f"{r.get('be_long_pct', float('nan')):>10.3f}"
                  f"{r.get('be_short_pct', float('nan')):>11.3f}")
        lines.append(cells)

    lines += ["", "  RT = round trip in bps (enter + exit, walk the book, NO fees).",
              "  fund30d% = funding over 30 days as % of NOTIONAL (positive = longs pay).",
              "  L10x%    = the same funding as % of MARGIN at 10x.",
              "  BE = break-even move the price must travel to clear round trip +",
              "       funding + 10 bps VIP0 taker fees, before any edge.",
              "",
              "  *** LEVERAGE DOES NOT CHANGE THE BE. Both the move and the funding",
              "      scale linearly with notional, so the ratio is identical at 1x and",
              "      10x. What leverage changes is LIQUIDATION RISK, not economics. ***",
              ""]
    lines.append("  Book depth actually available (ask levels/bid levels consumed):")
    for r in rows:
        if "error" in r:
            continue
        bits = [f"${format(n, ',')}={r.get(f'book_depth_{n}', '-')}"
                for n in NOTIONALS]
        lines.append(f"    {r['symbol']:<10s} " + "  ".join(bits))
        if r.get("note"):
            lines.append(f"               -> {r['note']}")

    txt = "\n".join(lines)
    (OUT / "event_cost.md").write_text(txt, encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
