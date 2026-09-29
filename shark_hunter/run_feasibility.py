"""Can this hypothesis ever be settled? A feasibility check, run before
committing to anything.

    python -m shark_hunter.run_feasibility

Phase 3 recommended a 12-month forward test.  This module exists to check
whether that recommendation was sound **before** anyone spends the year, and
it is not.  It says the recommendation was wrong, in public, with the
arithmetic attached.
"""

from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

from . import config as C
from .backtest.costs import CostModel
from .backtest.engine import run_backtest
from .runner import get_dataset, git_commit, write_frame, write_manifest
from .strategies.recipes import STRATEGIES, build_spec
from .validation.feasibility import (assess, deflated_feasibility,
                                     expected_max_sharpe, inflate_for_multiple_testing,
                                     required_trades)

N_TRIALS = 41_472          # carried forward from phase 2/3, search-inclusive
SYMBOL_BREADTH = (9, 25, 50, 100, 170)


def _trades_for(symbol: str, timeframe: str):
    df = get_dataset(symbol, timeframe).frame
    spec = build_spec(df, STRATEGIES["SHARK-01"],
                      time_stop_bars=C.DEFAULT_TIME_STOP_BARS[timeframe])
    return run_backtest(df, spec, symbol=symbol, timeframe=timeframe,
                        costs=CostModel.for_symbol(symbol)).trades


def main() -> int:
    t0 = time.time()
    print("=" * 78)
    print("FEASIBILITY: can a forward test ever settle this hypothesis?")
    print("=" * 78)

    frames = [t for t in (_trades_for(s, "4h") for s in C.UNIVERSE) if not t.empty]
    trades = pd.concat(frames, ignore_index=True)
    r = trades["r_net"].dropna()
    edge, std = float(r.mean()), float(r.std())
    years = (trades["exit_time"].max() - trades["exit_time"].min()).days / 365.25
    per_year = len(trades) / years

    print(f"\nobserved edge      : {edge:+.4f} R per trade")
    print(f"per-trade dispersion: {std:.3f} R")
    print(f"signal / noise     : {edge / std:.4f}   <- edge as a fraction of one trade's spread")
    print(f"trades             : {len(trades):,} over {years:.2f}y  ({per_year:.0f}/yr, 9 symbols)")

    # --- the exact statement ------------------------------------------------
    d = deflated_feasibility(edge, std, trials=N_TRIALS)
    print("\n--- deflated test (exact) " + "-" * 43)
    print(f"observed Sharpe per trade : {d['observed_sharpe_per_trade']:.4f}")
    print(f"luck benchmark, {N_TRIALS:,} trials : {d['luck_benchmark_sharpe']:.4f}")
    print(f"deficit                   : {d['deficit']:+.4f}")
    if d["detectable_at_any_n"]:
        print(f"trades needed             : {d['trades_needed']:,}")
    else:
        print("trades needed             : UNDEFINED -- the observed Sharpe is below the")
        print("                            luck benchmark, so NO sample size can clear it.")

    # --- the naive arithmetic, for scale ------------------------------------
    need = required_trades(edge, std)
    need_adj = inflate_for_multiple_testing(need, N_TRIALS)
    print("\n--- if the multiple-testing bar were ignored (shown for scale only) " + "-" * 5)
    print(f"trades needed at 80% power : {need:,}")

    rows = []
    for ns in SYMBOL_BREADTH:
        tpy = per_year * ns / 9
        rows.append({"n_symbols": ns, "trades_per_year": tpy,
                     "years_uncorrected": need / tpy,
                     "months_uncorrected": 12 * need / tpy,
                     "years_deflated": need_adj / tpy,
                     "months_deflated": 12 * need_adj / tpy})
    breadth = pd.DataFrame(rows)
    breadth["years_uncorrected"] = breadth["years_uncorrected"].round(1)
    breadth["years_deflated"] = breadth["years_deflated"].round(1)
    write_frame(breadth, "phase4_feasibility_breadth")
    print("\n--- time required, by universe breadth " + "-" * 34)
    print(breadth.to_string(index=False))

    a = assess(edge, std, int(per_year), 9, 50, len(trades), trials=N_TRIALS)
    verdict = a.verdict
    print(f"\nverdict: {verdict}")

    payload = {
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "git_commit": git_commit(),
        "observed_edge_r": edge, "per_trade_std_r": std,
        "signal_to_noise": edge / std,
        "n_trades": int(len(trades)), "years": years, "trades_per_year": per_year,
        "deflated": d, "required_trades_uncorrected": need,
        "required_trades_deflated": need_adj,
        "breadth": breadth.to_dict("records"),
        "verdict": verdict,
        "conclusion": (
            "A 12-month forward test CANNOT settle this hypothesis at any "
            "universe size a retail account can trade. The observed per-trade "
            "Sharpe is below the benchmark that pure luck produces from the "
            "41,472 configurations already searched. The phase-3 "
            "recommendation to forward-test is retracted."
        ),
    }
    write_manifest(payload, "manifest_phase4.json")
    print(f"\nelapsed {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
