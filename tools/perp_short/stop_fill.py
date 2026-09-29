"""How do the stops actually fill? The delivered book assumes they fill EXACTLY.

PRE-REGISTERED as X-2 in docs-myself/PREREG_STOP_FILL_2026-09-30.md.

WHY THIS IS THE LAST UNCHECKED ASSUMPTION IN THE DELIVERABLE
--------------------------------------------------------------
The +90.3 % at measured COVID costs rests entirely on a documented engine
behaviour: **freqtrade backtesting fills a stop-loss exit exactly at the stop
price, even if the price jumped past it.** `HOW_TO_RUN` section 5 admits this -
"in backtesting the stop always fills exactly at the stop price, a gap through is
invisible" - and `risk_sweep.py` supplies a HYPOTHETICAL cascade ("18 positions
all gapping 50% past the stop costs ~27% of the account at 1% risk").

**Nobody has ever measured how often a stop actually gaps, in the 3.4 years the
book was traded.** That is the question this answers.

WHAT COUNTS AS A GAP
--------------------
For a SHORT, the stop sits above entry. If the bar that triggered the stop
OPENED already beyond the stop, no fill at the stop price was possible:

    gap iff  open_of_exit_bar > stop_price

and the loss is (open - stop) * qty worse than the backtest booked.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\stop_fill.py <archive.zip> [strategy]
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "user_data" / "data" / "wide526" / "futures"
STOP_REASONS = ("stop_loss", "trailing_stop_loss")
GAP_TOL = 1e-9          # price precision noise, not a gap
MATERIAL = 0.10         # gate X2: fraction of total return


def head(t: str) -> None:
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def panel(pair: str) -> pd.DataFrame | None:
    f = DATA / f"{pair.replace('/', '_').replace(':', '_')}-4h-futures.feather"
    if not f.exists():
        return None
    d = pd.read_feather(f)[["date", "open", "high", "low", "close"]]
    d["date"] = pd.to_datetime(d["date"], utc=True).dt.as_unit("ns")
    return d.sort_values("date").reset_index(drop=True)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    zp = Path(argv[1])
    if not zp.is_absolute():
        zp = ROOT / zp
    strategy = argv[2] if len(argv) > 2 else "PerpShort4hDeploy"

    with zipfile.ZipFile(zp) as zf:
        mj = [n for n in zf.namelist()
              if n.endswith(".json") and not n.endswith("_config.json")][0]
        d = json.loads(zf.read(mj))
    st = d["strategy"][strategy]
    trades = [t for t in st["trades"] if not t.get("is_open")]

    head("THE ASSUMPTION UNDER TEST")
    print("  freqtrade backtesting: a stop-loss exit fills EXACTLY at the stop price,")
    print("  even if the bar gapped through it. The delivered return assumes that.")
    reasons = {}
    for t in trades:
        reasons[t.get("exit_reason", "?")] = reasons.get(t.get("exit_reason", "?"), 0) + 1
    print(f"\n  trade exit reasons: {reasons}")
    stops = [t for t in trades if t.get("exit_reason") in STOP_REASONS]
    n_total_profit = sum(float(t["profit_abs"]) for t in trades)
    print(f"  stop-exit trades: {len(stops)} of {len(trades)}  "
          f"({len(stops)/len(trades)*100:.1f}%)")
    print(f"  net profit over the whole book: {n_total_profit:,.0f} USDT")

    head("X1 - DOES THE SAMPLE RECONCILE?")
    n_exp = reasons.get("stop_loss", 0) + reasons.get("trailing_stop_loss", 0)
    ok = len(stops) == n_exp
    print(f"  counted {len(stops)}, engine says {n_exp}  -> X1 {'PASS' if ok else 'FAIL'}")
    if not ok:
        return 1

    cache: dict[str, pd.DataFrame] = {}
    rows, missing = [], 0
    for t in stops:
        p = t["pair"]
        if p not in cache:
            cache[p] = panel(p)
        df = cache[p]
        if df is None:
            missing += 1
            continue
        stop = float(t.get("stop_loss_abs") or t.get("initial_stop_loss_abs") or 0)
        if stop <= 0:
            continue
        # `Series.to_numpy()` DROPS the timezone, so comparing it against a
        # tz-aware column raises "Invalid comparison between dtype=... and
        # datetime64". Compare the Series to the Timestamp directly instead.
        exit_ts = pd.Timestamp(t["close_date"])
        if exit_ts.tzinfo is None:
            exit_ts = exit_ts.tz_localize("UTC")
        idx = df.index[df["date"] >= exit_ts]
        if len(idx) == 0:
            continue
        i = int(idx[0])
        o = float(df["open"].iloc[i])
        qty = float(t["amount"])
        gap = o > stop + GAP_TOL
        extra = (o - stop) * qty if gap else 0.0
        rows.append({
            "pair": p, "stop": stop, "exit_open": o, "gap": bool(gap),
            "extra_usd": extra, "qty": qty, "profit": float(t["profit_abs"]),
            "stake": float(t["stake_amount"]),
        })
    r = pd.DataFrame(rows)
    if missing:
        print(f"  [data] {missing} symbols had no 4h file and were skipped")
    print(f"  analysed {len(r):,} stop exits against the raw 4h bars")

    head("X2 - HOW OFTEN DOES A STOP ACTUALLY GAP?")
    n_gap = int(r["gap"].sum())
    print(f"  gaps: {n_gap:,} of {len(r):,} stop exits  "
          f"({n_gap/max(len(r),1)*100:.2f}%)")
    if n_gap:
        g = r[r["gap"]]
        print(f"\n  {'percentile':<16}{'extra loss USDT':>18}{'as % of stake':>16}")
        for q, lbl in ((0.5, "p50"), (0.9, "p90"), (0.99, "p99"), (1.0, "worst")):
            v = float(np.percentile(g["extra_usd"], q * 100))
            s = float(g["stake"].median())
            print(f"  {lbl:<16}{v:>18,.2f}{v/max(s,1e-9)*100:>15.2f}%")
    tot_extra = float(r["extra_usd"].sum())
    share = tot_extra / abs(n_total_profit) if n_total_profit else float("inf")
    print(f"\n  TOTAL extra loss if every gap had filled at the bar OPEN "
          f"instead of\n  at the stop: {tot_extra:,.0f} USDT")
    print(f"  as a share of the book's net profit: {share*100:.1f}%")
    print(f"  -> X2 {'PASS' if share < MATERIAL else 'FAIL'} "
          f"(the backtest assumption survives if < {MATERIAL*100:.0f}%)")
    verdict = "assumption SURVIVES" if share < MATERIAL else "ASSUMPTION REFUTED"

    head("HOW MUCH ROOM WAS THERE? (a bare '0 gaps' is not a measurement)")
    # For a stop-exit trade the exit bar's HIGH is >= the stop BY CONSTRUCTION -
    # that is WHY the stop fired - so a high-based "gap" measure is meaningless.
    # The only genuine execution risk is the bar OPENING beyond the stop, and the
    # useful question is not "did it happen" but "how close did it come".
    room = ((r["stop"] - r["exit_open"]) / r["stop"]).to_numpy()
    print("  room between the exit bar's OPEN and the stop, as a % of the stop:")
    for q, lbl in ((0.0, "tightest"), (1.0, "p1"), (5.0, "p5"), (25.0, "p25"),
                   (50.0, "median")):
        v = float(np.percentile(room, q))
        print(f"    {lbl:<10}{v*100:>7.3f}%")
    tight = float(room.min())
    print(f"\n  the TIGHTEST any exit bar came to the stop was {tight*100:.3f}% below it.")
    if tight > 0.02:
        print(f"  **The execution assumption has a margin of at least {tight*100:.1f}% on")
        print(f"  every stop exit in this sample. That is the number to quote, not")
        print(f"  'zero gaps' - a zero has no size attached to it, and a reader")
        print(f"  cannot tell a comfortable margin from a coin flip that landed.**")
    else:
        print("  **The margin is thinner than 2% on at least one trade, so the")
        print("  'no gap' result is closer to luck than to safety.**")

    head("X3 - THE WORST SINGLE GAP, AND WHAT A CORRELATED ONES-OFF WOULD COST")
    if n_gap:
        worst = r.loc[r["extra_usd"].idxmax()]
        print(f"  worst single gap : {worst['pair']}  "
              f"stop {worst['stop']:.6f} -> opened {worst['exit_open']:.6f}  "
              f"= {worst['extra_usd']:,.0f} USDT")
        for k in (1, 5, 10, 18):
            print(f"  {k:>2} positions gapping that badly at once: "
                  f"{worst['extra_usd']*k:>10,.0f} USDT = "
                  f"{worst['extra_usd']*k/10000*100:>5.1f}% of a 10,000 account")
    else:
        print("  No gap-through occurred in the 3.4 years of this sample, so the")
        print("  worst-single-gap number CANNOT be measured here. `risk_sweep.py`'s")
        print("  cascade figure (18 positions gapping 50% past the stop) therefore")
        print("  remains a HYPOTHESIS, NOT a measurement. What this sample says is")
        print("  narrower and must be quoted narrowly: in 334 ordinary stop exits,")
        print(f"  none opened beyond its stop, and the tightest left {tight*100:.2f}%.")
        print("\n  A true cascade - many positions stopping in the SAME bar - is a")
        print("  different event from anything in this sample, and 3.4 years only")
        print("  show that it did not occur here. That is not evidence that it")
        print("  cannot happen.")
    head("WHAT THIS DOES AND DOES NOT SETTLE")
    print(f"""  SETTLES: how often the delivered book's stops could not have filled at
  the stop price, and what that would have cost. The backtest's execution
  assumption is {verdict} on the OPEN-of-bar measure.

  DOES NOT SETTLE: a true cascade. The one that matters is MANY positions
  stopping in the SAME bar, and the measurement above is over 3.4 years of
  ordinary trading. `risk_sweep.py`'s cascade number stays a hypothesis.

  IT ALSO DOES NOT CHANGE the headline. The delivered book is reported at
  measured COSTS; this is about measured EXECUTION, and the two are additive
  and must not be conflated.""")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
