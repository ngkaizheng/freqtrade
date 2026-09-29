"""Funding-rate signals — the first genuinely orthogonal information source tested.

Why this matters
----------------
Everything tested so far was price-derived (MA, VWMA, OBV, momentum) or a
mechanical variation (vol targeting). Volume was refuted: 0.017 Sharpe.

Funding rate is different in kind. It is a REAL payment between longs and
shorts on perpetual futures, set by the exchange to tether the perp to spot:
    positive -> longs pay shorts  (crowded long / bullish positioning)
    negative -> shorts pay longs  (crowded short / bearish positioning)
It is not computed from price, and it is not the price itself.

The natural hypothesis is CONTRARIAN: when positioning is crowded, the crowd
is wrong. This is the same shape as the handoff's H3 test (which failed —
those signals marked oversold-bounce zones, not further downside). So this is
a fair test of a fair idea.

Time alignment (critical)
-------------------------
Binance settles funding at 00:00, 08:00 and 16:00 UTC. The daily candle for
day D covers [D 00:00, D+1 00:00), so all three settlements of day D are known
by day D's close. Deciding exposure at day D's close using day D's funding is
therefore legitimate. The single lag point stays `shift(1)`.
"""

import numpy as np
import pandas as pd

from volume_signal_study import (
    MAJORS, PPY, block_idx, load_panel, run, shp, stats, wildcard,
)
from volume_vs_speed import sma_exposure

FUND_DIR = "user_data/data/binance_funding"
COST = 10.0


def load_funding(majors: list[str]) -> pd.DataFrame:
    out = {}
    for m in majors:
        path = f"{FUND_DIR}/{m}_USDT-funding.feather"
        try:
            df = pd.read_feather(path)
        except FileNotFoundError:
            continue
        s = df.set_index("fundingTime")["fundingRate"].astype(float)
        # Daily total funding paid over day D (3 settlements).
        daily = s.resample("1D").sum()
        out[f"{m}/USDT"] = daily
    fund = pd.DataFrame(out)
    fund.index = fund.index.tz_localize(None) if fund.index.tz else fund.index
    return fund


def to_daily_index(fund: pd.DataFrame, target_index: pd.DatetimeIndex) -> pd.DataFrame:
    """Align funding onto the OHLCV daily index (matching calendar days).

    The OHLCV index is tz-aware UTC while the funding index is tz-naive; pandas
    silently produces all-NaN if you reindex across that mismatch. Both sides
    are therefore reduced to tz-naive normalized dates before aligning.
    """
    f = fund.copy()
    idx = pd.DatetimeIndex(f.index)
    if idx.tz is not None:
        idx = idx.tz_convert("UTC").tz_localize(None)
    f.index = idx.normalize()

    t = pd.DatetimeIndex(target_index)
    if t.tz is not None:
        t = t.tz_convert("UTC").tz_localize(None)
    t = t.normalize()

    f = f.reindex(t)
    f.index = target_index
    return f


# ------------------------------------------------------------- signal families

def sig_funding_level(fund: pd.DataFrame, scale: float = 0.001) -> pd.Series:
    """Contrarian on the pooled funding level.

    Positive funding (crowded long) -> hold less; negative -> hold more.
    Exposure is clipped to [0, 1].
    """
    pooled = fund.mean(axis=1, skipna=True)
    # Smooth slightly so a single settlement does not whipsaw the book.
    pooled = pooled.rolling(3, min_periods=1).mean()
    expo = 1.0 - (pooled / scale)
    return expo.clip(0.0, 1.0)


def sig_funding_percentile(fund: pd.DataFrame, window: int = 90) -> pd.Series:
    """Contrarian on the funding percentile within its own trailing window."""
    pooled = fund.mean(axis=1, skipna=True).rolling(3, min_periods=1).mean()
    rank = pooled.rolling(window, min_periods=window).rank(pct=True)
    return (1.0 - rank).clip(0.0, 1.0)


def sig_funding_extreme(fund: pd.DataFrame, window: int = 90,
                        q: float = 0.9) -> pd.Series:
    """Binary contrarian: only de-risk at genuine funding extremes."""
    pooled = fund.mean(axis=1, skipna=True).rolling(3, min_periods=1).mean()
    hi = pooled.rolling(window, min_periods=window).quantile(q)
    lo = pooled.rolling(window, min_periods=window).quantile(1 - q)
    valid = hi.notna() & lo.notna()
    out = pd.Series(1.0, index=fund.index)
    out[valid & (pooled > hi)] = 0.25      # crowded long -> mostly out
    out[valid & (pooled < lo)] = 1.0       # crowded short -> fully in
    out[~valid] = 0.5
    return out


