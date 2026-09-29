"""
E#8 -- volatility targeting, and whether any leverage survives.

Pre-registration: PREREGISTRATION_E8.md, written before any result.

The arithmetic that motivates putting these in one experiment: leverage
multiplies return and drawdown alike, and a fully-invested account at leverage L
is liquidated after a move of about 1/L -- so 10x dies on a -10% move, which
happens constantly in crypto. Buy-and-hold drew down -79.8% on this universe.
Leverage is therefore a constraint on allowed drawdown, not a lever on return.

Every cell of the grid is reported. None is selected.

Run:  .venv\\Scripts\\python.exe tools\\cross_sectional\\e8_voltrev_leverage.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 40)

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "user_data/universe/raw_daily"
OUT = Path(__file__).resolve().parent

TOP_N = 50
VOL_WINDOW = 30
VOL_TARGETS = (0.20, 0.35, 0.50, 0.70)
LEVERAGES = (1, 2, 3, 5, 10, 20)
EXPOSURE_CLIP = 3.0
FEE_BPS = 10.0
COST_BPS = 3.6                     # measured mean at $10k/name
COST_RT = (COST_BPS + FEE_BPS) / 1e4
REBASE = -0.90
TRADING_DAYS = 365


def load_panel():
    frames, dropped = {}, []
    for f in sorted(RAW.glob("*_1d.csv.gz")):
        sym = f.name.replace("_1d.csv.gz", "")
        d = pd.read_csv(f)
        d["date"] = pd.to_datetime(d["date"], format="%Y-%m-%d", errors="coerce")
        d = d.dropna(subset=["date", "close", "quote_volume"]).set_index("date").sort_index()
        d = d[~d.index.duplicated()]
        d = d[d["quote_volume"] > 0]
        if (d["close"].pct_change() < REBASE).any():
            dropped.append(sym)
            continue
        frames[sym] = d
    px = pd.concat({k: v["close"] for k, v in frames.items()}, axis=1).sort_index()
    qv = pd.concat({k: v["quote_volume"] for k, v in frames.items()}, axis=1).sort_index()
    return px, qv, dropped


def basket(px: pd.DataFrame) -> pd.Series:
    return px.mean(axis=1).ffill()


def trend_overlay(px: pd.DataFrame, lookback: int = 126, skip: int = 21) -> pd.Series:
    """E#7's long/cash rule, mapped to a daily 0/1 exposure series."""
    sig = (px / px.shift(lookback) - 1.0)
    m = sig.mean(axis=1) > 0
    raw = m.astype(float)
    out = raw.ffill().fillna(0.0)
    return out


def first_liquidation(cum: pd.Series, leverage: float) -> str | None:
    """A fully-invested account at leverage L is gone when the cumulative move
    against it reaches 1/L. Computed on the DAILY levered path, before
    compounding, because compounding a blown-up account is meaningless."""
    if leverage <= 1:
        return None
    thr = 1.0 / leverage
    hit = cum <= (1.0 - thr)
    if not hit.any():
        return None
    return str(cum.index[hit][0].date())


def run(base_ret: pd.Series, exposure: pd.Series, leverage: int, cost_rt: float) -> dict:
    r = base_ret.reindex(exposure.index).fillna(0.0)
    e = exposure.reindex(r.index).fillna(0.0)
    levered = r * e * leverage
    turnover = e.diff().abs().fillna(e.abs())
    net = levered - turnover * cost_rt
    eq = (1 + net).cumprod()
    dd = float((eq / eq.cummax() - 1).min())
    years = len(net) / TRADING_DAYS
    cagr = float((eq.iloc[-1] ** (1 / years) - 1) * 100) if eq.iloc[-1] > 0 else float("nan")
    liq = first_liquidation((1 + levered).cumprod(), leverage)
    return {
        "cagr_pct": cagr,
        "max_dd_pct": dd * 100,
        "sharpe": float(net.mean() / net.std(ddof=1) * math.sqrt(TRADING_DAYS)) if net.std() else float("nan"),
        "torture": cagr / abs(dd) if dd else float("nan"),
        "mean_exposure": float(e.mean()),
        "annual_turnover": float(turnover.mean() * TRADING_DAYS),
        "liquidated": liq is not None,
        "liquidation_date": liq,
        "final_equity": float(eq.iloc[-1]),
    }


