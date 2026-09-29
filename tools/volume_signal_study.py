"""Volume-based signals on large-cap majors — tested the same way as everything else.

Why volume is a genuinely different hypothesis
----------------------------------------------
MA, RSI, Bollinger are all transformations of PRICE — they carry no information
the price does not already contain. Volume is a second, largely orthogonal
dimension. That is why "look at volume" is a reasonable instinct.

But be warned: the handoff already tested adding a new information dimension
(H3: VIX / credit / breadth) and it FAILED — the signals pointed the wrong way
(they marked oversold-bounce zones, not further-downside zones) and did not
exceed placebo. So this is a fair test of a fair idea, not a promising lead.

Signal families tested (all long-only exposure scaling, no shorting):
  1. volume trend     — is volume rising or falling vs its own average
  2. volume spike     — capitulation: huge volume + down move
  3. volume breakout  — price breakout CONFIRMED by volume
  4. OBV trend        — on-balance-volume slope (cumulative signed volume)
  5. volume-weighted MA — VWMA vs price (volume-weighted trend)

Every one is measured against:
  * equal-weight buy & hold of the same pool
  * a FLAT control at the same average exposure  <-- the handoff's key demand
  * a random-exposure placebo matched on mean + run structure
"""

import glob
import os

import numpy as np
import pandas as pd

DATA_DIR = "user_data/data/binance"
PPY = 365

MAJORS = [
    "BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "AVAX", "DOT", "LINK",
    "LTC", "BCH", "ATOM", "UNI", "AAVE", "XLM", "ETC", "ALGO", "FIL",
    "NEO", "TRX",
]


