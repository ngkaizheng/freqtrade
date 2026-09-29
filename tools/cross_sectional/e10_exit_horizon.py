"""
E#10 -- the untested middle: a SIGNAL exit at 21-60 days.

E#9 tested a PRICE-based trailing stop and it carried no information: the
20-day return after a stop fires was indistinguishable from a random day.
E#7 tested a SIGNAL-based exit (flat when the trailing return goes negative) at
126 days and it was too slow to stop a drawdown -- 2022 loss ratio 0.96x.

Nobody in this project has tested the middle. That is where a usable exit
should live: long enough not to be a noise trigger, short enough to be in cash
before the drawdown bottoms.

The question is NOT "does some lookback win". It is:

    is there ANY lookback in {21, 42, 63} whose signal exit is followed by a
    reliably negative forward return, beating a same-frequency placebo?

If none does, the honest conclusion is that there is no exit rule in this
family, and "no stop is gambling" is a true statement rather than an
unanswered one.

Run:  .venv\\Scripts\\python.exe tools\\cross_sectional\\e10_exit_horizon.py
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

pd.set_option("display.width", 240)

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "user_data/universe/raw_daily"
OUT = Path(__file__).resolve().parent

TOP_N = 50
LOOKBACKS = (21, 42, 63, 126)      # 126 is E#7's registered lookback, for reference
FWD = 20
REBASE = -0.90
COST_RT = (3.6 + 10.0) / 1e4       # measured mean book + VIP0 taker


def load():
    closes, vols = {}, {}
    for f in sorted(RAW.glob("*_1d.csv.gz")):
        sym = f.name.replace("_1d.csv.gz", "")
        d = pd.read_csv(f)
        d["date"] = pd.to_datetime(d["date"], format="%Y-%m-%d", errors="coerce")
        d = d.dropna(subset=["date", "close", "quote_volume"]).set_index("date").sort_index()
        d = d[~d.index.duplicated()]
        d = d[d["quote_volume"] > 0]
        if (d["close"].pct_change() < REBASE).any():
            continue
        closes[sym] = d["close"]
        vols[sym] = d["quote_volume"]
    return (pd.concat(closes, axis=1).sort_index(),
            pd.concat(vols, axis=1).sort_index())


def main() -> None:
    px, qv = load()
    uni = list(qv.median().nlargest(TOP_N).index)
    eq = px[uni].mean(axis=1).ffill()
    r = eq.pct_change(fill_method=None).fillna(0.0)
    fwd = (eq.shift(-FWD) / eq - 1.0).dropna()
    print(f"basket: top {TOP_N} liquid names, {len(eq)} bars, "
          f"{eq.index[0].date()} -> {eq.index[-1].date()}")
    print(f"daily vol {r.std()*100:.2f}%\n")

    print("=" * 100)
    print("PART A -- when the SIGNAL says exit (trailing return negative), what follows?")
    print("=" * 100)
    print(f"{'lookback':>9} {'exits':>7} {'fwd 20d %':>11} {'t':>7} "
          f"{'placebo %':>11} {'t':>7} {'diff t':>8}   verdict")
    print("-" * 92)

    rng = np.random.default_rng(20260926)
    any_info = False
    for L in LOOKBACKS:
        sig = (eq / eq.shift(L) - 1.0)
        in_pos = True
        exits = []
        for i in range(1, len(eq)):
            if in_pos and sig.iloc[i] < 0:
                in_pos = False
                exits.append(eq.index[i])
            elif not in_pos and sig.iloc[i] > 0:
                in_pos = True
        if len(exits) < 15:
            print(f"{L:>9}d {len(exits):>7}   too few events")
            continue
        after = fwd.reindex(exits).dropna()
        pool = fwd.index[:-1]
        pl = fwd.reindex(rng.choice(pool, size=min(len(exits), len(pool)), replace=False)).dropna()
        t_a = after.mean() / after.std(ddof=1) * math.sqrt(len(after))
        t_p = pl.mean() / pl.std(ddof=1) * math.sqrt(len(pl))
        se = math.sqrt(after.var(ddof=1) / len(after) + pl.var(ddof=1) / len(pl))
        t_d = (after.mean() - pl.mean()) / se
        a1 = t_a <= -1.645
        a2 = t_d <= -1.645
        ok = a1 and a2
        any_info = any_info or ok
        print(f"{L:>9}d {len(exits):>7} {after.mean()*100:>11.2f} {t_a:>7.2f} "
              f"{pl.mean()*100:>11.2f} {t_p:>7.2f} {t_d:>8.2f}   "
              f"{'INFORMATION' if ok else ('noise' if a2 else 'no signal')}")

    print()
    print("=" * 100)
    print("PART B -- what the exit does to the actual portfolio")
    print("=" * 100)
    print(f"{'lookback':>9} {'CAGR%':>9} {'maxDD%':>9} {'Sharpe':>8} {'turnover/yr':>12}")
    print("-" * 60)
    for L in LOOKBACKS:
        sig = (eq / eq.shift(L) - 1.0)
        # The exposure for the move from t-1 to t must be decided at t-1. An
        # earlier version used `sig > 0` at t, which reads the close at t and
        # multiplies it by the return that had already accrued to that close --
        # one day of look-ahead, and it produced a CAGR of +199.8% at the 21-day
        # lookback. The decision is shifted by one bar.
        expo = (sig > 0).astype(float).shift(1).ffill().fillna(0.0)
        strat = r * expo
        to = expo.diff().abs().fillna(expo.abs())
        net = strat - to * COST_RT
        eqc = (1 + net).cumprod()
        years = len(net) / 365
        cagr = (eqc.iloc[-1] ** (1 / years) - 1) * 100
        dd = (eqc / eqc.cummax() - 1).min() * 100
        sh = net.mean() / net.std(ddof=1) * math.sqrt(365)
        print(f"{L:>9}d {cagr:>9.1f} {dd:>9.1f} {sh:>8.2f} {to.mean()*365:>12.1f}")
    bh = (1 + r).cumprod()
    print(f"{'buy&hold':>9} {((bh.iloc[-1])**(365/len(r))-1)*100:>9.1f} "
          f"{(bh/bh.cummax()-1).min()*100:>9.1f} "
          f"{r.mean()/r.std(ddof=1)*math.sqrt(365):>8.2f} {0:>12.1f}")

    print()
    print("=" * 100)
    print("VERDICT")
    print("=" * 100)
    if any_info:
        print("  At least one signal horizon carries information about what follows.")
        print("  Part B's portfolio table is the thing to read next, and the")
        print("  question becomes whether it survives cost and beats holding.")
    else:
        print("""  NO signal horizon in {21, 42, 63, 126} days carries information about
  what the market does next. A trailing return turning negative is not
  followed by a fall, at any horizon tested.

  Taken with E#9 (a price-based trailing stop, also noise), the conclusion is
  that there is NO exit rule in this family that works on this data. The
  statement "no stop is gambling" is therefore CORRECT rather than
  unanswered: on this sample there is nothing better to do than size down.""")


if __name__ == "__main__":
    main()
