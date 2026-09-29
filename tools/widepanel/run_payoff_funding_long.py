"""Payoff-ratio frontier, funding filter, and the long book.

Implements PREREG_PAYOFF_FUNDING_LONG_2026-09-27.md. Nothing here was decided
after seeing a number:

  §1  payoff ratio  : r_multiple in {1.5, 2.0, 2.5, 3.0, 4.0}, short leg,
                      FULL SAMPLE only, whole grid published as a frontier.
  §2  funding filter: short when funding7d above / below its 365-bar median,
                      FULL SAMPLE only, BOTH signs reported.
  §3  long book     : L1 no filter, L2 high-vol, L3 funding — reported on
                      BOTH the user's window (2024-01 -> 2025-09) and the full
                      sample, because the window is 21 months and cannot reach
                      significance on its own.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from shark_hunter import config as C                                   # noqa: E402
from shark_hunter.backtest.costs import CostModel                     # noqa: E402
from shark_hunter.backtest.engine import run_backtest                   # noqa: E402
from shark_hunter.strategies.recipes import STRATEGIES, build_spec     # noqa: E402
from tools.widepanel.run_wide import dependence_t                      # noqa: E402

FEAT = ROOT / "shark_data" / "wide" / "features"
OUT = ROOT / "shark_results" / "wide"
SLIPP = {"calm_12.0bps": 1.0, "volatile_22.8bps": 6.4, "covid_34.9bps": 12.45}
USER_WINDOW = ("2024-01-01", "2025-09-30")


def run(symbols, mask_col, side, atr_stop, r_mult, slip):
    """side: 'long' or 'short'. mask_col gates the signal via rvol=NaN."""
    frames = []
    for sym in symbols:
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
        t = t[t.direction == side]
        if not t.empty:
            frames.append(t)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    # ⚠ MUST sort by time. The frames are concatenated SYMBOL BY SYMBOL, which
    # leaves the series in symbol order, not chronological order. The integrated
    # autocorrelation time is computed from the series' own ordering, so an
    # unsorted series reports IAT = 1.0 and inflates t by ~4x — this bug showed
    # t_adj = 7.81 for a cell whose true value is 1.87. Every dependence
    # statistic on a multi-symbol trade set needs the trades in time order.
    return out.sort_values("entry_time").reset_index(drop=True)


def line(label, t):
    if t.empty:
        return {"label": label, "n": 0}
    st = dependence_t(t.r_net.to_numpy(dtype=float))
    by = t.groupby("symbol")["r_net"].mean()
    span = (t.exit_time.max() - t.entry_time.min()).days / 365.25
    return {
        "label": label, "n": st["n"], "net_r": st["mean_r"],
        "gross_r": float(t.r_gross.mean()), "snr": st["snr"],
        "iat": st["iat"], "n_eff": st["n_effective"],
        "t_adj": st["t_adjusted"], "hit": float((t.r_net > 0).mean()),
        "pos_sym": float((by > 0).mean()), "total_R": float(t.r_net.sum()),
        "R_per_yr": float(t.r_net.sum() / max(span, 1e-9)),
    }


def main() -> int:
    syms = pd.read_csv(FEAT / "universe.csv")["symbol"].tolist()
    rows = []

    # ---------------- §1 payoff ratio, full sample, short, low-vol on ----
    print("=" * 100)
    print("§1  PAYOFF RATIO — short leg, 1.5 ATR stop, low-vol filter, FULL SAMPLE")
    print("=" * 100)
    for rm in (1.5, 2.0, 2.5, 3.0, 4.0):
        r = run(syms, "low_vol", "short", 1.5, rm, SLIPP["calm_12.0bps"])
        d = line(f"r_multiple={rm}", r)
        d.update(test="payoff", cost="calm")
        rows.append(d)
        print(f"  target {rm:>4.1f}R : n={d['n']:>5}  net={d['net_r']:+.4f}R  "
              f"hit={d['hit']:.1%}  t_adj={d['t_adj']:+.2f}  "
              f"total={d['total_R']:>7.0f}R  R/yr={d['R_per_yr']:>6.0f}")

    # ---------------- §2 funding filter, full sample, short, low-vol on ---
    print("\n" + "=" * 100)
    print("§2  FUNDING FILTER — short leg, 1.5 ATR, low-vol on, FULL SAMPLE")
    print("=" * 100)
    for mname, mcol in (("funding_high", "funding_high"),
                        ("funding_low", "funding_low")):
        r = run(syms, mcol, "short", 1.5, 2.0, SLIPP["calm_12.0bps"])
        d = line(mname, r)
        d.update(test="funding", cost="calm")
        rows.append(d)
        print(f"  {mname:<14}: n={d['n']:>5}  net={d['net_r']:+.4f}R  "
              f"hit={d['hit']:.1%}  t_adj={d['t_adj']:+.2f}  "
              f"total={d['total_R']:>7.0f}R  sym+={d['pos_sym']:.0%}")

    # ---------------- §3 long book, BOTH windows -------------------------
    print("\n" + "=" * 100)
    print("§3  LONG BOOK — both windows. The user's window is 21 months and")
    print("    cannot reach t=2; the full-sample column is the honest one.")
    print("=" * 100)
    for win, (lo, hi) in (("full 2023-01..2026-08", ("2023-01-01", "2026-08-31")),
                          ("user 2024-01..2025-09", USER_WINDOW)):
        for lname, mcol in (("L1 no filter", None),
                            ("L2 high-vol", "high_vol"),
                            ("L3 funding_high", "funding_high"),
                            ("L3 funding_low", "funding_low")):
            r = run(syms, mcol, "long", 1.5, 2.0, SLIPP["calm_12.0bps"])
            r = r[(r.entry_time >= lo) & (r.entry_time <= hi)]
            d = line(f"{win} | {lname}", r)
            d.update(test="long", window=win)
            rows.append(d)
            print(f"  {win:<24} {lname:<15} n={d['n']:>5}  "
                  f"net={d['net_r']:+.4f}R  hit={d['hit']:.1%}  "
                  f"t_adj={d['t_adj']:+.2f}  sym+={d['pos_sym']:.0%}")

    pd.DataFrame(rows).to_csv(OUT / "payoff_funding_long.csv", index=False)
    print(f"\nwrote {OUT / 'payoff_funding_long.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
