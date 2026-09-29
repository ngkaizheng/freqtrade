"""MA200 exposure study — implements the handoff's core methodology.

    Close > MA200  ->  100% exposure
    Close < MA200  ->   50% exposure

Deliberately NOT a Freqtrade backtest: we need a buy-and-hold benchmark and a
randomization placebo, neither of which Freqtrade's trade-level accounting
gives us for a "resize, never close" rule.

Critical methodology from quant-research-handoff:
  1. ONE lag point. Decide on close[t], hold that exposure from t+1.
     (handoff pitfall #1: same-bar execution turned a null Sharpe of -0.74
      into +14.79 on synthetic data.)
  2. min_periods explicit; NaN must not manufacture a phantom signal.
  3. Compare against buy-and-hold, never against nothing.
  4. Permutation/placebo test: a circular shift of the exposure series keeps
     its frequency AND its run structure, controlling for the purely MECHANICAL
     effect that holding less risk lowers drawdown.
"""

import glob
import os

import numpy as np
import pandas as pd

DATA_DIR = "user_data/data/binance"
MA_WINDOW = 200
EXPOSURE_RISK_ON = 1.00
EXPOSURE_RISK_OFF = 0.50
TRADING_DAYS = 365  # crypto trades every day


def load(pair: str, timeframe: str = "1d") -> pd.DataFrame:
    path = os.path.join(DATA_DIR, f"{pair.replace('/', '_')}-{timeframe}.feather")
    df = pd.read_feather(path)
    df = df.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    return df


def max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    return float((equity / peak - 1.0).min())


