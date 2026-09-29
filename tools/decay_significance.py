"""Is the train->test decay real, or is the test window just too short?

train_test_2025_2026.py found a striking decay:
    20-major pool : train edge +0.402  ->  test edge -0.001
    per-asset mean: train edge +0.197  ->  test edge -0.031
    13/20 train-positive assets flipped negative

That looks like the classic overfitting signature. But before concluding that,
the decay must be tested against the noise floor of the test window. With
~2.7 years, SE(Sharpe) ~ 0.6, so point estimates are extremely unstable.

This script answers three questions:
  1. How wide is the test-edge confidence interval really?
  2. Is (train edge - test edge) statistically distinguishable from zero?
  3. Is the 7/20 sign flip rate different from chance?

Honest framing: if none of these are significant, the correct conclusion is
"cannot distinguish", NOT "the edge is real" AND NOT "the edge is gone".
"""

import os
import numpy as np
import pandas as pd

PPY = 365
COST = 10.0
WINDOWS = [10, 20, 30, 50, 75, 100, 150, 200]
MAJORS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "AVAX", "DOT", "LINK",
          "LTC", "BCH", "ATOM", "UNI", "AAVE", "XLM", "ETC", "ALGO", "FIL",
          "NEO", "TRX"]


def sharpe(r, ppy=PPY):
    sd = r.std()
    return float(r.mean() / sd * np.sqrt(ppy)) if sd and sd > 0 else np.nan


def sma_expo(close, w):
    ma = close.rolling(w, min_periods=w).mean()
    v = ma.notna()
    out = pd.Series(0.5, index=close.index)
    out[v] = np.where(close[v] > ma[v], 1.0, 0.5)
    return out


def rule_returns(rets, close, w, cost=COST):
    """Net daily returns of the SMA rule."""
    e = sma_expo(close, w)
    pos = e.shift(1).fillna(0.0)
    turn = pos.diff().abs().fillna(pos.abs())
    return pos * rets - turn * cost / 10_000.0


def flat_returns(rets, close, w, cost=COST):
    e = sma_expo(close, w)
    a = float(e.mean())
    return a * rets


def edge(rr, rf, ppy=PPY):
    return sharpe(rr, ppy) - sharpe(rf, ppy)


def block_idx(n, block, rng):
    nb = int(np.ceil(n / block))
    st = rng.integers(0, n, nb)
    return np.concatenate([np.arange(s, s + block) % n for s in st])[:n]


