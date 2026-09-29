"""Reduce the corrected leverage matrix to report tables, and check the invariants
that make the matrix mean what it claims to mean."""

from __future__ import annotations

import json
import zipfile
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "user_data" / "matrix"
LEVS = (1, 2, 5, 10, 20)


def load(z: Path) -> dict:
    with zipfile.ZipFile(z) as zf:
        n = next(x for x in zf.namelist() if x.endswith(".json") and "meta" not in x)
        d = json.loads(zf.read(n))["strategy"]
    return d[next(iter(d))]


def buy_and_hold() -> list[tuple]:
    import statistics
    import pandas as pd

    cfg = json.loads((REPO / "user_data" / "config_wide_ft.json").read_text(encoding="utf-8"))
    pairs = cfg["exchange"]["pair_whitelist"]
    out = []
    for p in pairs:
        # pair_to_filename keeps the settlement: BTC/USDT:USDT -> BTC_USDT_USDT
        sym = p.replace("/", "_").replace(":", "_")
        # this is the file the backtester actually reads: datadir/futures/<pair>-<tf>-futures
        f = OUT.parent / "data" / "wide_ft" / "futures" / f"{sym}-4h-futures.feather"
        df = pd.read_feather(f)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")
        lo, hi = df["date"].iloc[0], df["date"].iloc[-1]
        # equal-weight buy&hold, rebalanced to equal notional at the start
        r = df["close"] / df["open"].iloc[0] - 1
        out.append((p, r.iloc[-1] * 100, lo, hi))
    return out


