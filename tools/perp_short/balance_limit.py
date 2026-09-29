"""B-1: is concurrency limited by FREE BALANCE, or by the 24-slot cap?

PRE-REGISTERED in docs-myself/PREREG_BALANCE_2026-09-30.md.

V-1 (section 30c) ruled the slot cap out at every risk above 0.5 %, and left
"free balance" as an INFERENCE it had not measured. This measures it.

The test is clean because the two hypotheses predict different things:

  * if the SLOT CAP binds, the committed-notional ratio at entry clusters near a
    ceiling that is the SAME at every risk level - the cap does not know the
    position size;
  * if FREE BALANCE binds, the ratio clusters near a ceiling that MOVES with
    risk, because each rung's positions are larger and the same wallet funds
    fewer of them.

So: build the equity and the open-notional path trade by trade, and look at
where the ratio sits when a new position is opened.

No backtest is run. Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\balance_limit.py
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RUNS = ["n40_r00025", "n40_r00040", "n40_r00050",
        "n40_r00075", "n40_r00100", "n40_r00150"]
START = 10_000.0
TOL = 0.02          # B1a


def head(t: str) -> None:
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def events(trades: list[dict]):
    """One row per (timestamp, trade, kind) with net P&L and notional.

    Fees are charged on NOTIONAL: `fee_open`/`fee_close` in the export are
    RATES, and the amount charged is rate * qty * price. Getting this wrong
    overcharges by ~3x on this panel and was a real bug in round 35.
    """
    out = []
    for t in trades:
        e, x, q = float(t["open_rate"]), float(t["close_rate"]), float(t["amount"])
        g = (e - x) * q if t.get("is_short", True) else (x - e) * q
        fee = float(t["fee_open"]) * q * e + float(t["fee_close"]) * q * x
        net = g - fee + float(t.get("funding_fees") or 0.0)
        out.append({
            "open": pd.Timestamp(t["open_date"]),
            "close": pd.Timestamp(t["close_date"]),
            "notional": q * e,
            "net": net,
        })
    return out


def analyse(tag: str):
    zips = sorted((ROOT / "user_data" / "risk_out" / tag).glob("*.zip"))
    if not zips:
        return None
    with zipfile.ZipFile(zips[-1]) as zf:
        mj = [n for n in zf.namelist()
              if n.endswith(".json") and not n.endswith("_config.json")][0]
        d = json.loads(zf.read(mj))
    st = d["strategy"]["PerpShort4hDeploy"]
    cmp_ = d["strategy_comparison"][0]
    tr = [t for t in st["trades"] if not t.get("is_open")]
    ev = events(tr)
    cfg = json.loads((ROOT / "user_data" / f"config_risk_{tag}.json")
                     .read_text(encoding="utf-8"))

    # B1a: the reconstruction must reconcile with the engine
    recon = sum(e["net"] for e in ev)
    eng = float(cmp_["profit_total_abs"])
    if abs(recon - eng) > max(TOL * max(abs(eng), 1.0), 1.0):
        print(f"  [ABORT] {tag}: reconstructed {recon:,.0f} vs engine {eng:,.0f}")
        return None

    # Walk the book forward on a single TIME-ordered event stream.
    #
    # ⚠ The first version sorted ONE list by open date and then advanced a
    # pointer looking for closes matching the current timestamp. Two different
    # orderings in one walk, so `equity`, `open_notional` and `open_n` drifted
    # without bound: it reported committed p50 of 1823 % and a concurrency of
    # 1173. The absurdity is what caught it.
    #
    # One stream, sorted by (time, kind) with CLOSES FIRST, and the open book
    # carried explicitly. Nothing is matched by timestamp equality.
    stream = []
    for i, e in enumerate(ev):
        stream.append((e["open"], 1, i))     # kind 1 = open
        stream.append((e["close"], 0, i))    # kind 0 = close, so it sorts first
    stream.sort(key=lambda x: (x[0], x[1]))

    equity = START
    live = {}            # index -> notional, the open book
    ratios, frees, n_at_entry = [], [], []
    for _, kind, i in stream:
        if kind == 0:                        # close
            equity += ev[i]["net"]
            live.pop(i, None)
        else:                                 # open
            free = equity - sum(live.values())
            ratios.append((sum(live.values()) + ev[i]["notional"]) / equity)
            frees.append(free / equity)
            n_at_entry.append(len(live) + 1)
            live[i] = ev[i]["notional"]
    r = np.array(ratios)
    f = np.array(frees)
    return {
        "tag": tag, "requested": float(cfg["risk_per_trade"]),
        "trades": len(tr), "engine_total": eng, "recon": recon,
        "r_med": float(np.median(r)), "r_p90": float(np.percentile(r, 90)),
        "r_p99": float(np.percentile(r, 99)), "r_max": float(r.max()),
        "free_med": float(np.median(f)), "free_p10": float(np.percentile(f, 10)),
        "conc_max": int(max(n_at_entry)),
    }


def main() -> int:
    print("B-1 IS CONCURRENCY LIMITED BY FREE BALANCE, OR BY THE SLOT CAP?\n")
    print("Pre-registered in docs-myself/PREREG_BALANCE_2026-09-30.md.")
    print("No backtest is run: this reads the six existing risk-frontier archives.\n")
    print("  slot cap   predicts a commitment ceiling that is the SAME at every rung")
    print("  free balance predicts a ceiling that MOVES with the rung\n")

    rows = [r for r in (analyse(t) for t in RUNS) if r]
    if not rows:
        return 1
    df = pd.DataFrame(rows).sort_values("requested")

    head("B1a - DOES THE RECONSTRUCTION MATCH THE ENGINE?")
    df["err"] = (df["recon"] - df["engine_total"]).abs() / df["engine_total"].abs()
    print(f"  max reconstruction error: {df['err'].max()*100:.3f}%  -> B1a "
          f"{'PASS' if df['err'].max() < TOL else 'FAIL'}")
    if df["err"].max() >= TOL:
        return 1

    head("THE MEASUREMENT - commitment at the moment of each entry")
    print("  'committed' = open notional (including the new one) / equity at entry")
    print(f"  {'requested':>10}{'trades':>8}{'committed p50':>15}{'p90':>9}"
          f"{'p99':>9}{'max':>8}{'free p10':>10}{'conc max':>10}")
    for _, r_ in df.iterrows():
        print(f"  {r_['requested']*100:>9.2f}%{r_['trades']:>8}"
              f"{r_['r_med']*100:>14.1f}%{r_['r_p90']*100:>8.1f}%"
              f"{r_['r_p99']*100:>8.1f}%{r_['r_max']*100:>7.1f}%"
              f"{r_['free_p10']*100:>9.1f}%{r_['conc_max']:>10d}")

    head("B1b / B1c - DOES THE CEILING MOVE WITH THE RISK RUNG?")
    p90 = df["r_p90"].to_numpy()
    spread = float(p90.max() / max(p90.min(), 1e-9))
    print(f"  p90 of committed, by rung: "
          f"{[f'{x*100:.0f}%' for x in sorted(p90)]}")
    print(f"  ratio max/min across rungs: {spread:.2f}x")
    if spread > 2.0:
        print("\n  -> B1b PASS: **the ceiling MOVES with the risk rung**, which the")
        print("     slot cap cannot do - it does not know the position size.")
        print("     **H-B1 CONFIRMED: free balance is the binding constraint.**")
        print("     The V-1 inference is now a measurement.")
    elif spread < 1.5:
        print("\n  -> B1c: **the ceiling is roughly the SAME at every rung**, which is")
        print("     what a fixed cap would produce.")
        print("     **H-B2: free balance is NOT the constraint. The V-1 inference was")
        print("     wrong, and it is recorded as wrong.**")
    else:
        print("\n  -> INCONCLUSIVE by the pre-registered bands (needs >2x for H-B1,")
        print("     <1.5x for H-B2). Reported as inconclusive, not rounded to a side.")

    print(f"\n  note: the engine's own `max_open_trades` is {int(df['conc_max'].max())} "
          f"observed at most across all rungs.")
    out = ROOT / "user_data" / "perp_short_out" / "balance_limit.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"  written: {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
