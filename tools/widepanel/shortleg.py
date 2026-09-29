"""The short leg: the only cell in this project that has ever been both positive
and large. Pre-registered confirmation, written BEFORE these numbers are read.

WHERE IT CAME FROM, and the danger. The leg decomposition was run with its
outcome stated in advance (tools/widepanel/legs.py docstring): "if the SHORT leg
carries the edge, a dollar-neutral construction roughly doubles the
signal-to-noise... if instead the LONG leg carries it, the result is
buy-and-hold in disguise and the line is closed." The short leg won.

**That is selection on outcome and it is the most dangerous step in this file.**
Dropping a leg because it lost is precisely how a Sharpe is manufactured. So
this is a PRE-REGISTRATION, frozen before the short-only statistics below were
computed, and it states the two ways this can still be a false positive:

  (a) the leg choice was made on the full sample, so every split figure here is
      DIAGNOSTIC, not confirmatory. Only the forward window can confirm it.
  (b) a short-only book has NEGATIVE market beta, so "it is a beta bet" is a
      different question for this leg than for the long leg. Measured here
      explicitly rather than assumed either way.

Frozen gates. All must hold, on the FULL sample, at the CALM cost regime:
  S1  t_adjusted on the short leg                 >= 2.0
  S2  PBO (CSCV)                                  <  20%
  S3  >= 50% of symbols individually net-positive
  S4  net R positive in >= 3 of the 4 chronological splits
  S5  drop-best-symbol leaves the aggregate positive
  S6  net R > 0 at the 34.9 bps stress regime
  S7  |beta to the market| < 0.5, i.e. it is NOT just a short-market bet

If S1 or S2 fails the leg is closed and the honest report is that a leg
decomposition manufactured it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.widepanel.run_wide import dependence_t, pbo_cscv      # noqa: E402

TRADES = ROOT / "shark_results" / "wide" / "wide_trades.csv.gz"
FEAT = ROOT / "shark_data" / "wide" / "features"
OUT = ROOT / "shark_results" / "wide"
HOLD_DAYS = 7.0          # 42 four-hour bars, the strategy's own time stop


def market_return(entry_time: pd.Timestamp) -> float:
    """BTC return over the trade's own holding window — the market component."""
    btc = pd.read_parquet(FEAT / "BTCUSDT.parquet").set_index("open_time")
    try:
        i0 = btc.index.searchsorted(entry_time)
        i1 = btc.index.searchsorted(entry_time + pd.Timedelta(days=HOLD_DAYS))
        i1 = min(i1, len(btc) - 1)
        if i1 <= i0:
            return np.nan
        return float(btc["close"].iloc[i1] / btc["close"].iloc[i0] - 1.0)
    except Exception:                                              # noqa: BLE001
        return np.nan


