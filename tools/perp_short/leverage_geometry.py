"""How much leverage can the delivered 4h short book actually carry?

PRE-REGISTERED as L-1 in docs-myself/PREREG_LEVERAGE_2026-09-30.md. Read the
gates there first.

The question matters because the user asked it directly (2026-09-27) and got
"leverage accelerates loss". That answer was measured on a 5m strategy whose
GROSS was approximately zero and whose fees were 99.2% of the loss. This book
is not that strategy: F-1 measured gross 0.0397R per trade against 0.0040R of
costs, an edge 9.8x its own cost. So the leverage question has never been
answered for the thing that is actually being deployed.

The answer is GEOMETRIC, not optimisable. A perpetual's liquidation price
depends only on leverage and the maintenance-margin rate - NOT on position size
- and this book risk-sizes every position off the same 4xATR stop, so sizing
cannot rescue a bad geometry:

    short at leverage L, maintenance margin rate mm:
        liquidation ~= entry * (1 + 1/L - mm)
        stop         =  entry * (1 + stop_pct)
        stop is reachable  <=>  stop_pct < 1/L - mm
                             <=>  L < 1 / (stop_pct + mm)

That is closed-form, per trade, per symbol, and needs no backtest. Gate L3 asks
what share of executed trades still have a reachable stop; below 95% a leverage
level is unusable and that is reported, not dropped.

t IS INVARIANT TO POSITION SIZE, so leverage cannot make this strategy
statistically significant. It scales return and drawdown together. The only
thing leverage can legitimately be chosen against is the geometry, which is
exactly what this measures.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\leverage_geometry.py
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from r_stats import tstat  # noqa: E402
from risk_unit import load_with_risk  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RESULTS = [
    ("full/n50", "user_data/sizing_out/full/n50/backtest-result-2026-09-28_21-44-27.zip"),
    ("oos/n50", "user_data/sizing_out/oos/n50/backtest-result-2026-09-28_21-45-26.zip"),
]
LEVERAGES = [1, 2, 3, 5, 8, 10, 15, 20]

# Binance USD-M tier-1 maintenance margin rate. Recorded as a CONSTANT to be
# varied, not silently assumed - it is the other half of the constraint and
# moving it moves the answer.
MMR = 0.004
# Worst measured round-trip cost regime in this repo (RESEARCH_STATE 1b).
COVID_BPS = 34.9
FEE_BPS_PER_SIDE = 5.0  # the backtest's configured fee, 0.0005
ATR_STOP = 4.0          # the frozen stop multiple


def head(t: str) -> None:
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def load(rel: str) -> pd.DataFrame:
    """⚠ CORRECTED 2026-09-30. The first version took the stop distance from
    `initial_stop_loss_ratio`, which is exactly 0.300000 on every trade - the
    CLASS BACKSTOP, not the 4xATR anchor (see `risk_unit.py`). It therefore
    measured a 30% stop and concluded that leverage above 3x is impossible.
    With the real stop (median 10.3%, p90 16.8%, max 37.4%) the answer is
    materially different, and the first answer was the wrong one in the
    conservative direction for the wrong reason."""
    return load_with_risk(rel)


def lmax(stop_pct: float, mmr: float = MMR) -> float:
    """Maximum leverage at which this trade's stop is still reachable."""
    return 1.0 / (stop_pct + mmr)


def liq_price(entry: float, lev: float, mmr: float = MMR) -> float:
    """Liquidation price for a SHORT position, isolated margin."""
    return entry * (1.0 + 1.0 / lev - mmr)


def handcheck() -> None:
    """L2: one hand computation, checked to the cent. If this disagrees with
    liq_price(), nothing below it can be trusted."""
    e, s, lev, mmr = 100.0, 110.0, 5.0, 0.004
    # by hand: 1 + 1/5 - 0.004 = 1.196  -> 119.60
    want = 119.60
    got = liq_price(e, lev, mmr)
    print(f"  hand check: short @ entry {e}, leverage {lev}x, mmr {mmr:.3f}")
    print(f"    liquidation = {e} * (1 + 1/{lev} - {mmr}) = {got:.2f}, "
          f"expected {want:.2f}  ->  {'MATCH' if abs(got-want) < 1e-9 else 'MISMATCH'}")
    assert abs(got - want) < 1e-9, "L2 FAILED: liquidation formula disagrees with hand calc"
    stop_pct = abs(e - s) / e
    print(f"    stop distance {stop_pct*100:.1f}%  ->  L_max = 1/({stop_pct:.3f}+{mmr}) "
          f"= {lmax(stop_pct):.2f}x")
    assert abs(lmax(stop_pct) - 1 / (0.10 + 0.004)) < 1e-9
    # monotonicity: higher leverage -> liquidation closer to entry
    prev = None
    for L in (1, 2, 3, 5, 10, 20):
        v = liq_price(e, L)
        if prev is not None:
            assert v < prev, f"L2 FAILED: liquidation not falling with leverage at L={L}"
        prev = v
    print("    liquidation falls monotonically as leverage rises  ->  OK")


