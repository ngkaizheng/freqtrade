"""Full frozen-gate battery on the funding_high cell — is it a lead or a fluke?

The funding filter produced t_adj = 2.41 on one of two pre-registered signs.
That is NOT a pass of the parent line's S1 gate (which sits on the 2.0R
incumbent at 1.87). It is a NEW cell in a study that has now examined many
cells, so the same battery has to be run on it: deflated bar, PBO, per-symbol
consistency, split consistency, and the stress cost regime. And the whole point
of reporting two signs is that the loser is the control.
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
SLIP = {"calm": 1.0, "volatile": 6.4, "covid": 12.45}


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
        if res.trades.empty:
            continue
        t = res.trades
        t = t[t.direction == "short"]
        if not t.empty:
            frames.append(t)
    if not frames:
        return pd.DataFrame()
    return (pd.concat(frames, ignore_index=True)
            .sort_values("entry_time").reset_index(drop=True))


def main() -> int:
    syms = pd.read_csv(FEAT / "universe.csv")["symbol"].tolist()
    rows = []
    for cname, sl in SLIP.items():
        for r_mult in (2.0, 3.0):
            for fname, mcol in (("funding_high", "funding_high"),
                                ("lowvol_only", "low_vol")):
                t = run(syms, mcol, 1.5, r_mult, sl)
                if t.empty:
                    continue
                r = t.r_net.to_numpy(dtype=float)
                st = dependence_t(r)
                by = t.groupby("symbol")["r_net"].mean()
                best = by.idxmax()
                drop_best = t[t.symbol != best]["r_net"].mean()
                sp = t.groupby("split")["r_net"].mean()
                wk = t.set_index("entry_time")["r_net"].resample("W").sum()
                stw = dependence_t(wk.to_numpy(dtype=float))
                # deflated bar, framing A, 41,472 trials
                need = 4.1954 / np.sqrt(st["n_effective"])
                rows.append({
                    "cost": cname, "r_multiple": r_mult, "filter_name": fname,
                    "n": st["n"], "net_r": st["mean_r"], "snr": st["snr"],
                    "iat": st["iat"], "n_eff": st["n_effective"],
                    "t_adj": st["t_adjusted"], "weekly_t": stw["t_adjusted"],
                    "pbo": pbo_cscv(t),
                    "pos_sym": float((by > 0).mean()),
                    "drop_best": float(drop_best),
                    "splits_pos": int((sp > 0).sum()),
                    "snr_needed_deflated": float(need),
                    "clears_deflated": bool(st["snr"] >= need),
                })
    d = pd.DataFrame(rows)
    pd.set_option("display.width", 260)
    print("SHORT LEG, 1.5 ATR stop. filter = low-vol only vs low-vol AND funding_high")
    print(d.round(4).to_string(index=False))
    d.to_csv(OUT / "funding_lead_gates.csv", index=False)

    print("\n" + "=" * 92)
    print("FROZEN BATTERY on the lead cell (funding_high, 2.0R, calm)")
    print("=" * 92)
    # NB: bracket access. `d.filter` is the DataFrame.filter METHOD, so
    # `d.filter == "funding_high"` silently compares a bound method to a string
    # and is always False - the selection comes back empty with no error.
    # Same family as `df.merge` used as a column name.
    g = d[(d["filter_name"] == "funding_high") & (d["r_multiple"] == 2.0)
          & (d["cost"] == "calm")].iloc[0]
    stress = d[(d["filter_name"] == "funding_high") & (d["r_multiple"] == 2.0)
               & (d["cost"] == "covid")].iloc[0]
    checks = [
        ("S1  t_adjusted >= 2.0", g.t_adj, g.t_adj >= 2.0),
        ("S2  PBO < 20%", g.pbo, g.pbo < 0.20),
        ("S3  >=50% symbols net-positive", g.pos_sym, g.pos_sym >= 0.50),
        ("S4  >=3 of 4 splits positive", g.splits_pos, g.splits_pos >= 3),
        ("S5  drop-best-symbol > 0", g.drop_best, g.drop_best > 0),
        ("S6  net R > 0 at 34.9 bps stress", stress.net_r, stress.net_r > 0),
        ("S7  snr >= deflated bar (41,472 trials)", g.snr, g.clears_deflated),
    ]
    for n, v, ok in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {n:<44} {v:>10.4f}")
    print(f"\n  {sum(1 for _,_,o in checks if o)}/7 pass.  "
          f"snr {g.snr:.4f} vs deflated bar {g.snr_needed_deflated:.4f}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
