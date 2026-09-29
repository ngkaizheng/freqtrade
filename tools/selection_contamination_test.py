"""Resolving the tension from H-E.

hE_parameter_free.py produced a surprising comparison on BTC:
    ensemble OOS mean edge : +0.027
    SMA-50   OOS mean edge : +0.160   <- HIGHER

If SMA-50 genuinely transfers better out-of-sample, then the whole "window
cannot be chosen" thesis (round 7) is wrong, and my H-E rationale collapses.

BUT there is a competing explanation that must be tested before accepting that:
SMA-50 was selected by looking at the FULL sample (lesson L5). Its OOS numbers
are therefore contaminated, and the ensemble -- which has NO selection -- is the
honest estimate. Under this explanation the ensemble is *supposed* to look worse;
that is the cost of not cheating.

The discriminating test: rank all 8 windows by OUT-OF-SAMPLE edge on each split.

  * If SMA-50 ranks near the top OOS consistently, its advantage is real and
    selection "worked" -> my thesis is wrong.
  * If SMA-50's OOS rank is middling and unstable, its +0.160 mean is an
    artifact of being one of 8 correlated draws, with the winner chosen by
    hindsight -> thesis holds.

This is DIAGNOSTIC: no rule is selected, nothing is tuned.
"""

import os
import numpy as np
import pandas as pd

PPY = 365
COST = 10.0
W = [10, 20, 30, 50, 75, 100, 150, 200]
RISK_ON, RISK_OFF = 1.00, 0.50

MAJORS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "AVAX", "DOT", "LINK",
          "LTC", "BCH", "ATOM", "UNI", "AAVE", "XLM", "ETC", "ALGO", "FIL",
          "NEO", "TRX"]


def sharpe(r, ppy=PPY):
    sd = r.std()
    return float(r.mean() / sd * np.sqrt(ppy)) if sd and sd > 0 else np.nan


def expo_single(close, w):
    ma = close.rolling(w, min_periods=w).mean()
    v = ma.notna()
    out = pd.Series(RISK_OFF, index=close.index)
    out[v] = np.where(close[v] > ma[v], RISK_ON, RISK_OFF)
    return out


def nets(rets, expo, cost=COST):
    pos = expo.shift(1).fillna(0.0)
    turn = pos.diff().abs().fillna(pos.abs())
    return pos * rets - turn * cost / 10_000.0


def edge_vs_flat(rets, expo):
    r = nets(rets, expo)
    f = pd.Series(float(expo.mean()), index=rets.index) * rets
    return sharpe(r) - sharpe(f)


def main():
    d = pd.read_feather("user_data/data/bitstamp/BTC_USD-1d.feather")
    d = d.sort_values("date").drop_duplicates("date")
    btc = d.set_index("date")["close"].astype(float).iloc[200:]
    r_btc = btc.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)

    closes = {}
    for m in MAJORS:
        p = f"user_data/data/binance/{m}_USDT-1d.feather"
        if not os.path.exists(p):
            continue
        dd = pd.read_feather(p).sort_values("date").drop_duplicates("date")
        closes[f"{m}/USDT"] = dd.set_index("date")["close"].astype(float)
    panel = pd.DataFrame(closes).sort_index().loc["2019-01-01":]
    prets = panel.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    ew = prets.mean(axis=1, skipna=True).fillna(0.0)
    idx = panel.ffill().mean(axis=1)

    print("=" * 96)
    print("# IS SMA-50's OOS ADVANTAGE REAL, OR SELECTION CONTAMINATION?")
    print("=" * 96)
    print("\n  Diagnostic: rank all 8 windows by OUT-OF-SAMPLE edge per split.")

    for name, close, rets, splits, tlen in (
        ("BTC/USD", btc, r_btc,
         ["2020-01-01", "2021-01-01", "2022-01-01", "2023-01-01", "2024-01-01",
          "2025-01-01"], 550),
        ("20-major pool", idx, ew,
         ["2021-06-01", "2022-01-01", "2022-07-01", "2023-01-01", "2023-07-01",
          "2024-01-01"], 400),
    ):
        print(f"\n{'=' * 96}")
        print(f"# {name}")
        print(f"{'=' * 96}")
        ranks = []
        for s in splits:
            c = pd.Timestamp(s, tz=close.index.tz)
            te = (close.index >= c) & (close.index < c + pd.Timedelta(days=tlen))
            if te.sum() < 100:
                continue
            edges = {w: edge_vs_flat(rets[te], expo_single(close, w)[te]) for w in W}
            order = sorted(edges, key=lambda w: -edges[w])
            rank50 = order.index(50) + 1
            ranks.append(rank50)
            top = order[0]
            print(f"  split {s}: SMA-50 rank {rank50}/8 "
                  f"(edge {edges[50]:+.3f}); best was SMA-{top} "
                  f"({edges[top]:+.3f})")
        ranks = np.array(ranks)
        print(f"\n  SMA-50 OOS rank: mean {ranks.mean():.1f}/8, "
              f"range {ranks.min()}-{ranks.max()}")
        print(f"  SMA-50 was best OOS in {int((ranks==1).sum())}/{len(ranks)} splits")
        print(f"  -> {'SMA-50 ranks consistently high => selection may have worked' if ranks.mean() <= 2.5 else 'SMA-50 OOS rank is middling/unstable => its mean edge is not a stable property'}")

    # ---- The contamination argument, made explicit ----
    print(f"\n{'=' * 96}")
    print("# CONTAMINATION ARGUMENT")
    print(f"{'=' * 96}")
    print("""
  SMA-50 was selected by looking at the FULL sample (rounds 1-2, lesson L5).
  Its out-of-sample numbers are therefore NOT clean out-of-sample numbers, even
  when computed on a held-out period: the choice of 50 already encodes knowledge
  of the whole series, including that held-out period.

  The ensemble has no such encoding -- it uses all 8 windows equally, so nothing
  about the sample influenced it. Its OOS figure is therefore the honest one.

  Consequence: the ensemble looking worse than SMA-50 is EXPECTED, not
  disqualifying. The comparison "ensemble +0.027 vs SMA-50 +0.160" is not
  evidence that SMA-50 is better; it is evidence that selection buys an
  in-sample-flattered number.

  The rank test above is the check on that reasoning. If SMA-50's OOS rank were
  consistently top, the contamination story would be insufficient and I would
  have to revise. Whatever it shows is what gets recorded.""")


if __name__ == "__main__":
    main()
