"""Reconcile +0.043R against +0.139R — the number that decides stop vs continue.

Two different quantities were in play and were being used as if interchangeable:

  +0.139R  the out-of-sample 2025 split alone (464 trades)
  +0.043R  the full sample, all four splits pooled (1,690 trades)

The literature review flagged this as the single decision-critical item, and
it is right.  The question is which one a *future* test should be powered on.

The answer is not simply "pooled", because the pooled estimate has a wide
interval and the 2025 figure is inside it.  So this computes:

  1. The confidence interval on the pooled edge, and the power required at the
     LOWER, CENTRE and UPPER ends of it.  That brackets the decision under
     every defensible assumption about the true edge.
  2. The empirical skew and kurtosis of the trade sequence.  A 1R stop / 2R
     target bracket is a capped-gain, bounded-loss payoff and generates
     negative skew structurally, which makes any normality-based power
     calculation optimistic (Bailey & Lopez de Prado 2012, Sharpe Efficient
     Frontier).
  3. A check that the 4h controls really do share SHARK-01's exit bracket.  A
     control measured on a different risk footing is not a control, and a 20x
     gap between SHARK-01 and the momentum baseline is exactly the size of gap
     that should be checked before believing it.
"""

from __future__ import annotations

import json
import math
import time

import numpy as np
import pandas as pd
from scipy import stats

from . import config as C
from .backtest.costs import CostModel
from .backtest.engine import run_backtest
from .runner import get_dataset, git_commit, write_frame, write_manifest
from .strategies.recipes import BASELINES, STRATEGIES, build_spec
from .validation.feasibility import deflated_feasibility

ALPHA, POWER = 0.05, 0.80
Z = stats.norm.ppf(1 - ALPHA / 2) + stats.norm.ppf(POWER)


def required_n(edge: float, std: float) -> float:
    if edge <= 0 or std <= 0:
        return float("inf")
    return float(math.ceil((Z * std / edge) ** 2))