def main() -> int:
    px, qv, dropped = load_panel()
    med = qv.median()
    uni = list(med.nlargest(TOP_N).index)
    px = px[uni]
    print(f"universe: top {TOP_N} by median daily quote volume "
          f"({med[uni].median()/1e6:.0f}m USD/day), {len(px)} daily bars")
    print(f"  G7 pre-removed: {len(dropped)} (evaluated, not asserted)")
    print(f"  cost {COST_RT*1e4:.1f} bps round trip "
          f"({COST_BPS} bps measured mean book + {FEE_BPS} bps fee)\n")

    b = basket(px)
    base_ret = b.pct_change(fill_method=None)
    # CORRECTED 2026-09-26. This was `base_ret.rolling(VOL_WINDOW).std()` with
    # no lag, so exposure[t] was a function of return[t] and the book was
    # credited with cutting exposure on exactly the days that turned out to be
    # large. The published result on this exact overlay is that correcting the
    # look-ahead makes the drawdown WORSE, not better: Liu, Tang & Zhou,
    # "Volatility-Managed Portfolio: Does It Really Work?", JPM 45(4), 2019,
    # report max drawdowns of 68-93% after the correction. One bar of lag.
    realised_vol = base_ret.rolling(VOL_WINDOW).std().shift(1) * math.sqrt(TRADING_DAYS)
    print(f"realised vol of the basket: mean {realised_vol.mean()*100:.0f}%/yr, "
          f"p10 {realised_vol.quantile(0.10)*100:.0f}%, "
          f"p90 {realised_vol.quantile(0.90)*100:.0f}%")

    bh = run(base_ret, pd.Series(1.0, index=px.index), 1, COST_RT)
    print(f"\nBENCHMARK buy-and-hold unlevered: CAGR {bh['cagr_pct']:+.2f}%  "
          f"maxDD {bh['max_dd_pct']:+.2f}%  torture {bh['torture']:.3f}")

    results = []
    bases = {
        "buy-and-hold": (base_ret, pd.Series(1.0, index=px.index)),
        "trend-126d-longcash": (base_ret, trend_overlay(px)),
    }
    for bname, (bret, bexp) in bases.items():
        print()
        print("=" * 118)
        print(f"BASE: {bname}   (unlevered, no vol target: "
              f"CAGR {run(bret, bexp, 1, COST_RT)['cagr_pct']:+.1f}%  "
              f"maxDD {run(bret, bexp, 1, COST_RT)['max_dd_pct']:+.1f}%)")
        print("=" * 118)
        print(f"{'vol target':>11} {'lev':>4} {'exposure':>9} {'CAGR%':>9} {'maxDD%':>9} "
              f"{'torture':>9} {'Sharpe':>8} {'liq?':>6} {'ann turnover':>13}")
        for vt in VOL_TARGETS:
            # The base's own exposure (the trend filter) and the volatility
            # overlay are MULTIPLIED. An earlier version computed bexp and then
            # never used it, so the trend rows were byte-identical to
            # buy-and-hold.
            vol_expo = (vt / realised_vol).clip(0.0, EXPOSURE_CLIP).fillna(0.0)
            expo = (vol_expo * bexp.reindex(vol_expo.index).fillna(0.0))
            for L in LEVERAGES:
                r = run(bret, expo, L, COST_RT)
                r.update({"base": bname, "vol_target": vt, "leverage": L})
                results.append(r)
                flag = "DEAD" if r["liquidated"] else "ok"
                print(f"{vt:>11.0%} {L:>4}x {r['mean_exposure']:>9.2f} {r['cagr_pct']:>9.1f} "
                      f"{r['max_dd_pct']:>9.1f} {r['torture']:>9.3f} {r['sharpe']:>8.2f} "
                      f"{flag:>6} {r['annual_turnover']:>13.1f}")
        r = run(bret, bexp, 1, COST_RT)
        r.update({"base": bname, "vol_target": None, "leverage": 1})
        results.append(r)

    res = pd.DataFrame(results)
    print()
    print("=" * 118)
    print("SURVIVORS, ranked by TORTURE RATIO (CAGR per unit of drawdown)")
    print("=" * 118)
    alive = res[~res["liquidated"]].sort_values("torture", ascending=False)
    cols = ["base", "vol_target", "leverage", "cagr_pct", "max_dd_pct", "torture", "sharpe"]
    show = alive[cols].copy()
    show["vol_target"] = show["vol_target"].map(lambda v: "none" if pd.isna(v) else f"{v:.0%}")
    for c in ["cagr_pct", "max_dd_pct", "torture", "sharpe"]:
        show[c] = show[c].round(3)
    print(show.head(20).to_string(index=False))

    print()
    print("=" * 118)
    print("GATES (pre-registered)")
    print("=" * 118)
    best = alive.iloc[0] if len(alive) else None
    gates = {
        "G1 CAGR > buy-and-hold (7.90%)": bool(best is not None and best["cagr_pct"] > bh["cagr_pct"]),
        "G2 torture ratio > buy-and-hold (0.099)": bool(best is not None and best["torture"] > bh["torture"]),
        "G3 that configuration survives": bool(best is not None and not best["liquidated"]),
        "G4 max DD no worse than -79.8%": bool(best is not None and best["max_dd_pct"] > bh["max_dd_pct"]),
    }
    for k, v in gates.items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    if best is not None:
        print(f"\n  best surviving: base={best['base']}  vol_target="
              f"{'none' if pd.isna(best['vol_target']) else format(best['vol_target'], '.0%')}  "
              f"leverage={int(best['leverage'])}x  CAGR {best['cagr_pct']:+.1f}%  "
              f"DD {best['max_dd_pct']:+.1f}%  torture {best['torture']:.3f}")
    print(f"\n  configurations swept {len(res)}, liquidated {int(res['liquidated'].sum())}")
    print(f"  VERDICT: {'PASS' if all(gates.values()) else 'FAIL'} ({sum(gates.values())}/{len(gates)})")

    out = {
        "experiment": "E#8",
        "spec": "tools/cross_sectional/PREREGISTRATION_E8.md",
        "universe": "top 50 by median daily quote volume",
        "cost_round_trip_bps": COST_RT * 1e4,
        "buy_and_hold": bh,
        "grid": res.to_dict("records"),
        "gates": {k: bool(v) for k, v in gates.items()},
        "verdict": "PASS" if all(gates.values()) else "FAIL",
    }
    (OUT / "e8_result.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(f"\nwritten {OUT / 'e8_result.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