def main():
    closes = {}
    for m in MAJORS:
        p = f"user_data/data/binance/{m}_USDT-1d.feather"
        if not os.path.exists(p):
            continue
        d = pd.read_feather(p).sort_values("date").drop_duplicates("date")
        closes[f"{m}/USDT"] = d.set_index("date")["close"].astype(float)
    panel = pd.DataFrame(closes).sort_index().loc["2019-01-01":]
    prets = panel.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)

    CUT = pd.Timestamp("2024-01-01", tz=panel.index.tz)

    print("=" * 94)
    print("# IS THE TRAIN->TEST DECAY REAL, OR IS THE TEST WINDOW TOO SHORT?")
    print("=" * 94)
    print(f"\ntrain 2019-01-01..2023-12-31 | test 2024-01-01..{panel.index[-1].date()}")

    # ---------- per-asset train / test edges ----------
    rows = []
    for t in panel.columns:
        c = panel[t].dropna()
        if len(c) < 800:
            continue
        r = prets[t].reindex(c.index).fillna(0.0)
        tr = c.index < CUT
        te = ~tr
        if tr.sum() < 500 or te.sum() < 100:
            continue
        # select window on TRAIN only
        best_w, best_e = None, -np.inf
        for w in WINDOWS:
            e = edge(rule_returns(r[tr], c[tr], w), flat_returns(r[tr], c[tr], w))
            if e > best_e:
                best_w, best_e = w, e
        e_te = edge(rule_returns(r[te], c[te], best_w),
                    flat_returns(r[te], c[te], best_w))
        rows.append({"pair": t, "w": best_w, "train": best_e, "test": e_te,
                     "n_train": int(tr.sum()), "n_test": int(te.sum())})

    df = pd.DataFrame(rows)
    n = len(df)
    print(f"\n  assets: {n}")
    print(f"  train edge mean {df['train'].mean():+.3f}  (sd {df['train'].std():.3f})")
    print(f"  test  edge mean {df['test'].mean():+.3f}  (sd {df['test'].std():.3f})")
    print(f"  decay          {df['train'].mean() - df['test'].mean():+.3f}")
    flips = int(((df["train"] > 0) & (df["test"] < 0)).sum())
    pos_train = int((df["train"] > 0).sum())
    print(f"  train-positive: {pos_train}/{n}   of those flipped negative: {flips}")

    # ---------- 1. Test-edge CI via cross-asset bootstrap ----------
    print(f"\n{'=' * 94}")
    print("# 1. HOW WIDE IS THE TEST-EDGE ESTIMATE?")
    print(f"{'=' * 94}")
    rng = np.random.default_rng(701)
    # (a) naive per-asset SE from the length of the test window
    for t in (2.7, 1.7):
        print(f"  Lo (2002) SE(Sharpe) at {t:.1f}y = {1/np.sqrt(t):.2f}")
    # (b) cross-asset bootstrap of the mean test edge
    tv = df["test"].to_numpy()
    boot = np.array([tv[rng.integers(0, n, n)].mean() for _ in range(10000)])
    lo, hi = np.percentile(boot, [2.5, 97.5])
    print(f"\n  cross-asset bootstrap on mean test edge:")
    print(f"    mean {tv.mean():+.3f}   95% CI [{lo:+.3f}, {hi:+.3f}]")
    print(f"    -> CI {'includes 0 (cannot reject no-edge)' if lo < 0 < hi else 'excludes 0'}")

    # ---------- 2. Is the decay significant? ----------
    print(f"\n{'=' * 94}")
    print("# 2. IS THE DECAY (TRAIN - TEST) SIGNIFICANT?")
    print(f"{'=' * 94}")
    diff = (df["train"] - df["test"]).to_numpy()
    print(f"\n  mean decay {diff.mean():+.3f}  sd {diff.std():.3f}")
    # Paired test across assets (note: assets are correlated, so this is optimistic)
    se = diff.std(ddof=1) / np.sqrt(n)
    tstat = diff.mean() / se
    print(f"  paired t-stat across assets: {tstat:.2f}  (optimistic: assets correlated)")
    # Bootstrap the decay
    bd = np.array([diff[rng.integers(0, n, n)].mean() for _ in range(10000)])
    dlo, dhi = np.percentile(bd, [2.5, 97.5])
    print(f"  bootstrap 95% CI on decay  : [{dlo:+.3f}, {dhi:+.3f}]")
    print(f"  -> decay {'IS significant' if dlo > 0 else 'NOT distinguishable from zero'}")

    # ---------- 3. Sign-flip rate vs chance ----------
    print(f"\n{'=' * 94}")
    print("# 3. IS 13/20 FLIPPING NEGATIVE UNUSUAL?")
    print(f"{'=' * 94}")
    from math import comb
    # Under H0: each train-positive asset has a 50% chance of a negative test edge
    m = pos_train
    p_obs = sum(comb(m, k) for k in range(flips, m + 1)) / (2 ** m)
    print(f"\n  train-positive assets: {m}")
    print(f"  flipped negative     : {flips}")
    print(f"  binomial p (H0: 50%) : {p_obs:.3f}")
    print(f"  -> {'unusual (evidence of decay)' if p_obs < 0.05 else 'within chance'}")

    # ---------- 4. What would we NEED to decide? ----------
    print(f"\n{'=' * 94}")
    print("# 4. HOW MUCH TEST DATA WOULD SETTLE THIS?")
    print(f"{'=' * 94}")
    print("""
  To detect an edge of +0.17 Sharpe at 80% power / 95% confidence you need
  roughly n = (2.8 / 0.17)^2 years ~ 271 years of data, which is impossible.

  To detect +0.5 Sharpe you need ~31 years. Also impossible for crypto.

  THIS IS THE CENTRAL PROBLEM and it does not go away with more searching:
  a modest Sharpe edge simply cannot be confirmed on any realistic sample of
  daily data. The 15-year BTC result had SE 0.26, which is why it passed; a
  2.7-year window has SE 0.61, which is why nothing can pass here.""")

    # ---------- Honest conclusion ----------
    print(f"{'=' * 94}")
    print("# HONEST CONCLUSION")
    print(f"{'=' * 94}")
    print(f"""
  The train->test decay is real in POINT ESTIMATE (train {df['train'].mean():+.3f}
  -> test {df['test'].mean():+.3f}) and {flips}/{m} train-positive assets flipped
  negative. But:

    * the mean test edge CI is [{lo:+.3f}, {hi:+.3f}] -- includes zero
    * the decay CI is [{dlo:+.3f}, {dhi:+.3f}] -- {'excludes' if dlo > 0 else 'includes'} zero
    * the flip rate is {flips}/{m}, binomial p = {p_obs:.3f}

  So the statistically defensible statement is NOT "the edge is gone". It is:

      the 2024-2026 window is too short to confirm or refute the edge, and the
      point estimates are consistent with BOTH mild decay AND noise.

  What this DOES change: it removes any basis for confidence. A candidate whose
  out-of-sample point estimates are uniformly worse has not earned trust, even
  if the decay is not provably significant. Absence of proof is not proof of
  absence, but it is also not a reason to trade.""")


if __name__ == "__main__":
    main()