def sig_funding_trend(fund: pd.DataFrame) -> pd.Series:
    """Momentum flavour: is funding RISING (crowd getting longer)?"""
    pooled = fund.mean(axis=1, skipna=True)
    fast = pooled.rolling(7, min_periods=7).mean()
    slow = pooled.rolling(30, min_periods=30).mean()
    valid = fast.notna() & slow.notna()
    out = pd.Series(0.5, index=fund.index)
    out[valid] = np.where(fast[valid] < slow[valid], 1.0, 0.5)
    return out


def main() -> None:
    close, volume = load_panel(MAJORS)
    fund_raw = load_funding(MAJORS)
    print(f"funding panel: {fund_raw.shape[1]} pairs  "
          f"{fund_raw.index.min().date()} -> {fund_raw.index.max().date()}")

    fund = to_daily_index(fund_raw, close.index)
    rets = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    ew = rets.mean(axis=1, skipna=True).fillna(0.0)

    start = "2020-01-01"  # funding data starts ~2019-09 for BTC, later for others
    ew, close, volume, fund = (x.loc[start:] for x in (ew, close, volume, fund))
    n = len(ew)
    n_years = n / PPY
    se = 1 / np.sqrt(n_years)

    print(f"window {ew.index[0].date()} -> {ew.index[-1].date()} "
          f"({n_years:.1f}y)  SE(Sharpe)~{se:.2f}  cost {COST:.0f}bps")
    cov = float(fund.notna().mean().mean())
    print(f"funding coverage: {cov:.1%} of pair-days present\n")

    bh = stats(run(ew, pd.Series(1.0, index=ew.index), 0.0))
    print("=" * 96)
    print(f"BASELINE equal-weight buy & hold: CAGR {bh['cagr']:.2%}  "
          f"MaxDD {bh['maxdd']:.2%}  Sharpe {bh['sharpe']:.2f}")
    print("=" * 96)

    signals = {
        "funding level (contrarian)": sig_funding_level(fund),
        "funding percentile 90d": sig_funding_percentile(fund),
        "funding extreme 90/10": sig_funding_extreme(fund),
        "funding trend (contrarian)": sig_funding_trend(fund),
    }

    print(f"\n{'=' * 96}")
    print("# SIGNALS vs FLAT CONTROL at matched average exposure")
    print(f"{'=' * 96}")
    print(f"\n  {'signal':<28} {'avgExp':>7} {'CAGR':>9} {'MaxDD':>9} {'Sharpe':>8}"
          f" {'vs flat':>9}")
    stored = {}
    for name, expo in signals.items():
        e = expo.reindex(ew.index).fillna(0.5)
        avg = float(e.mean())
        d = stats(run(ew, e, COST))
        fl = stats(run(ew, pd.Series(avg, index=ew.index), COST))
        stored[name] = (e, d, fl, avg)
        print(f"  {name:<28} {avg:>6.1%} {d['cagr']:>9.2%} {d['maxdd']:>9.2%} "
              f"{d['sharpe']:>8.2f} {d['sharpe'] - fl['sharpe']:>+9.3f}")

    # ---------------- Placebo ----------------
    print(f"\n{'=' * 96}")
    print("# WILDCARD PLACEBO — random exposure, matched mean, 200 draws")
    print("#   4 families tested -> Bonferroni p < 0.0125")
    print(f"{'=' * 96}")
    rng = np.random.default_rng(41)
    print(f"\n  {'signal':<28} {'Sharpe':>8} {'p(Sharpe)':>10} {'p(MaxDD)':>10}  verdict")
    for name, (e, d, fl, avg) in stored.items():
        sh, dd = [], []
        for _ in range(200):
            m = stats(run(ew, wildcard(avg, n, ew.index, 30, rng), COST))
            sh.append(m["sharpe"]); dd.append(m["maxdd"])
        p_sh = float((np.array(sh) >= d["sharpe"]).mean())
        p_dd = float((np.array(dd) >= d["maxdd"]).mean())
        verdict = ("PASSES Bonferroni" if p_sh < 0.0125
                   else "weak (p<0.05)" if p_sh < 0.05
                   else "indistinguishable")
        print(f"  {name:<28} {d['sharpe']:>8.2f} {p_sh:>10.3f} {p_dd:>10.3f}  {verdict}")

    # ---------------- Bootstrap vs flat ----------------
    print(f"\n{'=' * 96}")
    print("# PAIRED BOOTSTRAP — Sharpe(signal) - Sharpe(flat), 5000 draws")
    print(f"{'=' * 96}")
    rng2 = np.random.default_rng(43)
    print(f"\n  {'signal':<28} {'dSharpe':>9} {'95% CI':>20} {'p(<=0)':>8}  verdict")
    for name, (e, d, fl, avg) in stored.items():
        p_ = e.shift(1).fillna(0.0)
        t_ = p_.diff().abs().fillna(p_.abs())
        rr = (p_ * ew - t_ * COST / 10_000).to_numpy()
        rf = (avg * ew).to_numpy()
        point = shp(rr) - shp(rf)
        b = np.array([shp(rr[i]) - shp(rf[i])
                      for i in (block_idx(n, 20, rng2) for _ in range(5000))])
        lo, hi = np.percentile(b, [2.5, 97.5])
        print(f"  {name:<28} {point:>+9.3f} {f'[{lo:+.2f}, {hi:+.2f}]':>20} "
              f"{float((b <= 0).mean()):>8.3f}  "
              f"{'SIGNIFICANT' if lo > 0 else 'not significant'}")

    # ---------------- Does funding add anything ON TOP of trend? ----------------
    print(f"\n{'=' * 96}")
    print("# INCREMENTAL TEST — does funding add anything over a plain SMA-50?")
    print("#   (the handoff's demand: incremental information, not low correlation)")
    print(f"{'=' * 96}")
    sma50 = sma_exposure(close, 50).reindex(ew.index).fillna(0.5)
    best = max(stored.items(), key=lambda kv: kv[1][1]["sharpe"])[0]
    # Rescale the funding rule to SMA50's mean so the comparison is fair.
    fe = stored[best][0]
    target_mean = float(sma50.mean())
    fe_scaled = (fe * (target_mean / max(float(fe.mean()), 1e-9))).clip(0.0, 1.0)
    combo = pd.concat([sma50, fe_scaled], axis=1).min(axis=1)

    print(f"\n  best funding rule: '{best}'")
    print(f"  {'rule':<34} {'avgExp':>7} {'CAGR':>9} {'MaxDD':>9} {'Sharpe':>8}")
    for label, e in (("SMA-50 alone", sma50),
                     (f"{best} (rescaled)", fe_scaled),
                     ("min(SMA-50, funding)", combo)):
        m = stats(run(ew, e, COST))
        print(f"  {label:<34} {float(e.mean()):>6.1%} {m['cagr']:>9.2%} "
              f"{m['maxdd']:>9.2%} {m['sharpe']:>8.2f}")

    # Conditional: within SMA50 risk-on days, does funding still matter?
    mask_on = sma50 >= 1.0
    if mask_on.sum() > 100:
        sub_ew = ew[mask_on]
        sub_f = fe_scaled[mask_on]
        sub_sma = sma50[mask_on]
        a = stats(run(sub_ew, pd.Series(1.0, index=sub_ew.index), COST))
        b_ = stats(run(sub_ew, sub_f, COST))
        print(f"\n  Conditional — within SMA-50 risk-ON days (n={int(mask_on.sum())}):")
        print(f"    always 1.0        : Sharpe {a['sharpe']:.2f}")
        print(f"    funding-scaled    : Sharpe {b_['sharpe']:.2f}")
        print(f"    -> funding {'ADDS' if b_['sharpe'] > a['sharpe'] else 'adds NOTHING'}"
              f" inside the trend-on regime")

    # ---------------- One-bar shift ----------------
    print(f"\n{'=' * 96}")
    print("# ONE-BAR SHIFT TEST (look-ahead check)")
    print(f"{'=' * 96}")
    for name in (best,):
        e = stored[name][0]
        for extra in range(3):
            ee = e.shift(extra).fillna(0.5) if extra else e
            m = stats(run(ew, ee, COST))
            print(f"  {name} lag {extra}: CAGR {m['cagr']:>7.2%}  "
                  f"MaxDD {m['maxdd']:>7.2%}  Sharpe {m['sharpe']:>5.2f}")

    # ---------------- Per-asset ----------------
    print(f"\n{'=' * 96}")
    print(f"# PER-ASSET — '{best}' applied to each pair (vs buy & hold)")
    print(f"{'=' * 96}")
    print(f"\n  {'pair':<12} {'BH SR':>8} {'sig SR':>8} {'better?':>9}")
    wins = 0
    tot = 0
    for p in close.columns:
        if p not in fund.columns or fund[p].notna().sum() < 200:
            continue
        r = rets[p].fillna(0.0)
        f1 = fund[[p]]
        fn = {
            "funding level (contrarian)": sig_funding_level,
            "funding percentile 90d": sig_funding_percentile,
            "funding extreme 90/10": sig_funding_extreme,
            "funding trend (contrarian)": sig_funding_trend,
        }[best]
        e = fn(f1).reindex(r.index).fillna(0.5)
        b = stats(run(r, pd.Series(1.0, index=r.index), 0.0))
        d = stats(run(r, e, COST))
        tot += 1
        wins += d["sharpe"] > b["sharpe"]
        print(f"  {p:<12} {b['sharpe']:>8.2f} {d['sharpe']:>8.2f} "
              f"{'YES' if d['sharpe'] > b['sharpe'] else 'no':>9}")
    print(f"\n  beat buy & hold in {wins}/{tot} pairs")


if __name__ == "__main__":
    main()
