"""THE DECISIVE TEST: is it VOLUME, or is it just SPEED?

ma200_vs_vwma.py compared VWMA-50 against MA200 -- but those differ in TWO ways:
  * window:    50 days  vs  200 days   <-- SPEED
  * weighting: volume   vs  equal      <-- VOLUME

So a VWMA-50 win proves nothing about volume. The disagreement analysis there
showed VWMA was "right" on both sides of every disagreement -- but a faster
moving average is right at turning points BY CONSTRUCTION.

This script holds the window FIXED and varies only the weighting:
    SMA(N)  vs  VWMA(N)   for N = 20, 50, 100, 200

If VWMA(N) ~= SMA(N) at the same N, then volume adds nothing and the whole
apparent edge was just a shorter lookback.
"""

import numpy as np
import pandas as pd

from volume_signal_study import (
    MAJORS, PPY, block_idx, load_panel, run, shp, stats,
)

COST = 10.0


def ew_price(close: pd.DataFrame) -> pd.Series:
    return close.mean(axis=1, skipna=True)


def sma_exposure(close: pd.DataFrame, window: int) -> pd.Series:
    """Equal-weight SMA of price. No volume anywhere."""
    c = ew_price(close)
    ma = c.rolling(window, min_periods=window).mean()
    valid = ma.notna()
    out = pd.Series(0.5, index=close.index)
    out[valid] = np.where(c[valid] > ma[valid], 1.0, 0.5)
    return out


def vwma_exposure(close: pd.DataFrame, volume: pd.DataFrame, window: int) -> pd.Series:
    """Volume-weighted MA of price. Same window, volume-weighted."""
    c = ew_price(close)
    v = volume.sum(axis=1, min_count=1)
    num = (c * v).rolling(window, min_periods=window).sum()
    den = v.rolling(window, min_periods=window).sum()
    vw = num / den
    valid = vw.notna()
    out = pd.Series(0.5, index=close.index)
    out[valid] = np.where(c[valid] > vw[valid], 1.0, 0.5)
    return out