def cagr(equity: pd.Series, periods_per_year: int) -> float:
    years = len(equity) / periods_per_year
    if years <= 0 or equity.iloc[0] <= 0:
        return float("nan")
    return float((equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1)


def sharpe(returns: pd.Series, periods_per_year: int) -> float:
    sd = returns.std()
    if sd == 0 or np.isnan(sd):
        return float("nan")
    return float(returns.mean() / sd * np.sqrt(periods_per_year))


def simulate(
    exposure: pd.Series,
    returns: pd.Series,
    cost_bps: float,
    initial: float = 10_000.0,
) -> pd.Series:
    """Equity curve for a given target-exposure series.

    exposure[t] is decided at close[t]; it is realised one bar later, so the
    only lag point in this file is the shift(1) below.
    """
    pos = exposure.shift(1).fillna(0.0)
    turnover = pos.diff().abs().fillna(pos.abs())
    net = pos * returns - turnover * (cost_bps / 10_000.0)
    return initial * (1.0 + net).cumprod()


def metrics(equity: pd.Series, periods_per_year: int) -> dict:
    rets = equity.pct_change().dropna()
    return {
        "final": float(equity.iloc[-1]),
        "cagr": cagr(equity, periods_per_year),
        "maxdd": max_drawdown(equity),
        "sharpe": sharpe(rets, periods_per_year),
    }


def fmt(m: dict) -> str:
    return (
        f"${m['final']:>10,.0f}  CAGR {m['cagr']:>7.2%}  "
        f"MaxDD {m['maxdd']:>7.2%}  Sharpe {m['sharpe']:>5.2f}"
    )


def run_pair(pair: str) -> dict:
    df = load(pair)
    close = df["close"].astype(float)
    returns = close.pct_change(fill_method=None).fillna(0.0)
    returns = returns.replace([np.inf, -np.inf], np.nan).fillna(0.0)

    # Explicit validity mask: no phantom cross on the first valid MA200 bar.
    ma = close.rolling(MA_WINDOW, min_periods=MA_WINDOW).mean()
    valid = ma.notna() & close.notna()

    exposure = pd.Series(np.nan, index=df.index, dtype=float)
    exposure[valid] = np.where(
        close[valid] > ma[valid], EXPOSURE_RISK_ON, EXPOSURE_RISK_OFF
    )
    exposure = exposure.bfill().fillna(EXPOSURE_RISK_OFF)

    # Evaluate from the first bar where the MA is valid, so warm-up does not
    # inflate the statistics (handoff pitfall 6.4c).
    start = int(valid.idxmax())
    exposure = exposure.iloc[start:]
    returns_eval = returns.iloc[start:]
    close_eval = close.iloc[start:]

    print(f"\n{'=' * 78}")
    print(f"{pair}   bars={len(returns_eval)}   "
          f"{df['date'].iloc[start].date()} -> {df['date'].iloc[-1].date()}")
    print(f"{'=' * 78}")

    bh = 10_000.0 * (1.0 + returns_eval).cumprod()
    bh_m = metrics(bh, TRADING_DAYS)
    print(f"  {'buy & hold':<28} {fmt(bh_m)}")

    results = {}
    for cost in (0.0, 10.0, 20.0):
        eq = simulate(exposure, returns_eval, cost)
        m = metrics(eq, TRADING_DAYS)
        results[cost] = m
        label = f"MA200 rule ({cost:.0f}bps)"
        print(f"  {label:<28} {fmt(m)}")

    avg_exposure = float(exposure.mean())
    print(f"\n  average exposure: {avg_exposure:.1%}  "
          f"(time above MA200: {float((exposure == EXPOSURE_RISK_ON).mean()):.1%})")

    return {
        "pair": pair,
        "buy_hold": bh_m,
        "rule": results,
        "avg_exposure": avg_exposure,
        "exposure": exposure,
        "returns": returns_eval,
    }


def placebo(res: dict, n_perm: int = 200, cost_bps: float = 10.0, seed: int = 42) -> dict:
    """Circular-shift placebo.

    Shifting the exposure series preserves its exact frequency and run-length
    structure while destroying its alignment with returns. This is the control
    the handoff demands: it isolates "the signal knows when to de-risk" from
    "holding less risk mechanically lowers drawdown".
    """
    rng = np.random.default_rng(seed)
    exposure = res["exposure"]
    returns = res["returns"]
    n = len(exposure)
    n_valid = int((exposure == EXPOSURE_RISK_ON).sum())

    real = metrics(simulate(exposure, returns, cost_bps), TRADING_DAYS)

    dds, cagrs = [], []
    for _ in range(n_perm):
        shift = int(rng.integers(1, n))
        sh = pd.Series(np.roll(exposure.to_numpy(), shift), index=exposure.index)
        m = metrics(simulate(sh, returns, cost_bps), TRADING_DAYS)
        dds.append(m["maxdd"])
        cagrs.append(m["cagr"])

    dds = np.array(dds)
    cagrs = np.array(cagrs)
    # Fraction of placebos that are BETTER than the real rule. LOW = the real
    # signal is doing something the random shifts cannot.
    dd_better = float((dds > real["maxdd"]).mean())
    cagr_better = float((cagrs > real["cagr"]).mean())

    return {
        "real": real,
        "dd_better": dd_better,
        "cagr_better": cagr_better,
        "placebo_dd_mean": float(dds.mean()),
        "placebo_cagr_mean": float(cagrs.mean()),
        "n_perm": n_perm,
    }


def main() -> None:
    pairs = ["BTC/USDT", "ETH/USDT", "XRP/USDT"]
    results = [run_pair(p) for p in pairs]

    print(f"\n\n{'#' * 78}")
    print("# PLACEBO TEST (circular shift, 200 permutations, 10bps)")
    print("#   Does the signal beat RANDOM exposure changes of the same shape?")
    print(f"{'#' * 78}")
    for res in results:
        pl = placebo(res)
        print(f"\n{res['pair']}")
        print(f"  real            : DD {pl['real']['maxdd']:>7.2%}  "
              f"CAGR {pl['real']['cagr']:>6.2%}")
        print(f"  placebo mean    : DD {pl['placebo_dd_mean']:>7.2%}  "
              f"CAGR {pl['placebo_cagr_mean']:>6.2%}")
        print(f"  placebos beating real on DD  : {pl['dd_better']:>5.1%} "
              f"(low = signal adds value)")
        print(f"  placebos beating real on CAGR: {pl['cagr_better']:>5.1%}")
        dd_ok = pl["dd_better"] < 0.05
        print(f"  -> DD {'EXCEEDS placebo (p<0.05)' if dd_ok else 'INDISTINGUISHABLE from placebo'}")

    # Cross-asset summary
    print(f"\n\n{'#' * 78}")
    print("# CROSS-ASSET SUMMARY (10bps)")
    print(f"{'#' * 78}")
    print(f"  {'pair':<10} {'BH CAGR':>9} {'rule CAGR':>10} {'BH MaxDD':>10} "
          f"{'rule MaxDD':>11} {'DD better?':>11}")
    dd_wins = 0
    for res in results:
        bh = res["buy_hold"]
        r = res["rule"][10.0]
        better = r["maxdd"] > bh["maxdd"]
        dd_wins += better
        print(f"  {res['pair']:<10} {bh['cagr']:>9.2%} {r['cagr']:>10.2%} "
              f"{bh['maxdd']:>10.2%} {r['maxdd']:>11.2%} "
              f"{'YES' if better else 'no':>11}")
    print(f"\n  Drawdown improved in {dd_wins}/{len(results)} assets "
          f"(handoff found 7/8 on equity ETFs)")


if __name__ == "__main__":
    main()
