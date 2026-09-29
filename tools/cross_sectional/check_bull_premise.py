"""
Check the premise before acting on it.

The suggestion was: BTC has been in a bull market, so if E#6 is right it should
be profiting. Two things have to be established before that becomes evidence,
and only one of them has been:

  1. Was the window E#6 actually traded in a bull market?  (not yet checked)
  2. Did E#6 profit there?  (already known: 2026 was NEGATIVE)

If both hold, the failure is worse than a plain null: the strategy lost money
in the most favourable environment a long-momentum strategy can be given. If the
first does not hold, the premise does not apply to this sample and the negative
means less than it appears.

Run:  .venv\\Scripts\\python.exe tools\\cross_sectional\\check_bull_premise.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

pd.set_option("display.width", 220)

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "user_data/universe/raw_daily"
REBASE = -0.90


def load():
    frames = {}
    for f in sorted(RAW.glob("*_1d.csv.gz")):
        sym = f.name.replace("_1d.csv.gz", "")
        d = pd.read_csv(f)
        d["date"] = pd.to_datetime(d["date"], format="%Y-%m-%d", errors="coerce")
        d = d.dropna(subset=["date", "close", "quote_volume"]).set_index("date").sort_index()
        d = d[~d.index.duplicated()]
        d = d[d["quote_volume"] > 0]
        if (d["close"].pct_change() < REBASE).any():
            continue
        frames[sym] = d
    px = pd.concat({k: v["close"] for k, v in frames.items()}, axis=1).sort_index()
    qv = pd.concat({k: v["quote_volume"] for k, v in frames.items()}, axis=1).sort_index()
    return px, qv


def main() -> None:
    px, qv = load()
    med = qv.median()
    uni = list(med.nlargest(50).index)
    px = px[uni]

    print("=" * 82)
    print("1. WAS THE WINDOW ACTUALLY A BULL MARKET?  (BTC, the E#6 universe window)")
    print("=" * 82)
    btc = px["BTCUSDT"].dropna()
    print(f"  data ends {btc.index[-1].date()}")
    by_year = btc.resample("YE").last()
    first = btc.resample("YE").first()
    rows = []
    for y in by_year.index:
        rows.append({
            "year": y.year,
            "btc_first": float(first.loc[y]),
            "btc_last": float(by_year.loc[y]),
            "btc_return_pct": float((by_year.loc[y] / first.loc[y] - 1) * 100),
            "weeks_with_data": int(btc.loc[str(y.year)].resample("W-FRI").last().notna().sum()),
        })
    t = pd.DataFrame(rows)
    print(t.to_string(index=False, float_format=lambda v: f"{v:,.2f}"))
    eq = btc.resample("YE").last()
    print(f"\n  full-window BTC return {float((eq.iloc[-1]/btc.iloc[0]-1)*100):+.1f}% over "
          f"{(btc.index[-1]-btc.index[0]).days/365.25:.2f} years")

    print()
    print("=" * 82)
    print("2. THE CROSS-SECTION, EQUAL WEIGHTED -- did the OPPORTUNITY exist?")
    print("=" * 82)
    ew = px.mean(axis=1)
    ewy = ew.resample("YE").last()
    efy = ew.resample("YE").first()
    rows2 = [{"year": y.year,
              "equal_weight_return_pct": float((ewy.loc[y] / efy.loc[y] - 1) * 100)}
             for y in ewy.index]
    t2 = pd.DataFrame(rows2)
    print(t2.to_string(index=False, float_format=lambda v: f"{v:+.2f}"))

    print()
    print("=" * 82)
    print("3. THE PERIOD E#6 REPORTED AS NEGATIVE")
    print("=" * 82)
    w26 = btc.loc["2026"]
    uni26 = px.loc["2026"].mean(axis=1).dropna()
    print(f"  2026 window: {w26.index[0].date()} -> {w26.index[-1].date()}")
    print(f"  BTC          {float((w26.iloc[-1]/w26.iloc[0]-1)*100):+.1f}%")
    print(f"  equal-weight {float((uni26.iloc[-1]/uni26.iloc[0]-1)*100):+.1f}%")
    disc = px.pct_change()
    mom = disc.rolling(24 * 7).sum()
    print()
    print("  dispersion: BTC daily vol   "
          f"{float(btc.pct_change().loc['2026'].std()*100):.2f}%")
    print(f"              cross-sec daily {float(disc.loc['2026'].std(axis=1).mean()*100):.2f}%")
    print("""
  A long-momentum book is short the weak names as well as long the strong
  ones, so what matters is the CROSS-SECTION, not the index. If the index rose
  while dispersion was low and the leaders rotated rather than persisted, the
  strategy can lose in a rising market -- that is a genuine property of
  long-short cross-sectional strategies and not a defect in the test.""")


if __name__ == "__main__":
    main()