def main() -> int:
    t0 = time.time()
    frames, control_trades = [], {}
    for sym in C.UNIVERSE:
        df = get_dataset(sym, "4h").frame
        for name, recipe in (("SHARK-01", STRATEGIES["SHARK-01"]),
                             ("BASELINE-E-TSM", BASELINES["BASELINE-E-TSM"]),
                             ("BASELINE-C-BREAKOUT", BASELINES["BASELINE-C-BREAKOUT"])):
            spec = build_spec(df, recipe, time_stop_bars=C.DEFAULT_TIME_STOP_BARS["4h"])
            res = run_backtest(df, spec, symbol=sym, timeframe="4h",
                               costs=CostModel.for_symbol(sym))
            if res.trades.empty:
                continue
            control_trades.setdefault(name, []).append(res.trades)
            if name == "SHARK-01":
                frames.append(res.trades)
    t = pd.concat(frames, ignore_index=True)
    r = t["r_net"].dropna().to_numpy()

    edge, std, n = float(r.mean()), float(r.std(ddof=1)), len(r)
    se = std / math.sqrt(n)
    lo, hi = edge - 1.96 * se, edge + 1.96 * se
    tstat = edge / se
    years = (t["exit_time"].max() - t["exit_time"].min()).days / 365.25
    per_year = n / years

    print("=" * 76)
    print("RECONCILIATION: which edge size should power a forward test?")
    print("=" * 76)
    print(f"\npooled edge {edge:+.4f}R   sd {std:.3f}R   n {n:,}   "
          f"se {se:.4f}R   t {tstat:+.2f}")
    print(f"95% CI on the edge: [{lo:+.4f}R, {hi:+.4f}R]")

    oos = t[t["split"] == "oos"]
    print(f"2025 split alone : {oos['r_net'].mean():+.4f}R on {len(oos):,} trades "
          f"(the best of four splits)")

    rows = []
    print(f"\n{'assumption':<34} {'edge R':>9} {'trades needed':>15} {'years @9sym':>12}")
    print("-" * 76)
    for label, e in (("lower 95% bound", lo), ("pooled point estimate", edge),
                     ("upper 95% bound", hi), ("2025 split (best of 4)", oos["r_net"].mean())):
        need = required_n(e, std)
        yrs = need / per_year
        rows.append({"assumption": label, "edge_r": e, "trades_needed": need,
                     "years_at_9_symbols": yrs})
        ns = f"{need:,.0f}" if np.isfinite(need) else "never"
        ys = f"{yrs:,.1f}" if np.isfinite(yrs) else "never"
        print(f"{label:<34} {e:>+9.4f} {ns:>15} {ys:>12}")
    write_frame(pd.DataFrame(rows), "phase8_edge_reconciliation")

    # --- non-normality -----------------------------------------------------
    skew = float(stats.skew(r))
    kurt = float(stats.kurtosis(r, fisher=False))
    print(f"\ntrade-return skew {skew:+.3f}   non-excess kurtosis {kurt:.3f}")
    if skew < -0.5:
        print("  negative skew, as a capped-gain/bounded-loss bracket should be.")
        print("  normality-based power is therefore OPTIMISTIC; the true")
        print("  requirement is larger than the table above.")

    # --- are the controls on the same risk footing? ------------------------
    print("\n--- control risk-footing check ---")
    foot = []
    for name, lst in control_trades.items():
        tt = pd.concat(lst, ignore_index=True)
        m = tt[tt["split"] == "oos"]
        foot.append({
            "strategy": name, "trades_oos": len(m),
            "mean_r": float(m["r_net"].mean()),
            "mean_gross_r": float(m["r_gross"].mean()),
            "hit_rate": float((m["r_net"] > 0).mean()),
            "pct_stop": float((tt["exit_reason"] == "stop").mean()),
            "pct_target": float((tt["exit_reason"] == "target").mean()),
            "pct_time": float((tt["exit_reason"] == "time_stop").mean()),
            "atr_stop": float(tt["atr_stop"].iloc[0]),
            "r_multiple": float(tt["r_multiple"].iloc[0]),
        })
        f = foot[-1]
        print(f"  {name:<22} stop {f['atr_stop']:.1f}ATR / {f['r_multiple']:.1f}R  "
              f"exit mix {f['pct_stop']:.0%}/{f['pct_target']:.0%}/{f['pct_time']:.0%}  "
              f"hit {f['hit_rate']:.1%}  mean {f['mean_r']:+.4f}R")
    write_frame(pd.DataFrame(foot), "phase8_control_risk_footing")
    s1 = next(f for f in foot if f["strategy"] == "SHARK-01")
    same = all(abs(f["atr_stop"] - s1["atr_stop"]) < 1e-9
               and abs(f["r_multiple"] - s1["r_multiple"]) < 1e-9 for f in foot)
    print(f"\n  identical exit bracket across all three: {same}")

    d = deflated_feasibility(edge, std, trials=41_472)
    print(f"\ndeflated view on the pooled estimate: observed Sharpe "
          f"{d['observed_sharpe_per_trade']:.4f} vs luck bar "
          f"{d['luck_benchmark_sharpe']:.4f} -> "
          f"{'detectable' if d['detectable_at_any_n'] else 'UNDEFINED at any n'}")

    write_manifest({
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"), "git_commit": git_commit(),
        "pooled_edge_r": edge, "se_r": se, "ci95": [lo, hi], "t_stat": tstat,
        "oos_2025_edge_r": float(oos["r_net"].mean()),
        "trades_per_year": per_year, "skew": skew, "kurtosis": kurt,
        "controls_share_bracket": same,
        "reconciliation": rows,
        "conclusion": (
            "The 2025 figure is the best of four splits and is inside the pooled "
            "95% CI, so it is not evidence of a larger edge. Even powering on the "
            "UPPER bound of the interval requires a multi-year forward test. "
            "The stop recommendation stands; the +0.139R headline should never "
            "have been quoted without its interval."
        ),
    }, "manifest_phase8.json")
    print(f"\nelapsed {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