def main() -> None:
    rows = json.loads((OUT / "summary_corrected.json").read_text(encoding="utf-8"))
    by = {(r["stake_mode"], r["side"], r["lev_req"]): r for r in rows}

    print("=" * 110)
    print("1. INVARIANT: is the PRICE stop held at ~3.6% in every cell?")
    print("     (min is the exchange tick-size rounding of 0.036, not a smaller stop)")
    print("=" * 110)
    print(f"{'mode':10s} {'side':6s} {'lev':>4s} {'trades':>7s} {'px stop min':>12s} "
          f"{'px stop max':>12s} {'leverage actually used'}")
    bad = 0
    for mode in ("unlimited", "fixed"):
        for side in ("short", "long"):
            for lev in LEVS:
                r = by[(mode, side, lev)]
                lo, hi = r["px_stop_min"], r["px_stop_max"]
                la = r["lev_actual"]
                ok = abs(lo - 0.036) < 2e-3 and abs(hi - 0.036) < 1e-9
                bad += 0 if ok else 1
                print(f"{mode:10s} {side:6s} {lev:4d} {r['trades']:7d} {lo:12.6f} "
                      f"{hi:12.6f} {la}{'' if ok else '   <-- NOT 3.6%'}")
    print(f"\n-> cells whose price stop != 3.6% (tolerance 2e-3 for tick rounding): {bad} / {len(rows)}")

    for mode in ("unlimited", "fixed"):
        for side in ("short", "long"):
            print()
            print("=" * 110)
            print(f"2. {mode.upper()} / {side.upper()}")
            print("=" * 110)
            print(f"{'lev':>4s} {'trades':>7s} {'peak':>5s} {'win%':>6s} {'total%':>8s} "
                  f"{'CAGR%':>7s} {'SR(t)':>6s} {'SR(w)':>6s} {'DD%':>7s} {'PF':>5s} "
                  f"{'funding':>9s} {'stoploss%':>9s} {'target%':>8s} {'time%':>6s}")
            for lev in LEVS:
                r = by[(mode, side, lev)]
                ex = r["exit_reasons"]
                n = r["trades"]
                pct = lambda k: 100 * ex.get(k, 0) / n
                print(f"{lev:4d} {n:7d} {r['peak_concurrent']:5d} {r['winrate']*100:6.1f} "
                      f"{r['total_pct']:8.2f} {r['cagr']:7.2f} {r['sharpe_trades']:6.2f} "
                      f"{(r['sharpe_wallet'] or 0):6.2f} {r['maxdd_pct']:7.2f} {r['pf']:5.2f} "
                      f"{r['funding']:9,.0f} {pct('stop_loss'):9.1f} {pct('target_2r'):8.1f} "
                      f"{pct('time_stop'):6.1f}")

    print()
    print("=" * 110)
    print("3. CLEAN LEVERAGE SCALING (fixed stake): return / naive L x 1x return")
    print("=" * 110)
    for side in ("short", "long"):
        base = by[("fixed", side, 1)]["total_pct"]
        print(f"  {side}: 1x = {base:+.2f}%")
        for lev in (2, 5, 10, 20):
            r = by[("fixed", side, lev)]
            naive = base * lev
            print(f"    {lev:2d}x actual {r['total_pct']:+8.2f}%   naive {naive:+8.2f}%   "
                  f"ratio {(r['total_pct']/naive if naive else float('nan')):5.2f}   "
                  f"DD {r['maxdd_pct']:5.2f}%  SR(w) {(r['sharpe_wallet'] or 0):5.2f}")

    print()
    print("=" * 110)
    print("4. PER-YEAR P&L (unlimited/short), USDT on a 100k wallet")
    print("=" * 110)
    yrs = by[("unlimited", "short", 1)]["yearly"]
    bal = 100000.0
    print(f"{'year':6s} {'PnL USDT':>11s} {'year-end bal':>14s} {'ret%':>8s}")
    for y, p in yrs.items():
        bal += p
        print(f"{y:6s} {p:11,.0f} {bal:14,.0f} {100*p/100000:8.2f}")
    print(f"\n  1x  long, same window:")
    for y, p in by[("unlimited", "long", 1)]["yearly"].items():
        print(f"    {y}: {p:+,.0f}")

    print()
    print("=" * 110)
    print("5. BUY & HOLD, same 24 pairs, same 4h file window")
    print("=" * 110)
    bh = buy_and_hold()
    import statistics
    vals = sorted(x[1] for x in bh)
    for p, r, lo, hi in sorted(bh, key=lambda x: -x[1])[:5]:
        print(f"   {p:18s} {r:+8.1f}%")
    print("   ...")
    for p, r, lo, hi in sorted(bh, key=lambda x: -x[1])[-3:]:
        print(f"   {p:18s} {r:+8.1f}%")
    print(f"\n  n={len(bh)}  equal-weight {sum(vals)/len(vals):+.1f}%  "
          f"median {statistics.median(vals):+.1f}%  "
          f"positives {sum(1 for v in vals if v > 0)}/{len(vals)}")
    print(f"  window {min(x[2] for x in bh).date()} -> {max(x[3] for x in bh).date()}")

    print()
    print("=" * 110)
    print("6. RUIN: what actually breaks at high leverage (fixed stake = 4000 collateral/trade)")
    print("=" * 110)
    print(f"{'side':6s} {'lev':>4s} {'maxLossStreak':>14s} {'cap@risk USDT':>14s} "
          f"{'loss/stop%':>11s} {'feeDrag/trade%':>14s} {'feeDrag vs 3.6% stop':>21s}")
    for side in ("short", "long"):
        for lev in LEVS:
            r = load(OUT / "fixed" / f"{side}_lev{lev}.zip")
            t = r["trades"]
            streak = mx = 0
            for tr in sorted(t, key=lambda x: x["close_date"]):
                streak = 0 if tr["profit_abs"] > 0 else streak + 1
                mx = max(mx, streak)
            cap = r["avg_stake_amount"] * 24
            loss_pct = 0.036 * lev * 100
            fee_drag = 0.001 * lev * 100
            print(f"{side:6s} {lev:4d} {mx:14d} {cap:14,.0f} {loss_pct:11.1f} "
                  f"{fee_drag:14.1f} {fee_drag/3.6*100:20.0f}%")

    print()
    print("=" * 110)
    print("7. LEVERAGE vs BUY & HOLD, same window, equal-weight 24 perps")
    print("=" * 110)
    eq = sum(x[1] for x in bh) / len(bh)
    print(f"  buy&hold 1x = {eq:+.1f}%   then 1x/L applied at leverage L:")
    for lev in LEVS:
        s = by[("fixed", "short", lev)]["total_pct"]
        s20 = by[("unlimited", "short", lev)]["total_pct"]
        bl = eq * lev
        print(f"    {lev:2d}x  strategy(fixed) {s:+9.2f}%   strategy(unlimited) {s20:+9.2f}%   "
              f"buy&hold {bl:+9.1f}%   strat/BH {s/bl:5.2f}x")


if __name__ == "__main__":
    main()