def load_panel(majors: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    close, volume = {}, {}
    for m in majors:
        path = os.path.join(DATA_DIR, f"{m}_USDT-1d.feather")
        if not os.path.exists(path):
            continue
        df = pd.read_feather(path).sort_values("date").drop_duplicates("date")
        idx = df.set_index("date")
        close[f"{m}/USDT"] = idx["close"].astype(float)
        volume[f"{m}/USDT"] = idx["volume"].astype(float)
    return pd.DataFrame(close).sort_index(), pd.DataFrame(volume).sort_index()


def max_dd(eq: pd.Series) -> float:
    return float((eq / eq.cummax() - 1.0).min())


def cagr(eq: pd.Series) -> float:
    years = len(eq) / PPY
    return float((eq.iloc[-1] / eq.iloc[0]) ** (1 / years) - 1) if years > 0 else np.nan


def sharpe(r: pd.Series) -> float:
    sd = r.std()
    return float(r.mean() / sd * np.sqrt(PPY)) if sd and sd > 0 else np.nan


def stats(eq: pd.Series) -> dict:
    return {"final": float(eq.iloc[-1]), "cagr": cagr(eq),
            "maxdd": max_dd(eq), "sharpe": sharpe(eq.pct_change().dropna())}


def fmt(m: dict) -> str:
    return (f"CAGR {m['cagr']:>7.2%}  MaxDD {m['maxdd']:>7.2%}  "
            f"Sharpe {m['sharpe']:>5.2f}")


def run(returns: pd.Series, exposure: pd.Series, cost_bps: float,
        initial: float = 10_000.0) -> pd.Series:
    """exposure[t] decided on close[t], realised at t+1 — the single lag point."""
    pos = exposure.shift(1).fillna(0.0)
    turnover = pos.diff().abs().fillna(pos.abs())
    return initial * (1.0 + (pos * returns - turnover * cost_bps / 10_000.0)).cumprod()


# ------------------------------------------------------------ signal families

def sig_volume_trend(close: pd.DataFrame, volume: pd.DataFrame,
                     short: int = 10, long: int = 30) -> pd.Series:
    """Exposure 1.0 when aggregate volume is above its longer-run average."""
    v = volume.sum(axis=1, min_count=1)
    fast = v.rolling(short, min_periods=short).mean()
    slow = v.rolling(long, min_periods=long).mean()
    valid = fast.notna() & slow.notna()
    out = pd.Series(0.5, index=close.index)
    out[valid] = np.where(fast[valid] > slow[valid], 1.0, 0.5)
    return out


def sig_volume_spike(close: pd.DataFrame, volume: pd.DataFrame,
                     window: int = 30, mult: float = 2.0) -> pd.Series:
    """Capitulation: exposure up after a high-volume DOWN day (mean reversion)."""
    ret = close.mean(axis=1, skipna=True).pct_change(fill_method=None)
    v = volume.sum(axis=1, min_count=1)
    avg = v.rolling(window, min_periods=window).mean()
    spike = (v > mult * avg) & (ret < 0)
    valid = avg.notna()
    out = pd.Series(0.5, index=close.index)
    out[valid] = 0.5
    out[spike & valid] = 1.0
    return out.ffill().fillna(0.5)


def sig_volume_breakout(close: pd.DataFrame, volume: pd.DataFrame,
                        window: int = 30) -> pd.Series:
    """Price above its N-day high AND volume confirming — else stay light."""
    c = close.mean(axis=1, skipna=True)
    roll_max = c.rolling(window, min_periods=window).max()
    v = volume.sum(axis=1, min_count=1)
    vavg = v.rolling(window, min_periods=window).mean()
    valid = roll_max.notna() & vavg.notna()
    breakout = (c >= roll_max) & (v > vavg)
    out = pd.Series(0.5, index=close.index)
    out[valid] = 0.5
    out[breakout & valid] = 1.0
    return out


def sig_obv(close: pd.DataFrame, volume: pd.DataFrame,
            window: int = 30) -> pd.Series:
    """On-balance volume: cumulative signed volume vs its own moving average."""
    obv_all = []
    for col in close.columns:
        c = close[col]
        v = volume[col]
        sign = np.sign(c.diff().fillna(0.0))
        obv_all.append((sign * v).cumsum())
    obv = pd.concat(obv_all, axis=1).sum(axis=1, min_count=1)
    ma = obv.rolling(window, min_periods=window).mean()
    valid = ma.notna()
    out = pd.Series(0.5, index=close.index)
    out[valid] = np.where(obv[valid] > ma[valid], 1.0, 0.5)
    return out


def sig_vwma(close: pd.DataFrame, volume: pd.DataFrame,
             window: int = 50) -> pd.Series:
    """Volume-weighted moving average of the equal-weight price vs price."""
    c = close.mean(axis=1, skipna=True)
    v = volume.sum(axis=1, min_count=1)
    num = (c * v).rolling(window, min_periods=window).sum()
    den = v.rolling(window, min_periods=window).sum()
    vwma = num / den
    valid = vwma.notna()
    out = pd.Series(0.5, index=close.index)
    out[valid] = np.where(c[valid] > vwma[valid], 1.0, 0.5)
    return out


def wildcard(mean_exp: float, n: int, index, block: int,
             rng: np.random.Generator) -> pd.Series:
    nb = int(np.ceil(n / block))
    vals = rng.random(nb) < mean_exp
    return pd.Series(np.repeat(vals, block)[:n].astype(float), index=index)


def shp(x: np.ndarray) -> float:
    sd = x.std()
    return float(x.mean() / sd * np.sqrt(PPY)) if sd > 0 else 0.0


def block_idx(n: int, block: int, rng: np.random.Generator) -> np.ndarray:
    nb = int(np.ceil(n / block))
    starts = rng.integers(0, n, nb)
    return np.concatenate([(np.arange(s, s + block) % n) for s in starts])[:n]


def main() -> None:
    close, volume = load_panel(MAJORS)
    print(f"majors: {close.shape[1]} pairs   "
          f"{close.index[0].date()} -> {close.index[-1].date()}")
    print("meme/micro alts excluded by construction\n")

    rets = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    ew = rets.mean(axis=1, skipna=True).fillna(0.0)

    start = "2019-01-01"
    ew = ew.loc[start:]
    close = close.loc[start:]
    volume = volume.loc[start:]
    rets = rets.loc[start:]

    n_years = len(ew) / PPY
    se = 1 / np.sqrt(n_years)
    print(f"window {ew.index[0].date()} -> {ew.index[-1].date()} ({n_years:.1f}y)   "
          f"SE(Sharpe)~{se:.2f}\n")

    bh = run(ew, pd.Series(1.0, index=ew.index), 0.0)
    bh_s = stats(bh)
    print("=" * 96)
    print(f"BASELINE equal-weight buy & hold: {fmt(bh_s)}")
    print("=" * 96)

    signals = {
        "volume trend 10/30": sig_volume_trend(close, volume),
        "volume spike 2x": sig_volume_spike(close, volume),
        "volume breakout": sig_volume_breakout(close, volume),
        "OBV trend 30": sig_obv(close, volume),
        "VWMA 50": sig_vwma(close, volume),
    }

    print(f"\n{'=' * 96}")
    print("# SIGNALS vs FLAT CONTROL — flat = a constant position of the same avg size")
    print(f"{'=' * 96}")
    print(f"\n  {'signal':<22} {'avgExp':>7} {'dynamic':<40} {'flat control':<40}")
    stored = {}
    for name, expo in signals.items():
        expo = expo.reindex(ew.index).fillna(0.5)
        avg = float(expo.mean())
        dyn = run(ew, expo, 10.0)
        flat = run(ew, pd.Series(avg, index=ew.index), 10.0)
        stored[name] = (expo, dyn, flat, avg)
        d, f = stats(dyn), stats(flat)
        print(f"  {name:<22} {avg:>6.1%}  {fmt(d)}")
        print(f"  {'':<22} {'':>7}  {'flat same avg:':<40} {fmt(f)}")
        print(f"  {'':<22} {'':>7}  -> vs flat: dSharpe {d['sharpe']-f['sharpe']:+.3f}  "
              f"{'BEATS flat' if d['sharpe'] > f['sharpe'] else 'no better than flat'}\n")

    # ---- Wildcard placebo ----
    print(f"{'=' * 96}")
    print("# WILDCARD PLACEBO — random exposure, matched mean, 200 draws, 10bps")
    print(f"{'=' * 96}")
    rng = np.random.default_rng(3)
    print(f"\n  {'signal':<22} {'Sharpe':>8} {'MaxDD':>9} {'p(Sharpe)':>10} "
          f"{'p(MaxDD)':>9}  verdict")
    for name, (expo, dyn, flat, avg) in stored.items():
        d = stats(dyn)
        sh, dd = [], []
        for _ in range(200):
            w = wildcard(avg, len(ew), ew.index, 30, rng)
            m = stats(run(ew, w, 10.0))
            sh.append(m["sharpe"]); dd.append(m["maxdd"])
        p_sh = float((np.array(sh) >= d["sharpe"]).mean())
        p_dd = float((np.array(dd) >= d["maxdd"]).mean())
        # 5 families tested -> Bonferroni threshold 0.01
        verdict = "REAL (p<0.01)" if p_sh < 0.01 else (
            "weak (p<0.05)" if p_sh < 0.05 else "indistinguishable")
        print(f"  {name:<22} {d['sharpe']:>8.2f} {d['maxdd']:>9.2%} "
              f"{p_sh:>10.3f} {p_dd:>9.3f}  {verdict}")

    # ---- Paired bootstrap vs flat ----
    print(f"\n{'=' * 96}")
    print("# PAIRED BLOCK BOOTSTRAP — Sharpe(signal) - Sharpe(flat), 5000 draws")
    print(f"{'=' * 96}")
    rng2 = np.random.default_rng(5)
    print(f"\n  {'signal':<22} {'dSharpe':>9} {'95% CI':>20} {'p(<=0)':>8}  verdict")
    for name, (expo, dyn, flat, avg) in stored.items():
        pos = expo.shift(1).fillna(0.0)
        turn = pos.diff().abs().fillna(pos.abs())
        rr = (pos * ew - turn * 0.001).to_numpy()
        rf = (avg * ew).to_numpy()
        n = len(rr)
        point = shp(rr) - shp(rf)
        boots = []
        for _ in range(5000):
            i = block_idx(n, 20, rng2)
            boots.append(shp(rr[i]) - shp(rf[i]))
        boots = np.array(boots)
        lo, hi = np.percentile(boots, [2.5, 97.5])
        verdict = "significant" if lo > 0 else "NOT significant"
        print(f"  {name:<22} {point:>9.3f} {f'[{lo:>6.2f}, {hi:>6.2f}]':>20} "
              f"{float((boots <= 0).mean()):>8.3f}  {verdict}")

    # ---- One-bar shift (look-ahead check) on the best survivor ----
    best = max(stored.items(), key=lambda kv: stats(kv[1][1])["sharpe"])[0]
    print(f"\n{'=' * 96}")
    print(f"# ONE-BAR SHIFT TEST — best survivor '{best}' (10bps)")
    print(f"{'=' * 96}")
    expo = stored[best][0]
    for extra in range(3):
        e = expo.shift(extra).fillna(0.5) if extra else expo
        print(f"  extra lag {extra}: {fmt(stats(run(ew, e, 10.0)))}")

    # ---- Per-asset replication for the best survivor ----
    print(f"\n{'=' * 96}")
    print(f"# PER-ASSET (signal applied to each pair individually, 10bps)")
    print(f"{'=' * 96}")
    print(f"\n  {'pair':<12} {'BH Sharpe':>10} {'sig Sharpe':>11} {'better?':>9}")
    wins = 0
    for p in close.columns:
        r = rets[p].fillna(0.0)
        cl = close[[p]]
        vo = volume[[p]]
        fn = {
            "volume trend 10/30": sig_volume_trend,
            "volume spike 2x": sig_volume_spike,
            "volume breakout": sig_volume_breakout,
            "OBV trend 30": sig_obv,
            "VWMA 50": sig_vwma,
        }[best]
        e = fn(cl, vo).reindex(r.index).fillna(0.5)
        b = stats(run(r, pd.Series(1.0, index=r.index), 0.0))
        d = stats(run(r, e, 10.0))
        better = d["sharpe"] > b["sharpe"]
        wins += better
        print(f"  {p:<12} {b['sharpe']:>10.2f} {d['sharpe']:>11.2f} "
              f"{'YES' if better else 'no':>9}")
    print(f"\n  {best} beat buy & hold on Sharpe in {wins}/{len(close.columns)} pairs")


if __name__ == "__main__":
    main()
