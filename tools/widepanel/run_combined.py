"""The two levers combined: funding_high filter x payoff ratio.

Written after both were measured independently and both helped. Combining two
helps is exactly where a Sharpe gets manufactured, so this publishes the whole
grid around the combination rather than one cell, and it re-runs the FULL
frozen battery on the combination — including the deflated bar, which is the
gate that decided the parent line.

TRIAL ACCOUNTING, stated up front. The deflation used here is the project's own
framing-A benchmark over 41,472 configurations. Today's session added:
    4 cells x 3 cost regimes      = 12
    payoff-ratio frontier         =  5
    funding signs                 =  2
    long book 4 variants x 2 windows = 8
    this combination grid         =  3
                              total = 30
So the search count moves 41,472 -> 41,502, i.e. +0.07%. Negligible, and it is
recorded rather than ignored.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from shark_hunter import config as C                                    # noqa: E402
from shark_hunter.backtest.costs import CostModel                      # noqa: E402
from shark_hunter.backtest.engine import run_backtest                   # noqa: E402
from shark_hunter.strategies.recipes import STRATEGIES, build_spec     # noqa: E402
from tools.widepanel.run_wide import dependence_t, pbo_cscv            # noqa: E402

FEAT = ROOT / "shark_data" / "wide" / "features"
OUT = ROOT / "shark_results" / "wide"
SLIP = {"calm_12.0bps": 1.0, "volatile_22.8bps": 6.4, "covid_34.9bps": 12.45}
TRIALS = 41_472 + 30


def run(syms, mask_col, atr_stop, r_mult, slip):
    frames = []
    for sym in syms:
        df = pd.read_parquet(FEAT / f"{sym}.parquet").set_index("open_time").copy()
        if mask_col:
            df.loc[~df[mask_col].fillna(False), "rvol"] = np.nan
        spec = build_spec(df, STRATEGIES["SHARK-01"], atr_stop=atr_stop,
                          r_multiple=r_mult,
                          time_stop_bars=C.DEFAULT_TIME_STOP_BARS["4h"])
        res = run_backtest(df, spec, symbol=sym, timeframe="4h",
                           costs=CostModel(taker_fee_bps=C.TAKER_FEE_BPS,
                                           slippage_bps=slip))
        if not res.trades.empty:
            t = res.trades
            t = t[t.direction == "short"]
            if not t.empty:
                frames.append(t)
    if not frames:
        return pd.DataFrame()
    return (pd.concat(frames, ignore_index=True)
            .sort_values("entry_time").reset_index(drop=True))


def row(t, label, cost, r_mult, mask_name):
    if t.empty:
        return {"label": label}
    r = t.r_net.to_numpy(dtype=float)
    st = dependence_t(r)
    by = t.groupby("symbol")["r_net"].mean()
    sp = t.groupby("split")["r_net"].mean()
    wk = t.set_index("entry_time")["r_net"].resample("W").sum()
    stw = dependence_t(wk.to_numpy(dtype=float))
    need = 4.1954 / np.sqrt(st["n_effective"])
    span = (t.exit_time.max() - t.entry_time.min()).days / 365.25
    return {
        "label": label, "cost": cost, "r_multiple": r_mult, "filter": mask_name,
        "n": st["n"], "net_r": st["mean_r"], "gross_r": float(t.r_gross.mean()),
        "hit": float((r > 0).mean()), "snr": st["snr"], "iat": st["iat"],
        "n_eff": st["n_effective"], "t_adj": st["t_adjusted"],
        "weekly_t": stw["t_adjusted"], "pbo": pbo_cscv(t),
        "pos_sym": float((by > 0).mean()),
        "drop_best": float(t[t.symbol != by.idxmax()]["r_net"].mean()),
        "splits_pos": int((sp > 0).sum()),
        "snr_needed_deflated": float(need),
        "clears_deflated": bool(st["snr"] >= need),
        "total_R": float(r.sum()), "R_per_yr": float(r.sum() / span),
    }


def main() -> int:
    syms = pd.read_csv(FEAT / "universe.csv")["symbol"].tolist()
    rows = []
    for r_mult in (2.0, 2.5, 3.0):
        for cname, sl in SLIP.items():
            t = run(syms, "funding_high", 1.5, r_mult, sl)
            rows.append(row(t, f"funding_high x {r_mult}R", cname, r_mult,
                            "funding_high"))
    d = pd.DataFrame(rows)
    pd.set_option("display.width", 260)
    d.to_csv(OUT / "combined_levers.csv", index=False)

    print("COMBINED: low-vol AND funding_high, 1.5 ATR stop, SHORT leg")
    print("=" * 122)
    print(d[["cost", "r_multiple", "n", "net_r", "hit", "t_adj", "weekly_t",
             "pbo", "pos_sym", "splits_pos", "total_R", "R_per_yr",
             "snr_needed_deflated", "clears_deflated"]]
          .round(4).to_string(index=False))

    print("\n" + "=" * 96)
    print("FROZEN BATTERY — funding_high x 3.0R, calm cost")
    print("=" * 96)
    g = d[(d["r_multiple"] == 3.0)
          & (d["cost"] == "calm_12.0bps")].iloc[0]
    stress = d[(d["r_multiple"] == 3.0)
               & (d["cost"] == "covid_34.9bps")].iloc[0]
    checks = [
        ("S1  t_adjusted >= 2.0", g.t_adj, g.t_adj >= 2.0),
        ("S2  PBO < 20%", g.pbo, g.pbo < 0.20),
        ("S3  >=50% symbols net-positive", g.pos_sym, g.pos_sym >= 0.50),
        ("S4  >=3 of 4 splits positive", g.splits_pos, g.splits_pos >= 3),
        ("S5  drop-best-symbol > 0", g.drop_best, g.drop_best > 0),
        ("S6  net R > 0 at 34.9 bps stress", stress.net_r, stress.net_r > 0),
        (f"S7  snr >= deflated bar ({TRIALS:,} trials)", g.snr,
         g.clears_deflated),
    ]
    for n, v, ok in checks:
        vs = f"{v:.4f}" if isinstance(v, (float, np.floating)) else str(v)
        print(f"  {'PASS' if ok else 'FAIL'}  {n:<44} {vs:>12}")
    npass = sum(1 for _, _, o in checks if o)
    print(f"\n  {npass}/7 pass.  snr {g.snr:.4f} vs bar {g.snr_needed_deflated:.4f} "
          f"= {g.snr / g.snr_needed_deflated:.0%} of the requirement.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