def main() -> int:
    print("LEVERAGE GEOMETRY OF THE DELIVERED 4h SHORT BOOK (prereg L-1)\n")
    print("t is invariant to position size, so leverage cannot make this strategy")
    print("significant. It scales return AND drawdown together. The only thing it")
    print("can be chosen against is whether the stop is reachable at all.\n")

    head("L2  IS THE LIQUIDATION FORMULA RIGHT? (hand-checked, monotonicity-checked)")
    handcheck()

    for label, rel in RESULTS:
        df = load(rel)
        head(f"{label}   ({len(df)} trades, {df['pair'].nunique()} symbols, "
             f"mmr={MMR:.3f})")

        # ---- the distribution that decides everything ----------------------
        # The stop distance IS 4 x ATR, taken from the price panel, not from the
        # recorded stop fields.
        sp = (ATR_STOP * df["atr_pct"]).to_numpy()
        print(f"  stop distance = {ATR_STOP:g} x ATR, as a % of entry:")
        for q in (0.5, 0.75, 0.9, 0.95, 0.99, 1.0):
            print(f"    p{int(q*100):<3} = {np.percentile(sp, q*100)*100:6.2f}%")
        print(f"    mean {sp.mean()*100:.2f}%   ->  implied L_max mean "
              f"{np.mean([lmax(x) for x in sp]):.2f}x, "
              f"WORST {min(lmax(x) for x in sp):.2f}x")

        # ---- the frontier --------------------------------------------------
        # ---- the frontier --------------------------------------------------
        # UNIT DISCIPLINE. Fees are charged on NOTIONAL. This book risk-sizes
        # every position (notional = risk / (4*atr_pct)), so at higher leverage
        # the notional per trade is UNCHANGED and only the margin posted falls.
        # Fees in R are therefore INVARIANT to leverage, unless the freed
        # margin is deliberately redeployed into L times as many positions - in
        # which case BOTH fees and variance scale by L and nothing is gained but
        # capital efficiency. The first version of this script printed an "equity
        # fee/yr" column that scaled with L and compared USDT against R.
        years = (df["close"].max() - df["open"].min()).total_seconds() / (365.25 * 86400)
        gross_R = df["gross_R"].mean()
        fee_R = df["fee_R"].mean()
        fund_R = df["funding_R"].mean()
        print(f"  sample length {years:.2f} y, {len(df)/years:.0f} trades/yr, "
              f"mean notional {df['stake'].mean():,.0f} USDT")
        print(f"  gross {gross_R:+.4f}R/trade, fee {fee_R:.4f}R, funding "
              f"{fund_R:+.4f}R -> costs are {100*(fee_R+fund_R)/gross_R:.1f}% of gross\n")
        print(f"  {'L':>4}{'stop reachable':>16}{'sym>=90%':>10}{'L3':>7}"
              f"{'L4':>7}{'worst L_max':>13}{'cost/gross':>13}")

        verdicts = []
        for L in LEVERAGES:
            reach = (sp < (1.0 / L - MMR))
            frac = float(reach.mean())
            per = df.assign(ok=reach).groupby("pair")["ok"].mean()
            l4 = bool((per >= 0.90).all())
            l3 = frac >= 0.95
            l6 = (fee_R + fund_R) / gross_R < 1.0
            verdicts.append((L, frac, l4, l3, l6))
            print(f"  {L:>4}{frac*100:>15.1f}%{int((per>=0.90).sum()):>7}/{len(per)}"
                  f"{'  PASS' if l3 else '  FAIL':>7}"
                  f"{'  PASS' if l4 else '  FAIL':>7}"
                  f"{min(lmax(x) for x in sp):>12.2f}x"
                  f"{(fee_R+fund_R)/gross_R*100:>12.1f}%")

        print(f"\n  the cost column does not move with L and cannot: fees are a "
              f"fraction of notional,\n  and the notional is set by the risk rule, "
              f"not by the exchange leverage.")

        best = [v for v in verdicts if v[2] and v[3]]
        top = max(best)[0] if best else None
        print(f"\n  highest leverage passing L3+L4: {top if top else 'NONE'}x")
        if top:
            bad = (df.assign(ok=sp < (1.0 / top - MMR)).groupby("pair")["ok"].mean())
            bad = bad[bad < 0.90].sort_values()
            if len(bad):
                print(f"  symbols dropped at {top}x: {len(bad)}  worst: "
                      + ", ".join(f"{p} {m*100:.0f}%" for p, m in bad.head(5).items()))
            else:
                print(f"  no symbol drops below 90% at {top}x")
            lm = np.array([lmax(x) for x in sp])
            tight = df.assign(lmax=lm).nsmallest(5, "lmax")
            print(f"  the 5 tightest trades: "
                  + ", ".join(f"{r.pair.split('/')[0]} {r.lmax:.2f}x"
                               for r in tight.itertuples()))

        # ---- what does the sample's own t say about this? -------------------
        r = df["R"].to_numpy()
        t, m, n_eff, iat = tstat(r)
        print(f"\n  for scale: per-trade R mean {m:+.4f}, t = {t:+.2f} "
              f"(n_eff {n_eff}, IAT {iat:.2f}).")
        print(f"  **that t is the SAME at 1x and at 20x.** Leverage does not appear "
              f"in it.\n"
              f"  A higher backtest return at higher leverage is the same edge "
              f"scaled by a bigger number,\n  with the drawdown scaled by the same "
              f"number. It is a risk choice, not a better strategy.")

    head("WHAT THIS DOES AND DOES NOT SETTLE")
    print("""  SETTLES: the maximum leverage at which the 4xATR stop is still reachable.
           That is a hard, closed-form, per-trade constraint and it is now measured
           on the real stop distribution, not on the class backstop.

  DOES NOT SETTLE: whether the edge is real. It is not, statistically - t ~ 0.6.
           Leveraging an unproven edge does not prove it; it multiplies the
           variance of the outcome by L^2 while the mean goes up by L.

  IT DOES NOT CHANGE: the deployed operating point, which remains N=40 at 0.5%
           risk per trade. Nothing here reopens STOP_MULTIPLE, the universe, or
           the signal.""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
