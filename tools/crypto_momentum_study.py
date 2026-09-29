"""Cross-sectional momentum on crypto — with the handoff's equal-weight benchmark.

Why this design
---------------
quant-research-handoff/DECISIONS.md 阶段 0 records the single most important
lesson of that project:

    run_vs_equalweight.py -> 换成等权同池基准后，8 个策略中 0 个显著跑赢
    "与 SPY 比较是假的测试（池子偏差）→ 必须用等权同池"

Comparing a hand-picked basket against one index is not a test — the basket was
chosen with hindsight. So every momentum variant here is measured against an
equal-weight portfolio of the SAME pool over the SAME window, and against
random-K placebo selections.

Methodology carried over from the handoff checklist:
  * ONE lag point. Rank on data through t, hold from t+1 (shift(1)).
  * Point-in-time universe: a pair only enters once its data actually starts,
    so we never rank a coin that had not listed yet.
  * Costs charged on the traded delta, both legs.
  * Placebo: random K-of-N selection, to test whether ranking adds anything.
"""

import glob
import os

import numpy as np
import pandas as pd

DATA_DIR = "user_data/data/binance"
PERIODS_PER_YEAR = 365


def load_panel() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (close, volume) panels indexed by date, columns by pair."""
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*-1d.feather")))
    closes, volumes = {}, {}
    for path in files:
        pair = os.path.basename(path).replace("-1d.feather", "").replace("_", "/")
        df = pd.read_feather(path)
        df = df.sort_values("date").drop_duplicates("date")
        s = df.set_index("date")["close"].astype(float)
        v = df.set_index("date")["volume"].astype(float)
        closes[pair] = s
        volumes[pair] = v
    close = pd.DataFrame(closes).sort_index()
    volume = pd.DataFrame(volumes).sort_index()
    return close, volume


def max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    return float((equity / peak - 1.0).min())


def cagr(equity: pd.Series) -> float:
    years = len(equity) / PERIODS_PER_YEAR
    if years <= 0 or equity.iloc[0] <= 0:
        return float("nan")
    return float((equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1)


def sharpe(returns: pd.Series) -> float:
    sd = returns.std()
    if sd == 0 or np.isnan(sd):
        return float("nan")
    return float(returns.mean() / sd * np.sqrt(PERIODS_PER_YEAR))


def stats(equity: pd.Series) -> dict:
    r = equity.pct_change().dropna()
    return {
        "final": float(equity.iloc[-1]),
        "cagr": cagr(equity),
        "maxdd": max_drawdown(equity),
        "sharpe": sharpe(r),
    }


def fmt(m: dict) -> str:
    return (f"${m['final']:>11,.0f}  CAGR {m['cagr']:>7.2%}  "
            f"MaxDD {m['maxdd']:>7.2%}  Sharpe {m['sharpe']:>5.2f}")


def build_weights(
    close: pd.DataFrame,
    lookback: int,
    top_k: int,
    rebalance: int,
    mode: str,
    seed: int = 0,
) -> pd.DataFrame:
    """Daily target weights (long only, equal weight within selection).

    mode: 'momentum' rank by trailing return, 'equal' hold whole universe,
          'random' pick K at random each rebalance (placebo).
    """
    returns = close.pct_change(fill_method=None)
    mom = close / close.shift(lookback) - 1.0

    valid = close.notna()
    # Point-in-time universe: need the full lookback of real data.
    eligible = valid & (valid.rolling(lookback).sum() == lookback)

    rng = np.random.default_rng(seed)
    weights = pd.DataFrame(np.nan, index=close.index, columns=close.columns)

    for i in range(len(close)):
        if i % rebalance != 0:
            continue
        row_ok = eligible.iloc[i]
        pool = list(row_ok.index[row_ok])
        if not pool:
            continue

        if mode == "equal":
            chosen = pool
        elif mode == "random":
            k = min(top_k, len(pool))
            chosen = list(rng.choice(pool, size=k, replace=False))
        else:  # momentum
            scores = mom.iloc[i][pool].dropna()
            if scores.empty:
                continue
            k = min(top_k, len(scores))
            chosen = list(scores.nlargest(k).index)

        if not chosen:
            continue
        w = pd.Series(0.0, index=close.columns)
        w[chosen] = 1.0 / len(chosen)
        # Hold this target until the next rebalance.
        end = min(i + rebalance, len(close))
        weights.iloc[i:end] = w.to_numpy()

    return weights


def simulate(weights: pd.DataFrame, close: pd.DataFrame, cost_bps: float,
             initial: float = 10_000.0) -> pd.Series:
    """Equity curve. weights[t] is decided on close[t] and realised at t+1."""
    returns = close.pct_change(fill_method=None)
    returns = returns.replace([np.inf, -np.inf], np.nan)

    w = weights.shift(1)
    # Drift-free approximation: rebalance to target each bar's return.
    port_ret = (w * returns).sum(axis=1, min_count=1).fillna(0.0)

    turnover = (weights - weights.shift(1)).abs().sum(axis=1).fillna(0.0)
    cost = turnover.shift(1).fillna(0.0) * (cost_bps / 10_000.0)

    net = port_ret - cost
    return initial * (1.0 + net).cumprod()


def evaluate(close: pd.DataFrame, start: str = "2019-01-01") -> None:
    close = close.loc[start:]
    n_pairs = close.shape[1]
    print(f"universe: {n_pairs} pairs   window: {close.index[0].date()} -> "
          f"{close.index[-1].date()}  ({len(close)/PERIODS_PER_YEAR:.1f} years)")

    configs = [
        ("equal-weight (all)", "equal", 30, 999),
        ("momentum 30d top5", "momentum", 30, 5),
        ("momentum 90d top5", "momentum", 90, 5),
        ("momentum 180d top5", "momentum", 180, 5),
        ("momentum 90d top10", "momentum", 90, 10),
    ]

    print(f"\n{'=' * 92}")
    print(f"{'variant':<24} {'10bps portfolio metrics':<44} {'turnover/yr':>11}")
    print(f"{'=' * 92}")

    results = {}
    for label, mode, lookback, k in configs:
        w = build_weights(close, lookback, k, rebalance=7, mode=mode)
        eq = simulate(w, close, 10.0)
        results[label] = (w, eq)
        to = (w - w.shift(1)).abs().sum(axis=1).fillna(0).sum() / (len(close) / 365)
        print(f"  {label:<22} {fmt(stats(eq))}  {to:>9.1f}x")

    # Cost sensitivity on the headline variants
    print(f"\n{'=' * 92}")
    print("# COST SENSITIVITY")
    print(f"{'=' * 92}")
    for label in ("equal-weight (all)", "momentum 30d top5", "momentum 90d top5"):
        w, _ = results[label]
        print(f"\n  {label}")
        for cost in (0.0, 10.0, 20.0, 50.0):
            print(f"    {cost:>4.0f}bps  {fmt(stats(simulate(w, close, cost)))}")

    # Placebo for EVERY variant: with 5 configs tested, one p<0.05 is expected
    # by chance. Bonferroni threshold is 0.05/5 = 0.01.
    print(f"\n{'=' * 92}")
    print("# PLACEBO — every variant vs RANDOM K (200 draws, 10bps)")
    print("#   Multiple testing: 5 variants tested -> Bonferroni p < 0.01")
    print(f"{'=' * 92}")
    print(f"\n  {'variant':<22} {'real CAGR':>10} {'rand p95':>10} "
          f"{'p-value':>9}  {'verdict':<28}")
    for label, mode, lookback, k in configs:
        if mode == "equal":
            continue
        real = stats(simulate(results[label][0], close, 10.0))
        rand = []
        for seed in range(200):
            w = build_weights(close, lookback, k, rebalance=7, mode="random", seed=seed)
            rand.append(stats(simulate(w, close, 10.0))["cagr"])
        rand = np.array(rand)
        p = float((rand >= real["cagr"]).mean())
        if p < 0.01:
            verdict = "PASSES (p<0.01)"
        elif p < 0.05:
            verdict = "fails Bonferroni"
        else:
            verdict = "indistinguishable"
        print(f"  {label:<22} {real['cagr']:>10.2%} "
              f"{np.percentile(rand, 95):>10.2%} {p:>9.3f}  {verdict:<28}")

    # The 47 pairs are those LISTED TODAY on Binance. Coins that delisted or
    # went to zero are absent entirely -> this is survivorship bias, and in
    # crypto it is severe (LUNA, FTT, ... are simply not in the panel).
    print(f"\n{'=' * 92}")
    print("# UNIVERSAL CAVEAT — survivorship bias")
    print(f"{'=' * 92}")
    print("  The universe is pairs listed on Binance TODAY. Everything that")
    print("  delisted or went to zero (LUNA, FTT, ...) is silently absent.")
    print("  Momentum selects recent winners, so it is exactly the rule most")
    print("  exposed to this bias. Treat every CAGR above as an upper bound.")

    robustness(close, configs)


def robustness(close: pd.DataFrame, configs: list) -> None:
    """Plateau, sub-period stability, and the one-bar shift test."""

    # --- 1. Parameter plateau ---
    # The handoff's 7.3: a real edge sits on a plateau, an overfit one is a spike.
    print(f"\n{'=' * 92}")
    print("# PARAMETER PLATEAU (CAGR @10bps, rebalance=7)")
    print("#   A real effect is surrounded by similarly good values, not a spike.")
    print(f"{'=' * 92}")
    lookbacks = [14, 21, 30, 45, 60, 90]
    topks = [3, 5, 8, 10]
    print(f"\n  {'lookback':<10}" + "".join(f"{'top' + str(k):>12}" for k in topks))
    for lb in lookbacks:
        row = f"  {lb:<10}"
        for k in topks:
            w = build_weights(close, lb, k, rebalance=7, mode="momentum")
            m = stats(simulate(w, close, 10.0))
            row += f"{m['cagr']:>11.1%} "
        print(row)

    # --- 2. Sub-period stability ---
    print(f"\n{'=' * 92}")
    print("# SUB-PERIOD STABILITY (momentum 30d top5 vs equal-weight, CAGR @10bps)")
    print("#   A single full-sample number hides regimes where the rule failed.")
    print(f"{'=' * 92}")
    w_mom = build_weights(close, 30, 5, rebalance=7, mode="momentum")
    w_eq = build_weights(close, 30, 30, rebalance=7, mode="equal")
    eq_mom = simulate(w_mom, close, 10.0)
    eq_eq = simulate(w_eq, close, 10.0)
    print(f"\n  {'period':<12} {'equal-weight':>14} {'momentum':>14} {'momentum wins?':>16}")
    wins = 0
    total = 0
    for year in range(2019, 2027):
        mask = (eq_mom.index.year == year)
        if mask.sum() < 30:
            continue
        a = eq_eq[mask]
        b = eq_mom[mask]
        ra = a.iloc[-1] / a.iloc[0] - 1
        rb = b.iloc[-1] / b.iloc[0] - 1
        total += 1
        wins += rb > ra
        print(f"  {year:<12} {ra:>14.1%} {rb:>14.1%} "
              f"{'YES' if rb > ra else 'no':>16}")
    print(f"\n  momentum beat equal-weight in {wins}/{total} years")

    # --- 3. One-bar shift test (handoff's single most valuable diagnostic) ---
    # If performance collapses when signals are delayed one extra bar, the
    # original result was trading on information it could not have had.
    print(f"\n{'=' * 92}")
    print("# ONE-BAR SHIFT TEST (momentum 30d top5, 10bps)")
    print("#   Deliberately delay the signal by an extra bar. A real edge degrades")
    print("#   gracefully; a look-ahead artifact collapses.")
    print(f"{'=' * 92}")
    returns = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    for extra in (0, 1, 2):
        w = w_mom.shift(extra) if extra else w_mom
        port = (w.shift(1) * returns).sum(axis=1, min_count=1).fillna(0.0)
        turn = (w - w.shift(1)).abs().sum(axis=1).fillna(0.0)
        net = port - turn.shift(1).fillna(0.0) * 0.001
        eq = 10_000 * (1 + net).cumprod()
        m = stats(eq)
        print(f"  extra lag {extra}: {fmt(m)}")


def main() -> None:
    close, volume = load_panel()
    print(f"loaded {close.shape[1]} pairs, {close.shape[0]} daily rows\n")
    evaluate(close)


if __name__ == "__main__":
    main()
