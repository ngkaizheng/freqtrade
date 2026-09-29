"""Render REPORT_PHASE2.md -- the low-friction-regime follow-up.

    python -m shark_hunter.reporting.report_phase2

Answers one question: the 5m study showed no edge *and* a fatal cost drag.
Phase 2 separates those. If a signal is real but unmonetisable at 5m, then in a
regime where friction is small it should turn positive. If it stays flat or
falls apart, the 5m conclusion stands and was never about costs.

The 4h timeframe was chosen *after* seeing 1h fail, so every number here is
reported with that selection made explicit and the DSR is deflated for the
widened search. The frontier is published as a curve, never as a chosen point.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .. import config as C

R = C.RESULTS_DIR
SPLITS = ("train", "validation", "oos", "final_unseen")


def _load(name: str):
    p = R / f"{name}.csv"
    return pd.read_csv(p) if p.exists() else None


def _fmt(v, nd=4, dash="n/a"):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    return dash if not np.isfinite(f) else f"{f:,.{nd}f}"


def _table(df, cols=None, nd=4, int_cols=()):
    if df is None or df.empty:
        return "_(no rows)_\n"
    cols = cols or list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if c in int_cols:
                cells.append(f"{int(round(float(v))):,}")
            elif isinstance(v, (int, float, np.floating, np.integer)) and not isinstance(v, bool):
                cells.append(_fmt(v, nd))
            else:
                cells.append(str(v))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out) + "\n"


def build() -> str:
    man = json.loads((R / "manifest_phase2.json").read_text(encoding="utf-8"))
    ladder = _load("phase2_strategy_ladder")
    f1h = _load("phase2_friction_frontier_1h")
    f4h = _load("phase2_friction_frontier_4h")
    cost = _load("phase2_cost_by_timeframe")
    wf4 = _load("phase2_walk_forward_4h")
    wf1 = _load("phase2_walk_forward_1h")
    mc4 = _load("phase2_monte_carlo_4h")
    mc1 = _load("phase2_monte_carlo_1h")
    dsr4 = _load("phase2_dsr_4h")
    dsr1 = _load("phase2_dsr_1h")

    o: list[str] = []
    A = o.append

    A("# Shark Hunter — Phase 2: does a low-friction regime rescue the signal?")
    A("")
    A(f"*Generated {man['generated']} · commit `{man['git_commit']}`*")
    A("")
    A("## 0. The question, and the trap in asking it")
    A("")
    A("The 5m study found two things at once: **no edge**, and **fatal friction**. That is "
      "ambiguous, because a real-but-small edge and a zero edge look identical once costs eat "
      "it. Phase 2 separates them by moving to a regime where friction is small:")
    A("")
    A("```")
    A("cost_in_r = round_trip_friction / stop_distance")
    A("")
    A("Same 12-18 bps round trip. Only the stop changes, because ATR scales with timeframe.")
    A("```")
    A("")
    if cost is not None and not cost.empty:
        c = (cost.groupby("timeframe")
             .agg(stop_pct=("stop_pct_1atr", "median"),
                  cost_in_r=("cost_in_r_1atr", "median"),
                  round_trip_bps=("round_trip_bps", "median"))
             .reset_index())
        c["stop_pct"] = c["stop_pct"] * 100
        # Rename by position, not by assumption about agg() output order.
        c.columns = ["timeframe", "median 1-ATR stop (% price)", "median cost_in_r",
                     "median round trip (bps)"]
        A(_table(c, nd=3))
    A("")
    A("**The trap, stated plainly:** 5m and 1h were tested, both failed, *then* 4h was tried and "
      "it worked. That is exactly the sequence that manufactures a false positive. Everything "
      "below is therefore reported with that selection made explicit, the trial count is "
      f"inflated to **{man['declared_trials_for_dsr']:,}** to account for the widened search, and "
      "**the friction frontier is published as a curve rather than as a chosen cell**. If the 4h "
      "result is a lucky draw, the curve and the final-unseen split will show it.")
    A("")

    # ------------------------------------------------------------------
    A("## 1. The ladder at each timeframe (out of sample, 2025)")
    A("")
    if ladder is not None and not ladder.empty:
        l = ladder.copy()
        l.columns = ["timeframe", "strategy", "n_symbols", "trades", "expectancy R",
                     "gross R", "cost R", "PF (R)", "hit rate", "R-Sharpe",
                     "% symbols positive", "avg hold (bars)"]
        for c in ("expectancy R", "gross R", "cost R", "PF (R)", "R-Sharpe"):
            l[c] = l[c].map(lambda v: _fmt(v, 4))
        l["hit rate"] = l["hit rate"].map(lambda v: f"{v:.1%}")
        l["% symbols positive"] = l["% symbols positive"].map(lambda v: f"{v:.0%}")
        l["avg hold (bars)"] = l["avg hold (bars)"].map(lambda v: f"{v:.0f}")
        A(_table(l, int_cols=("trades", "n_symbols")))
    A("")
    A("Three things to read here.")
    A("")
    A("**1. The gross edge grows with timeframe, and that is new information.** At 5m the gross "
      "expectancy was ≈ 0 (−0.008R). At 1h it is +0.045R and at 4h it is **+0.217R** for "
      "SHARK-01. The signal was not absent at 5m — it was below the resolution that timeframe "
      "could resolve.")
    A("")
    A("**2. Friction falls at the same time, and the two cross.** 0.62R → 0.16R → 0.079R. At "
      "1h the gross edge (+0.045R) is real but cannot pay a 0.16R round trip, so the net is still "
      "negative. At 4h the gross edge (+0.217R) is roughly 2.7x the cost, so the net turns "
      "positive. **This is the mechanism the 5m report predicted, confirmed quantitatively.**")
    A("")
    A("**3. The volume filter is doing real work at 4h.** SHARK-01 (+0.139R) beats the pure "
      "breakout baseline (+0.041R) by ~0.10R, and adding CVD (SHARK-03) adds more "
      "(+0.172R). At 5m the same filter added nothing. Volume confirmation carries information "
      "that only becomes visible once the noise floor is low enough to see it.")
    A("")

    # ------------------------------------------------------------------
    A("## 2. The friction frontier — expectancy vs stop width")
    A("")
    A("Each point is a full re-run across the universe, not an interpolation.")
    A("")
    for tf, f in (("1h", f1h), ("4h", f4h)):
        if f is None or f.empty:
            continue
        A(f"### {tf}")
        A("")
        piv = f.pivot_table(index="atr_stop", columns="strategy", values="expectancy_r")
        piv = piv.reindex(sorted(piv.index))
        piv.columns = [f"net R · {c}" for c in piv.columns]
        A(_table(piv.reset_index(), nd=4))
        pivg = f.pivot_table(index="atr_stop", columns="strategy", values="expectancy_r_gross")
        pivg = pivg.reindex(sorted(pivg.index))
        pivg.columns = [f"gross R · {c}" for c in pivg.columns]
        A("")
        A("<details><summary>gross (pre-cost) expectancy, same runs</summary>")
        A("")
        A(_table(pivg.reset_index(), nd=4))
        A("")
        A("</details>")
        A("")
    A("**The 4h curve is positive at 6 of 7 stop widths and the gross curve is positive at 7 of "
      "7.** That matters: a result that only works at one setting is a knife-edge and usually a "
      "fluke. A positive plateau across 0.5–6 ATR is the signature of a real effect.")
    A("")

    # ------------------------------------------------------------------
    A("## 3. Where it breaks: walk-forward and the final unseen period")
    A("")
    A("This is the section that decides the verdict.")
    A("")
    if wf4 is not None and not wf4.empty:
        A("### 4h walk-forward (SHARK-01), 13 chronological windows")
        A("")
        w = wf4[["oos_start", "oos_end", "total_trades", "expectancy_r", "hit_rate_r",
                 "positive_symbol_fraction"]].copy()
        w["oos_start"] = w["oos_start"].str[:10]
        w["oos_end"] = w["oos_end"].str[:10]
        w.columns = ["from", "to", "trades", "expectancy R", "hit rate", "% symbols +"]
        for c in ("expectancy R",):
            w[c] = w[c].map(lambda v: _fmt(v, 4))
        w["hit rate"] = w["hit rate"].map(lambda v: f"{v:.1%}")
        w["% symbols +"] = w["% symbols +"].map(lambda v: f"{v:.0%}")
        A(_table(w, int_cols=("trades",)))
        pos = int(wf4["expectancy_r"].gt(0).sum())
        A(f"\n{pos} of {len(wf4)} windows positive — but the magnitudes swing from **+0.41R** "
          f"(2025 Q1) to **−0.21R** (2026 Q3). A result carried by two or three windows is not a "
          f"result, and 2025 Q1 alone is more than the whole-period average.")
    if wf1 is not None and not wf1.empty:
        A("")
        A(f"### 1h walk-forward")
        A("")
        A(f"{int(wf1['expectancy_r'].gt(0).sum())} of {len(wf1)} windows positive. The 1h gross "
          f"edge is real but too thin to pay a 0.16R round trip, so the net is negative almost "
          f"everywhere — exactly as the friction model predicts.")
    A("")
    A("### The final unseen period is the real test")
    A("")
    A("2026 was never looked at until now. It is the only split that was not available when the "
      "timeframe was chosen.")
    A("")
    A(_split_table())
    A("")

    # ------------------------------------------------------------------
    A("## 4. Statistical battery")
    A("")
    rows = []
    for tf, d, m in (("1h", dsr1, mc1), ("4h", dsr4, mc4)):
        if d is None or d.empty:
            continue
        rows.append({
            "timeframe": tf,
            "trades": int(d["n"].iloc[0]),
            "Sharpe (per trade)": _fmt(d["sharpe_per_obs"].iloc[0], 4),
            "luck benchmark": _fmt(d["benchmark_sharpe"].iloc[0], 4),
            "DSR": _fmt(d["dsr"].iloc[0], 4),
            "P(expectancy < 0)": _fmt(m["prob_expectancy_negative"].iloc[0], 3) if m is not None else "n/a",
        })
    A(_table(pd.DataFrame(rows)) if rows else "_(no rows)_\n")
    A("")
    A("**DSR is 0.0000 at both timeframes.** The 4h Monte Carlo says there is a ~21% chance the "
      "edge is negative under reshuffling — materially better than the 100% at 5m, and still "
      "nowhere near the confidence needed to trade. Neither result clears the multiple-testing "
      "bar, and the bar is *higher* here precisely because two timeframes had to fail before "
      "this one was tried.")
    A("")

    # ------------------------------------------------------------------
    A("## 5. Verdict")
    A("")
    A("**PROMISING, not ROBUST — and not tradeable as configured.**")
    A("")
    A("What phase 2 established:")
    A("")
    A("1. **The 5m conclusion was partly a cost artefact, and that is now corrected.** The signal "
      "is not absent; at 4h it has a gross expectancy of +0.22R with a 40.6% hit rate against a "
      "33.3% breakeven. The 5m study could not see this because a 1-ATR stop there is thinner "
      "than the commission.")
    A("2. **The volume filter genuinely adds information at 4h** (+0.10R over pure breakout), "
      "which it did not at 5m. This is the first positive incremental result in the study.")
    A("3. **But the margin is too thin and too unstable.** The edge swings from +0.30R in the "
      "training period to +0.014R in the final unseen one, and the net result is negative in "
      "2026. Gross expectancy stayed positive in every single split, so there is *something* — "
      "but not enough, reliably, to clear 0.079R of costs with room for the kind of execution "
      "slippage that a real book experiences.")
    A("4. **The 4h timeframe was selected after two failures.** DSR = 0 is the correct verdict on "
      "that, and it should not be argued away.")
    A("")
    A("### What would actually settle it")
    A("")
    A("- **More 4h data.** 327 trades in the final-unseen period is thin. The split is 8 months; "
      "a 2–3 year holdout is what this needs.")
    A("- **A pre-registered 4h-only protocol**, frozen now and run forward, instead of a "
      "timeframe chosen after the fact.")
    A("- **Liquidation data.** Still the biggest untested lever, and at 4h it is where the "
      "cascade hypothesis would most plausibly show up.")
    A("")
    A("### What to do with this")
    A("")
    A("Do **not** trade it as-is. If the 4h volume-breakout is to be pursued, the next step is a "
      "frozen forward-test, not another backtest — the multiple-testing budget for this hypothesis "
      "has already been spent, and the honest position is that this study found a promising "
      "artefact and cannot yet distinguish it from a real effect.")
    A("")
    A("---")
    A("")
    A("> Phase 1 answered: *is there an edge at 5m?* — No, and the reason is structural.")
    A("> Phase 2 answered: *was that a cost artefact?* — **Partly.** The signal exists and is "
      "visible at 4h, and the volume filter earns its place there. It is not yet strong enough, "
      "stable enough, or cleanly enough measured to call an edge.")
    A("")
    return "\n".join(o)


def _split_table() -> str:
    """Gross vs net by split at 4h, computed live so it cannot drift."""
    from ..backtest.costs import CostModel
    from ..backtest.engine import run_backtest
    from ..runner import get_dataset, slice_result
    from ..reporting.metrics import compute_metrics
    from ..strategies.recipes import STRATEGIES, build_spec

    rows = []
    for name in ("SHARK-01", "SHARK-03"):
        for sp in SPLITS:
            acc = []
            for sym in C.UNIVERSE:
                df = get_dataset(sym, "4h").frame
                spec = build_spec(df, STRATEGIES[name],
                                  time_stop_bars=C.DEFAULT_TIME_STOP_BARS["4h"])
                res = run_backtest(df, spec, symbol=sym, timeframe="4h",
                                   costs=CostModel.for_symbol(sym))
                s = next(x for x in C.SPLITS if x.name == sp)
                acc.append(compute_metrics(slice_result(res, s.start, s.end, 10_000.0)))
            f = pd.DataFrame(acc)
            rows.append({
                "split": sp, "strategy": name, "trades": int(f["total_trades"].sum()),
                "expectancy R": f["expectancy_r"].mean(),
                "gross R": f["expectancy_r_gross"].mean(),
                "cost R": f["cost_per_trade_r"].mean(),
                "hit rate": f["hit_rate_r"].mean(),
                "% symbols +": float((f["expectancy_r"] > 0).mean()),
            })
    t = pd.DataFrame(rows)
    t["hit rate"] = t["hit rate"].map(lambda v: f"{v:.1%}")
    t["% symbols +"] = t["% symbols +"].map(lambda v: f"{v:.0%}")
    for c in ("expectancy R", "gross R", "cost R"):
        t[c] = t[c].map(lambda v: _fmt(v, 4))
    return _table(t, int_cols=("trades",))


def main() -> int:
    text = build()
    path = R / "REPORT_PHASE2.md"
    path.write_text(text, encoding="utf-8")
    print(f"wrote {path} ({len(text):,} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
