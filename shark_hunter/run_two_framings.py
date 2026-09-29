"""Two sample-size framings, stated precisely.

Phase 4 claimed the required sample size was UNDEFINED, so that no forward
test could conclude.  That conclusion survives, but the *reason* was imprecise,
and conflating two framings is exactly the kind of overstatement this project
exists to catch.  Both framings are computed here, separately.

FRAMING A -- the selected result, deflated for having been searched for.
The 4h configuration was chosen after 5m and 1h both failed.  The observed
per-trade Sharpe must beat the Sharpe that pure luck delivers from the 41,472
configurations already examined.  It does not, so the required n is undefined.

FRAMING B -- a fresh, pre-registered test on unseen data.
A pre-registered forward test involves no cherry-picking: the rule was frozen
before the data existed, so there is no selection to deflate for.  The bar is
simply zero, and the required n is finite.

Both are computed.  The honest summary is that the conclusion is unchanged --
infeasible under either -- but the numbers differ by a factor of ~18 and the
report should say so.
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
from .strategies.recipes import STRATEGIES, build_spec
from .validation.feasibility import expected_max_sharpe

N_TRIALS = 41_472
ALPHA, POWER = 0.05, 0.80


def framing_b(edge: float, std: float) -> dict:
    """Fresh pre-registered test: bar is zero, required n is finite."""
    z = stats.norm.ppf(1 - ALPHA / 2) + stats.norm.ppf(POWER)
    n = int(math.ceil((z * std / edge) ** 2))
    return {"required_trades": n, "bar_sharpe": 0.0,
            "observed_sharpe": edge / std, "detectable": True}


def framing_a(edge: float, std: float, trials: int) -> dict:
    """Selected result: bar is the luck benchmark, required n may be undefined."""
    sr = edge / std
    luck = expected_max_sharpe(trials)
    z = stats.norm.ppf(1 - ALPHA / 2) + stats.norm.ppf(POWER)
    deficit = sr - luck
    return {"required_trades": int(math.ceil((z / deficit) ** 2)) if deficit > 0 else None,
            "bar_sharpe": luck, "observed_sharpe": sr,
            "detectable": bool(deficit > 0)}


def main() -> int:
    t0 = time.time()
    frames = []
    for sym in C.UNIVERSE:
        df = get_dataset(sym, "4h").frame
        spec = build_spec(df, STRATEGIES["SHARK-01"],
                          time_stop_bars=C.DEFAULT_TIME_STOP_BARS["4h"])
        r = run_backtest(df, spec, symbol=sym, timeframe="4h",
                         costs=CostModel.for_symbol(sym))
        if not r.trades.empty:
            frames.append(r.trades)
    trades = pd.concat(frames, ignore_index=True)
    v = trades["r_net"].dropna()
    edge, std = float(v.mean()), float(v.std())
    years = (trades["exit_time"].max() - trades["exit_time"].min()).days / 365.25
    per_year = len(trades) / years

    b = framing_b(edge, std)
    a = framing_a(edge, std, N_TRIALS)

    print("=" * 74)
    print("SAMPLE SIZE UNDER TWO FRAMINGS")
    print("=" * 74)
    print(f"edge {edge:+.4f}R   dispersion {std:.3f}R   "
          f"{len(trades)} trades over {years:.2f}y ({per_year:.0f}/yr, 9 symbols)")
    print()
    print("A. selected result, deflated for the search that produced it")
    print(f"   observed Sharpe {a['observed_sharpe']:.4f}  vs luck bar "
          f"{a['bar_sharpe']:.4f}  -> required n = "
          f"{a['required_trades'] if a['required_trades'] else 'UNDEFINED'}")
    print()
    print("B. fresh pre-registered test, no selection to deflate for")
    print(f"   bar = 0, required n = {b['required_trades']:,} trades")
    print(f"   at {per_year:.0f} trades/yr  ->  "
          f"{b['required_trades'] / per_year:.1f} years")
    for ns in (9, 50, 100, 170):
        tpy = per_year * ns / 9
        print(f"   at {ns:>3} symbols ({tpy:>6.0f}/yr) -> "
              f"{b['required_trades'] / tpy:5.1f} years")
    print()
    print("CONCLUSION: unchanged. Infeasible under either framing. The phase-4")
    print("report overstated by conflating them -- B is finite at ~"
          f"{b['required_trades'] / per_year:.0f} years, not undefined.")

    rows = [{"framing": "A_selected_deflated", **a},
            {"framing": "B_preregistered", **b}]
    write_frame(pd.DataFrame(rows), "phase5_sample_size_two_framings")
    write_manifest({
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"), "git_commit": git_commit(),
        "edge_r": edge, "std_r": std, "trades_per_year": per_year,
        "n_trials": N_TRIALS, "framing_a": a, "framing_b": b,
        "conclusion": "Infeasible under both framings. Phase 4 conflated them; "
                      "the stop recommendation stands, the stated reason was "
                      "over-strong.",
    }, "manifest_phase5.json")
    print(f"\nelapsed {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
