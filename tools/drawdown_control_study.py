"""Drawdown control on large-cap majors — with matched-exposure controls.

The handoff's central warning (README, SPEC §4.3):

    「降低回撤」本身不证明信号有价值。
    H3 的 200 次置换检验证明：随机减仓也能得到类似的回撤改善。

So the naive comparison (vol-targeted vs buy & hold) is MEANINGLESS: any rule
that holds less risk will show a smaller drawdown. Two controls are mandatory:

  1. CONSTANT-EXPOSURE control at the same average exposure. If the dynamic
     rule cannot beat a flat position of identical average size, its "timing"
     is worthless — all the benefit came from holding less.
  2. WILDCARD/random-exposure control with the same mean AND a similar
     run structure.

Only if a rule beats BOTH does it contain real timing information.

Universe is deliberately large-cap majors only (no meme coins, no micro alts),
because those go to zero and their risk is not controllable.
"""

import glob
import os

import numpy as np
import pandas as pd

DATA_DIR = "user_data/data/binance"
PPY = 365  # crypto trades every day

# Established large caps only. Deliberately excludes meme coins (DOGE, SHIB)
# and micro alts whose downside is not controllable.
MAJORS = [
    "BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "AVAX", "DOT", "LINK",
    "LTC", "BCH", "ATOM", "UNI", "AAVE", "XLM", "ETC", "ALGO", "FIL",
    "NEO", "TRX",
]


def load_panel(majors: list[str]) -> pd.DataFrame:
    series = {}
    for m in majors:
        path = os.path.join(DATA_DIR, f"{m}_USDT-1d.feather")
        if not os.path.exists(path):
            continue
        df = pd.read_feather(path).sort_values("date").drop_duplicates("date")
        series[f"{m}/USDT"] = df.set_index("date")["close"].astype(float)
    return pd.DataFrame(series).sort_index()


def max_dd(eq: pd.Series) -> float:
    return float((eq / eq.cummax() - 1.0).min())


def cagr(eq: pd.Series) -> float:
    years = len(eq) / PPY
    return float((eq.iloc[-1] / eq.iloc[0]) ** (1 / years) - 1) if years > 0 else np.nan


def sharpe(r: pd.Series) -> float:
    sd = r.std()
    return float(r.mean() / sd * np.sqrt(PPY)) if sd and not np.isnan(sd) else np.nan


def stats(eq: pd.Series) -> dict:
    return {
        "final": float(eq.iloc[-1]),
        "cagr": cagr(eq),
        "maxdd": max_dd(eq),
        "sharpe": sharpe(eq.pct_change().dropna()),
    }


def fmt(m: dict) -> str:
    return (f"${m['final']:>10,.0f}  CAGR {m['cagr']:>7.2%}  "
            f"MaxDD {m['maxdd']:>7.2%}  Sharpe {m['sharpe']:>5.2f}")


def run(returns: pd.Series, exposure: pd.Series, cost_bps: float,
        initial: float = 10_000.0) -> pd.Series:
    """exposure[t] decided at close[t], realised at t+1 (single lag point)."""
    pos = exposure.shift(1).fillna(0.0)
    turnover = pos.diff().abs().fillna(pos.abs())
    net = pos * returns - turnover * (cost_bps / 10_000.0)
    return initial * (1.0 + net).cumprod()


# ---------------------------------------------------------------- exposure rules

def vol_target(returns: pd.Series, target_vol: float, window: int = 30,
               cap: float = 1.0) -> pd.Series:
    """Scale exposure inversely to realised vol, capped at `cap`."""
    realised = returns.rolling(window, min_periods=window).std() * np.sqrt(PPY)
    raw = target_vol / realised
    return raw.clip(upper=cap).fillna(0.0)


def trend_filter(close: pd.Series, window: int = 200) -> pd.Series:
    ma = close.rolling(window, min_periods=window).mean()
    valid = ma.notna()
    out = pd.Series(0.0, index=close.index)
    out[valid] = np.where(close[valid] > ma[valid], 1.0, 0.5)
    return out


def vol_plus_trend(returns: pd.Series, close: pd.Series, target_vol: float,
                   window: int = 30) -> pd.Series:
    vt = vol_target(returns, target_vol, window)
    tf = trend_filter(close)
    return (vt * tf).clip(upper=1.0)


def wildcard(mean_exposure: float, n: int, index, block: int,
             rng: np.random.Generator) -> pd.Series:
    """Random exposure with matched mean and similar run structure.

    Built by sampling the mean exposure in blocks, which preserves persistence
    (a real exposure rule does not flip every single day).
    """
    n_blocks = int(np.ceil(n / block))
    vals = rng.random(n_blocks) < mean_exposure
    seq = np.repeat(vals, block)[:n]
    return pd.Series(seq.astype(float), index=index)


