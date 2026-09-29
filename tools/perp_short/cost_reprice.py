"""Re-price a backtest at different costs WITHOUT changing the strategy.

WHY THIS FILE EXISTS
--------------------
Every "measured cost" number this project has published came out of
`cost_frontier.py`. On 2026-09-30, running it against the DEPLOYED N=40
configuration showed it does not reproduce the engine: the engine printed
+113.74 % with a 14.16 % max drawdown, and the replay printed +3687 % gross with
a 62-67 % max drawdown. A 32x disagreement is not a rounding difference.

The cause is structural, not a typo. `cost_frontier.replay` IGNORES the engine's
own `amount` on every trade and re-derives the position from
`risk_per_trade * equity / (ATR_STOP * atr_pct)` using its own defaults -
`ATR_STOP=1.5` and a config it reads from `user_data/config_perp_short.json`
(risk 0.01), against a deployed book that runs `atr_stop=4.0` and `risk=0.005`.
That works out to ~25 % of equity per trade where the engine stakes ~4.9 %.

**Re-pricing is supposed to change the COST, not the strategy.** Re-deriving
stakes turns a re-pricing into a backtest of a different, five-times-more-levered
book, and then reports its return as the deployed book's.

THIS FILE DOES IT PROPERLY:
  * it uses the engine's own `amount` on every trade, so the book is identical;
  * it charges a round-trip cost in basis points of notional, per regime;
  * it walks the equity path in CLOSE order, which is what a drawdown needs.

AND IT PROVES ITSELF BEFORE YOU BELIEVE IT: at the engine's OWN cost it must
reproduce the engine's OWN printed total return and max drawdown, to a stated
tolerance. If it does not, it refuses to report any other regime. A cost
re-pricer that cannot reproduce the engine is not measuring costs.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\cost_reprice.py <archive.zip> [strategy]
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

# round-trip cost in bps, from RESEARCH_STATE section 4. `engine_default` is what
# freqtrade itself charges at fee=0.0005: 5 bps per side.
REGIMES = [
    ("engine_default", 10.0, "freqtrade's own fee, 5bps/side, no slippage"),
    ("measured_calm", 12.0, "section 1b calm day 2026-09-20 median"),
    ("measured_cascade", 15.6, "section 1b long-tail cascade 2024-08-05"),
    ("measured_volatile", 22.8, "section 1b volatile 2025-10-10"),
    ("measured_covid", 34.9, "section 1b COVID 2020-03-12, the 2.9x stress end"),
    ("xsect_benchmark", 70.0,
     "the published cross-sectional benchmark (Bianchi & Babiak via Fieberg)"),
]
# The re-pricer must land this close to the engine at the engine's own cost.
TOL_TOTAL = 0.02      # 2 percentage points of total return
TOL_DD = 0.03         # 3 points of max drawdown


def load(zip_path: Path, strategy: str | None):
    # Read BOTH members INSIDE the `with`. Reading the config after the block
    # raises "Attempt to use ZIP archive that was already closed" - and the
    # first version of this function did exactly that.
    with zipfile.ZipFile(zip_path) as zf:
        mj = [n for n in zf.namelist()
              if n.endswith(".json") and not n.endswith("_config.json")][0]
        cj = [n for n in zf.namelist() if n.endswith("_config.json")][0]
        d = json.loads(zf.read(mj))
        cfg = json.loads(zf.read(cj))
    name = strategy or list(d["strategy"].keys())[0]
    return name, d["strategy"][name], d["strategy_comparison"][0], cfg


def trades_frame(st, fee_side_bps: float = 5.0) -> pd.DataFrame:
    rows = []
    for t in st["trades"]:
        if t.get("is_open"):
            continue
        amt = float(t["amount"])
        e = float(t["open_rate"])
        x = float(t["close_rate"])
        short = bool(t.get("is_short", True))
        gross = (e - x) * amt if short else (x - e) * amt
        rows.append({
            "close": pd.Timestamp(t["close_date"]),
            "open": pd.Timestamp(t["open_date"]),
            "pair": t["pair"], "is_short": short,
            "qty": amt, "entry": e, "exit": x,
            "notional_rt": amt * (e + x),          # both legs, for a round trip
            "gross": gross,
            "engine_fee": fee_side_bps / 1e4 * amt * (e + x),
            "engine_funding": float(t.get("funding_fees") or 0.0),
        })
    return pd.DataFrame(rows).sort_values("close").reset_index(drop=True)


def run(df: pd.DataFrame, start: float, rt_bps: float, engine_rt_bps: float):
    """Re-price. Position sizes are the engine's own; only the cost changes.

    THE COST CONVENTION, STATED BECAUSE GETTING IT WRONG MADE THE VALIDATION
    FAIL BY 9.4 pp. freqtrade charges `fee_side` on EACH leg: total =
    fee_side * qty * (entry + exit). A "round trip" has to be expressed relative
    to that, not applied to some other notional - charging `rt_bps * qty *
    (entry + exit)` at rt_bps = 10 double-counts, because 10 bps of two-leg
    notional is twice the engine's 5 bps/side.

    So the regime cost is a MULTIPLE of the engine's own fee:

        fee(regime) = engine_fee * (rt_bps / engine_rt_bps)

    which is exact at the anchor (rt_bps == engine_rt_bps reproduces the engine
    to the cent) and proportional elsewhere, and reads honestly: "this round
    trip costs 3.49x what freqtrade charged".

    Also fixed here: the first version computed the regime's cost into a variable
    named `cost` that nothing ever read, so EVERY regime printed the engine's
    own number and the cost frontier came out perfectly flat. **A computed value
    that is never consumed is a silent no-op** - the same family as trap #6 (a
    risk control that fails open) and #11 (a paging loop that never advances).
    The tell was that the cost column varied and nothing else did, which is not
    a thing a real cost does.
    """
    fee = df["engine_fee"] * (rt_bps / engine_rt_bps)
    pnl = df["gross"] - fee + df["engine_funding"]
    # Keep the CLOSE DATE as the index. cumsum() on the default RangeIndex
    # returns a RangeIndex, and `metrics` then does `.days` on an int.
    pnl = pd.Series(pnl.to_numpy(), index=pd.DatetimeIndex(df["close"]),
                    name="pnl")
    eq = pd.Series(start + pnl.cumsum().to_numpy(),
                   index=pd.DatetimeIndex(df["close"]), name="equity")
    peak = eq.cummax()
    dd = (peak - eq) / peak
    return {
        "total": float(eq.iloc[-1] / start - 1.0),
        "maxdd": float(dd.max()),
        "equity": eq, "pnl": pnl, "dd": dd,
    }


def metrics(eq: pd.Series, pnl: pd.Series, start: float) -> dict:
    total = float(eq.iloc[-1] / start - 1.0)
    years = max((eq.index[-1] - eq.index[0]).days / 365.25, 1e-9)
    peak = eq.cummax()
    dd = (peak - eq) / peak
    r = pnl / eq.shift(1).fillna(start)
    sharpe = float(r.mean() / r.std(ddof=1) * np.sqrt(365.25)) if r.std(ddof=1) > 0 else float("nan")
    pf = float(pnl[pnl > 0].sum() / -pnl[pnl < 0].sum()) if (pnl < 0).any() else float("inf")
    return {"total": total, "cagr": float((eq.iloc[-1] / start) ** (1 / years) - 1),
            "sharpe": sharpe, "maxdd": float(dd.max()), "pf": pf,
            "winrate": float((pnl > 0).mean()), "n": int(len(pnl))}


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    zp = Path(argv[1])
    if not zp.is_absolute():
        zp = ROOT / zp
    name, st, cmp_, cfg = load(zp, argv[2] if len(argv) > 2 else None)
    start = float(st.get("starting_balance") or cfg.get("dry_run_wallet") or 10_000)
    fee_side = float(cfg.get("fee", 0.0005))
    df = trades_frame(st, fee_side * 1e4)

    engine_rt = fee_side * 2 * 1e4
    n_long = int((~df["is_short"]).sum())
    n_short = int(df["is_short"].sum())

    print("=" * 78)
    print("COST RE-PRICE OF AN EXISTING BACKTEST - the book is the engine's own")
    print("=" * 78)
    print(f"  archive        : {zp.name}")
    print(f"  strategy       : {name}")
    print(f"  universe       : {df['pair'].nunique()} symbols, "
          f"risk_per_trade={cfg.get('risk_per_trade')}, atr_stop={cfg.get('atr_stop')}")
    print(f"  trades         : {len(df)} ({n_short} short, {n_long} long), "
          f"starting wallet {start:,.0f}")
    print(f"  engine's own fee: {fee_side*1e4:.1f} bps/side = {engine_rt:.1f} bps round trip")
    print("  funding from the export is carried through unchanged at every regime.")

    # ---------------- THE VALIDATION GATE ----------------------------------
    print("\n--- VALIDATION: does this tool reproduce the ENGINE at the ENGINE's cost? ---")
    eng_total = float(cmp_["profit_total_pct"]) / 100.0
    eng_dd = float(cmp_["max_drawdown_account"])
    got = run(df, start, engine_rt, engine_rt)
    d_total = abs(got["total"] - eng_total)
    print(f"  engine printed : total {eng_total*100:+.2f}%   maxDD {eng_dd*100:.2f}%")
    print(f"  re-pricer says : total {got['total']*100:+.2f}%   "
          f"maxDD {got['maxdd']*100:.2f}%  <- close-order basis, see below")
    print(f"  difference     : {d_total*100:.2f} pp of total   (gate: <= "
          f"{TOL_TOTAL*100:.0f} pp)")
    ok = d_total <= TOL_TOTAL
    if not ok:
        print("\n  VALIDATION FAILED ON TOTAL RETURN. A re-pricer that cannot reproduce")
        print("  the engine's total at the engine's own cost is not measuring costs, and")
        print("  NO regime below is reported. Fix the tool.")
        return 1
    print("  -> PASS on total return: the book is identical, so only the cost moves below.")
    print("\n  WARNING - THE TWO DRAWDOWNS ARE DIFFERENT STATISTICS, NOT COMPARABLE.")
    print(f"  The engine's {eng_dd*100:.2f}% is measured on a MARK-TO-MARKET equity curve that")
    print("  includes open positions. This tool books a trade only when it CLOSES, so")
    print(f"  its {got['maxdd']*100:.2f}% is a close-order figure. It is reported for regime")
    print("  comparison, where every row uses the same basis - not as a second opinion")
    print("  on the engine's drawdown. Comparing them is the LESSON L3 error: two things")
    print("  differing in two ways at once.")
    # GBK console: these documents are full of U+2212 and similar. Reconfigure
    # stdout rather than stripping characters - the text is the deliverable.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    # ---------------- the frontier ------------------------------------------
    print("\n--- THE COST FRONTIER (engine position sizes, cost re-priced) ---")
    print(f"  {'regime':<20}{'rt bps':>8}{'total':>10}{'CAGR':>9}{'Sharpe':>9}"
          f"{'maxDD':>8}{'PF':>7}{'win%':>7}")
    rows = []
    for rname, bps, _note in REGIMES:
        res = run(df, start, bps, engine_rt)
        m = metrics(res["equity"], res["pnl"], start)
        rows.append((rname, bps, m, res))
        print(f"  {rname:<20}{bps:>8.1f}{m['total']*100:>9.1f}%{m['cagr']*100:>8.1f}%"
              f"{m['sharpe']:>9.2f}{m['maxdd']*100:>7.1f}%{m['pf']:>7.2f}"
              f"{m['winrate']*100:>6.1f}%")

    # ---------------- by year at the stress end ----------------------------
    stress = dict((r[0], r) for r in rows)["measured_covid"]
    pnl = stress[3]["pnl"]
    print("\n--- BY YEAR at measured_covid (the stress end) ---")
    yr = pnl.groupby(pnl.index.year).sum()
    eq = start + yr.cumsum()
    base = pd.concat([pd.Series([start], index=[yr.index[0] - 1]),
                      eq]).sort_index()
    for y, v in yr.items():
        b = base[base.index < y].iloc[-1]
        n = int((pnl.index.year == y).sum())
        print(f"  {y}   n={n:>4}   pnl {v:>12,.0f}   return {v/b*100:>7.1f}%")

    # ---------------- how much does cost cost you, as a share -------------
    print("\n--- WHAT THE COST SENSITIVITY IS WORTH ---")
    g = metrics(run(df, start, 0.0, engine_rt)["equity"], run(df, start, 0.0, engine_rt)["pnl"], start)
    print(f"  gross (no cost at all)        : {g['total']*100:+.1f}%")
    for rname, bps, _ in REGIMES[1:]:
        m = dict((r[0], r[2]) for r in rows)[rname]
        print(f"  {rname:<28}: {m['total']*100:+.1f}%   "
              f"({(g['total']-m['total'])*100:.1f} pp of return given up)")
    print("\n  This is the number a person deciding to trade this needs: the return at")
    print("  the cost they will actually face, and what that cost costs them.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