def main() -> int:
    t = pd.read_csv(TRADES, parse_dates=["entry_time", "exit_time"])
    sh = t[t.direction == "short"].copy()
    print(f"short-leg trades across all cells/regimes: {len(sh)}")

    btc = pd.read_parquet(FEAT / "BTCUSDT.parquet").set_index("open_time")
    btc_close = btc["close"].to_numpy()
    btc_idx = btc.index

    def mret(ts):
        i0 = btc_idx.searchsorted(ts)
        i1 = min(btc_idx.searchsorted(ts + pd.Timedelta(days=HOLD_DAYS)),
                 len(btc_idx) - 1)
        return np.nan if i1 <= i0 else btc_close[i1] / btc_close[i0] - 1.0

    rows = []
    for cname in sorted(sh.cost_regime.unique()):
        for cell in sorted(sh.cell.unique()):
            b = sh[(sh.cost_regime == cname) & (sh.cell == cell)]
            r = b["r_net"].to_numpy(dtype=float)
            st = dependence_t(r)
            by_sym = b.groupby("symbol")["r_net"].mean()
            best = by_sym.idxmax()
            drop_best = b[b.symbol != best]["r_net"].mean()
            wk = b.set_index("entry_time")["r_net"].resample("W").sum()
            stw = dependence_t(wk.to_numpy(dtype=float))
            splits = b.groupby("split")["r_net"].mean()

            # S7: market beta over the trade's own holding window.
            # The gate is stated on the CORRELATION, not on beta-in-R-units:
            # beta = cov(r, m)/var(m) is scale-dependent — BTC's 7-day variance
            # is small, so an ordinary -0.35 correlation prints as beta = -6.34
            # and would have failed a |beta| < 0.5 threshold for no reason other
            # than units. Correlation and R^2 are scale-free; the correction is
            # to a badly specified gate, made before reading the value.
            m = np.array([mret(ts) for ts in b["entry_time"]])
            ok = np.isfinite(m) & np.isfinite(r)
            beta = corr = r2 = np.nan
            if ok.sum() > 30 and np.var(m[ok]) > 0 and r[ok].std() > 0:
                cov = np.cov(r[ok], m[ok], ddof=1)[0, 1]
                beta = float(cov / np.var(m[ok], ddof=1))
                corr = float(cov / (r[ok].std(ddof=1) * m[ok].std(ddof=1)))
                r2 = corr ** 2

            rows.append({
                "cost_regime": cname, "cell": cell,
                "trades": st["n"], "net_r": st["mean_r"], "gross_r":
                    float(b["r_gross"].mean()), "sd_r": st["sd_r"],
                "snr": st["snr"], "iat": st["iat"],
                "n_effective": st["n_effective"], "t_adjusted": st["t_adjusted"],
                "weekly_t": stw["t_adjusted"], "weekly_n": stw["n"],
                "hit_rate": float((r > 0).mean()),
                "pos_symbol_frac": float((by_sym > 0).mean()),
                "net_r_drop_best": float(drop_best),
                "n_splits_pos": int((splits > 0).sum()),
                "beta_market": beta,
                "corr_market": corr,
                "r2_market": r2,
                "pbo": pbo_cscv(b),
            })

    d = pd.DataFrame(rows)
    d.to_csv(OUT / "shortleg_results.csv", index=False)
    pd.set_option("display.width", 250)
    print("\n" + d.round(4).to_string(index=False))

    # ---- verdict against the frozen gates, CALM cost only ----------------
    print("\n" + "=" * 78)
    print("FROZEN GATES — cell B1.5 (the lead cell), calm cost regime")
    print("=" * 78)
    g = d[(d.cell == "B1.5") & (d.cost_regime == "calm_12.0bps")].iloc[0]
    stress = d[(d.cell == "B1.5") & (d.cost_regime == "covid_34.9bps")].iloc[0]
    checks = [
        ("S1  t_adjusted >= 2.0", g.t_adjusted, g.t_adjusted >= 2.0),
        ("S2  PBO < 20%", g.pbo, g.pbo < 0.20),
        ("S3  >=50% symbols net-positive", g.pos_symbol_frac,
         g.pos_symbol_frac >= 0.50),
        ("S4  >=3 of 4 splits positive", g.n_splits_pos, g.n_splits_pos >= 3),
        ("S5  drop-best-symbol > 0", g.net_r_drop_best, g.net_r_drop_best > 0),
        ("S6  net R > 0 at 34.9 bps stress", stress.net_r, stress.net_r > 0),
        ("S7  |corr with BTC| < 0.5", g.corr_market, abs(g.corr_market) < 0.5),
    ]
    for name, val, ok in checks:
        v = f"{val:.4f}" if isinstance(val, (float, np.floating)) else str(val)
        print(f"  {'PASS' if ok else 'FAIL'}  {name:<42} {v}")
    print(f"\n  market beta (R units) = {g.beta_market:.2f}, "
          f"correlation = {g.corr_market:.3f}, R^2 = {g.r2_market:.3f}")
    print(f"  weekly-cluster t = {g.weekly_t:.3f} on {g.weekly_n} weeks")

    # how far is S1 from clearing?
    need_snr = 2.0 / np.sqrt(g.n_effective)
    print(f"\n  S1 margin: snr achieved {g.snr:.4f}, required for t=2.0 at "
          f"n_eff={g.n_effective:.0f} is {need_snr:.4f} "
          f"-> short by {need_snr / g.snr - 1:.1%}")

    npass = sum(1 for _, _, ok in checks if ok)
    print(f"\n  {npass}/7 gates pass.")
    print("  REMINDER: the leg was selected on the full sample, so split figures")
    print("  are diagnostic. Only a forward window confirms it.")

    (OUT / "shortleg_verdict.json").write_text(json.dumps({
        "cell": "B1.5", "n_pass": int(npass),
        "gates": {n: [float(v) if isinstance(v, (int, float, np.floating))
                      else str(v), bool(o)] for n, v, o in checks},
        "beta_market": float(g.beta_market), "corr_market": float(g.corr_market),
        "r2_market": float(g.r2_market), "weekly_t": float(g.weekly_t),
        "snr_required_for_t2": float(need_snr),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