def main() -> None:
    close = load_panel(MAJORS)
    print(f"majors universe: {close.shape[1]} pairs   "
          f"{close.index[0].date()} -> {close.index[-1].date()}")
    print("excluded meme/micro alts by construction (DOGE, SHIB, ...)\n")

    rets = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    # Equal-weight portfolio of all majors.
    ew_ret = rets.mean(axis=1, skipna=True).fillna(0.0)

    # Evaluate from 2019-01-01 so every rule has warmed up.
    start = "2019-01-01"
    ew_ret = ew_ret.loc[start:]
    btc_close = close["BTC/USDT"].loc[start:]
    print(f"window: {ew_ret.index[0].date()} -> {ew_ret.index[-1].date()}  "
          f"({len(ew_ret) / PPY:.1f} years)")
    se_note = f"Sharpe standard error ~ 1/sqrt({len(ew_ret) / PPY:.1f}) = " \
              f"{1 / np.sqrt(len(ew_ret) / PPY):.2f}"
    print(f"NOTE: {se_note}\n")

    bh = run(ew_ret, pd.Series(1.0, index=ew_ret.index), 0.0)
    print(f"{'=' * 94}")
    print("# BASELINE")
    print(f"{'=' * 94}")
    print(f"  {'equal-weight buy & hold':<30} {fmt(stats(bh))}")

    # ---- Rules ----
    rules = {
        "vol target 60%": vol_target(ew_ret, 0.60),
        "vol target 40%": vol_target(ew_ret, 0.40),
        "trend filter (MA200)": trend_filter(btc_close),
        "vol 60% + trend": vol_plus_trend(ew_ret, btc_close, 0.60),
        "vol 40% + trend": vol_plus_trend(ew_ret, btc_close, 0.40),
    }

    print(f"\n{'=' * 94}")
    print("# RULES (10bps) — and the MATCHED CONSTANT-EXPOSURE control")
    print("#   If the dynamic rule cannot beat a FLAT position of the same")
    print("#   average size, its timing is worthless.")
    print(f"{'=' * 94}")
    print(f"\n  {'rule':<24} {'avg exp':>8}  {'dynamic rule':<52} {'flat control':<52}")
    stored = {}
    for name, expo in rules.items():
        expo = expo.reindex(ew_ret.index).fillna(0.0)
        avg = float(expo.mean())
        dyn = run(ew_ret, expo, 10.0)
        flat = run(ew_ret, pd.Series(avg, index=ew_ret.index), 10.0)
        stored[name] = (expo, dyn, flat, avg)
        print(f"  {name:<24} {avg:>7.1%}  {fmt(stats(dyn))}")
        print(f"  {'':<24} {'':>8}  {'flat @ same avg:':<52} {fmt(stats(flat))}")
        d, f = stats(dyn), stats(flat)
        verdict = "TIMING ADDS VALUE" if d["sharpe"] > f["sharpe"] else "no better than flat"
        print(f"  {'':<24} {'':>8}  -> Sharpe {d['sharpe']:.2f} vs {f['sharpe']:.2f}  "
              f"[{verdict}]\n")

    # ---- Wildcard placebo at matched mean ----
    print(f"{'=' * 94}")
    print("# WILDCARD PLACEBO — random exposure, matched mean, 200 draws (10bps)")
    print("#   p = fraction of random paths beating the real rule.")
    print(f"{'=' * 94}")
    rng = np.random.default_rng(7)
    print(f"\n  {'rule':<24} {'real Sharpe':>12} {'real MaxDD':>12} "
          f"{'p(Sharpe)':>10} {'p(MaxDD)':>10}  verdict")
    for name, (expo, dyn, flat, avg) in stored.items():
        d = stats(dyn)
        sh, dd = [], []
        for _ in range(200):
            w = wildcard(avg, len(ew_ret), ew_ret.index, block=30, rng=rng)
            m = stats(run(ew_ret, w, 10.0))
            sh.append(m["sharpe"])
            dd.append(m["maxdd"])
        sh, dd = np.array(sh), np.array(dd)
        p_sh = float((sh >= d["sharpe"]).mean())
        p_dd = float((dd >= d["maxdd"]).mean())
        verdict = "REAL (p<0.05)" if p_sh < 0.05 else "indistinguishable"
        print(f"  {name:<24} {d['sharpe']:>12.2f} {d['maxdd']:>12.2%} "
              f"{p_sh:>10.3f} {p_dd:>10.3f}  {verdict}")

    # ---- Cost sensitivity ----
    print(f"\n{'=' * 94}")
    print("# COST SENSITIVITY")
    print(f"{'=' * 94}")
    for name in ("vol target 60%", "vol 60% + trend"):
        expo = stored[name][0]
        print(f"\n  {name}")
        for c in (0.0, 10.0, 20.0, 50.0):
            print(f"    {c:>4.0f}bps  {fmt(stats(run(ew_ret, expo, c)))}")

    # ---- One-bar shift test ----
    print(f"\n{'=' * 94}")
    print("# ONE-BAR SHIFT TEST (vol 60% + trend, 10bps)")
    print("#   Graceful degradation = no look-ahead; collapse = artifact.")
    print(f"{'=' * 94}")
    expo = stored["vol 60% + trend"][0]
    for extra in (1, 2, 3):
        e = expo.shift(extra - 1).fillna(0.0)
        m = stats(run(ew_ret, e, 10.0))
        print(f"  extra lag {extra - 1}: {fmt(m)}")

    # ---- Sub-period ----
    print(f"\n{'=' * 94}")
    print("# SUB-PERIOD: vol 60% + trend vs buy & hold")
    print(f"{'=' * 94}")
    expo = stored["vol 60% + trend"][0]
    eq_rule = run(ew_ret, expo, 10.0)
    eq_bh = run(ew_ret, pd.Series(1.0, index=ew_ret.index), 0.0)
    print(f"\n  {'year':<8} {'buy & hold':>12} {'rule':>12} {'BH MaxDD':>11} "
          f"{'rule MaxDD':>12}")
    for y in range(2019, 2027):
        mask = eq_rule.index.year == y
        if mask.sum() < 30:
            continue
        a, b = eq_bh[mask], eq_rule[mask]
        print(f"  {y:<8} {a.iloc[-1]/a.iloc[0]-1:>12.1%} {b.iloc[-1]/b.iloc[0]-1:>12.1%} "
              f"{max_dd(a):>11.2%} {max_dd(b):>12.2%}")

    # ---- Sharpe CI + paired bootstrap vs the flat control ----
    # Lo (2002): the annualised Sharpe standard error is ~1/sqrt(years),
    # independent of sampling frequency. With 7.7 years that is +/-0.36, which
    # swamps every difference observed above.
    print(f"\n{'=' * 94}")
    print("# IS THE EDGE REAL? Sharpe CI + paired bootstrap vs flat control")
    print(f"{'=' * 94}")
    n_years = len(ew_ret) / PPY
    se = 1.0 / np.sqrt(n_years)
    print(f"\n  Lo (2002): SE(annualised Sharpe) ~ 1/sqrt({n_years:.1f}) = {se:.3f}")
    print(f"  So a Sharpe of 0.85 has a 95% CI of roughly "
          f"[{0.85 - 1.96 * se:.2f}, {0.85 + 1.96 * se:.2f}]")
    print("\n  Paired block bootstrap on Sharpe(rule) - Sharpe(flat), 5000 draws:")
    print(f"\n  {'rule':<24} {'dSharpe':>9} {'95% CI':>20} {'p(<=0)':>8}  verdict")

    def block_bootstrap_idx(n: int, block: int, rng: np.random.Generator) -> np.ndarray:
        n_blocks = int(np.ceil(n / block))
        starts = rng.integers(0, n, n_blocks)
        idx = np.concatenate([(np.arange(s, s + block) % n) for s in starts])
        return idx[:n]

    def shp(x: np.ndarray) -> float:
        sd = x.std()
        return float(x.mean() / sd * np.sqrt(PPY)) if sd > 0 else 0.0

    rng2 = np.random.default_rng(11)
    for name, (expo, dyn, flat, avg) in stored.items():
        pos = expo.shift(1).fillna(0.0)
        turn = pos.diff().abs().fillna(pos.abs())
        r_rule = (pos * ew_ret - turn * 0.001).to_numpy()
        r_flat = (avg * ew_ret).to_numpy()
        n = len(r_rule)

        # NOTE: the statistic must be the DIFFERENCE OF SHARPES, not the Sharpe
        # of the difference series -- the latter measures something else and can
        # flip sign even when the two Sharpes are nearly identical.
        point = shp(r_rule) - shp(r_flat)
        boots = []
        for _ in range(5000):
            idx = block_bootstrap_idx(n, 20, rng2)
            boots.append(shp(r_rule[idx]) - shp(r_flat[idx]))
        boots = np.array(boots)
        lo, hi = np.percentile(boots, [2.5, 97.5])
        p_le0 = float((boots <= 0).mean())
        verdict = "significant" if lo > 0 else "NOT significant"
        print(f"  {name:<24} {point:>9.3f} "
              f"{f'[{lo:>6.2f}, {hi:>6.2f}]':>20} {p_le0:>8.3f}  {verdict}")

    # ---- Per-asset consistency ----
    print(f"\n{'=' * 94}")
    print("# PER-ASSET: drawdown improvement (vol 60% + trend, 10bps)")
    print("#   Cross-asset replication is the strongest anti-overfit evidence.")
    print(f"{'=' * 94}")
    print(f"\n  {'pair':<12} {'BH CAGR':>9} {'rule CAGR':>10} {'BH MaxDD':>10} "
          f"{'rule MaxDD':>11}  better?")
    wins = 0
    pairs = [c for c in close.columns]
    for p in pairs:
        r = rets[p].loc[start:].fillna(0.0)
        cl = close[p].loc[start:]
        e = vol_plus_trend(r, cl, 0.60).reindex(r.index).fillna(0.0)
        b = stats(run(r, pd.Series(1.0, index=r.index), 0.0))
        d = stats(run(r, e, 10.0))
        better = d["maxdd"] > b["maxdd"]
        wins += better
        print(f"  {p:<12} {b['cagr']:>9.2%} {d['cagr']:>10.2%} "
              f"{b['maxdd']:>10.2%} {d['maxdd']:>11.2%}  {'YES' if better else 'no'}")
    print(f"\n  drawdown improved in {wins}/{len(pairs)} majors")


if __name__ == "__main__":
    main()