def main() -> None:
    close, volume = load_panel(MAJORS)
    rets = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    ew = rets.mean(axis=1, skipna=True).fillna(0.0)
    start = "2019-01-01"
    ew, close, volume = ew.loc[start:], close.loc[start:], volume.loc[start:]
    n_years = len(ew) / PPY

    bh = stats(run(ew, pd.Series(1.0, index=ew.index), 0.0))
    print("=" * 96)
    print("# DECISIVE TEST — same window, only the WEIGHTING changes")
    print("=" * 96)
    print(f"window {ew.index[0].date()} -> {ew.index[-1].date()} ({n_years:.1f}y), "
          f"{COST:.0f}bps")
    print(f"buy & hold: {bh['cagr']:.2%} CAGR, {bh['maxdd']:.2%} DD, "
          f"Sharpe {bh['sharpe']:.2f}\n")

    def cell(m: dict) -> str:
        return f"{m['cagr']:>7.2%} / {m['maxdd']:>8.2%} / SR {m['sharpe']:>5.2f}"

    print(f"  {'window':<8} {'SMA (price only)':<34} {'VWMA (volume-weighted)':<34} "
          f"{'delta':>7}")
    rows = []
    for w in (20, 50, 100, 200):
        s = sma_exposure(close, w)
        v = vwma_exposure(close, volume, w)
        ms = stats(run(ew, s, COST))
        mv = stats(run(ew, v, COST))
        rows.append((w, s, v, ms, mv))
        print(f"  {w:<8} {cell(ms):<34} {cell(mv):<34} "
              f"{mv['sharpe'] - ms['sharpe']:>+7.2f}")

    print(f"\n  Average |delta| across windows: "
          f"{np.mean([abs(mv['sharpe']-ms['sharpe']) for _,_,_,ms,mv in rows]):.3f}")

    # Paired bootstrap at each window
    print(f"\n{'=' * 96}")
    print("# PAIRED BOOTSTRAP — Sharpe(VWMA) - Sharpe(SMA), same window")
    print(f"{'=' * 96}")
    rng = np.random.default_rng(31)
    n = len(ew)
    print(f"\n  {'window':<8} {'dSharpe':>9} {'95% CI':>20} {'p(<=0)':>8}  verdict")
    for w, s, v, ms, mv in rows:
        ps = s.shift(1).fillna(0.0)
        pv = v.shift(1).fillna(0.0)
        ts = ps.diff().abs().fillna(ps.abs())
        tv = pv.diff().abs().fillna(pv.abs())
        rs = (ps * ew - ts * COST / 10_000).to_numpy()
        rv = (pv * ew - tv * COST / 10_000).to_numpy()
        point = shp(rv) - shp(rs)
        b = np.array([shp(rv[i]) - shp(rs[i])
                      for i in (block_idx(n, 20, rng) for _ in range(5000))])
        lo, hi = np.percentile(b, [2.5, 97.5])
        verdict = "volume helps" if lo > 0 else "no volume effect"
        print(f"  {w:<8} {point:>+9.3f} {f'[{lo:+.2f}, {hi:+.2f}]':>20} "
              f"{float((b <= 0).mean()):>8.3f}  {verdict}")

    # The speed question, for contrast
    print(f"\n{'=' * 96}")
    print("# FOR CONTRAST — the SPEED effect (same weighting, different window)")
    print(f"{'=' * 96}")
    print(f"\n  {'comparison':<28} {'dSharpe':>9} {'95% CI':>20}  verdict")
    for a_w, b_w in ((20, 200), (50, 200), (100, 200)):
        ea = sma_exposure(close, a_w).shift(1).fillna(0.0)
        eb = sma_exposure(close, b_w).shift(1).fillna(0.0)
        ta = ea.diff().abs().fillna(ea.abs())
        tb = eb.diff().abs().fillna(eb.abs())
        ra = (ea * ew - ta * COST / 10_000).to_numpy()
        rb = (eb * ew - tb * COST / 10_000).to_numpy()
        point = shp(ra) - shp(rb)
        b = np.array([shp(ra[i]) - shp(rb[i])
                      for i in (block_idx(n, 20, rng) for _ in range(5000))])
        lo, hi = np.percentile(b, [2.5, 97.5])
        print(f"  {'SMA' + str(a_w) + ' vs SMA' + str(b_w):<28} {point:>+9.3f} "
              f"{f'[{lo:+.2f}, {hi:+.2f}]':>20}  "
              f"{'SIGNIFICANT' if lo > 0 else 'not significant'}")

    # Verdict
    print(f"\n{'=' * 96}")
    print("# VERDICT")
    print("=" * 96)
    deltas = [abs(mv["sharpe"] - ms["sharpe"]) for _, _, _, ms, mv in rows]
    any_sig = False
    for w, s, v, ms, mv in rows:
        ps = s.shift(1).fillna(0.0)
        pv = v.shift(1).fillna(0.0)
        ts = ps.diff().abs().fillna(ps.abs())
        tv = pv.diff().abs().fillna(pv.abs())
        rs = (ps * ew - ts * COST / 10_000).to_numpy()
        rv = (pv * ew - tv * COST / 10_000).to_numpy()
        b = np.array([shp(rv[i]) - shp(rs[i])
                      for i in (block_idx(n, 20, rng) for _ in range(2000))])
        if np.percentile(b, 2.5) > 0:
            any_sig = True
    print(f"\n  Mean |Sharpe difference| between SMA and VWMA at the same window: "
          f"{np.mean(deltas):.3f}")
    if not any_sig:
        print("  No window shows a significant volume effect.")
        print("  => The apparent VWMA 'edge' was SPEED (50 vs 200), not VOLUME.")
        print("  => Volume weighting adds nothing measurable over a plain SMA.")
    else:
        print("  At least one window shows a significant volume effect — "
              "worth a closer look.")


if __name__ == "__main__":
    main()
