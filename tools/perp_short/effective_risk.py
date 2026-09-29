"""V-1: does `risk_per_trade` mean what it says, and what actually limits concurrency?

PRE-REGISTERED in docs-myself/PREREG_EFFECTIVE_RISK_2026-09-30.md.

Two questions, both left open by earlier rounds:
  * C-1 ruled OUT `max_open_trades=24` as the reason trade count falls with risk, and
    said the remaining explanation (free balance) was INFERRED, not measured.
  * Nobody has ever checked whether the `max_stake_frac = 0.25` clip makes the ACTUAL
    risk smaller than the configured `risk_per_trade`, differently per symbol.

    notional = risk * equity / (4 * atr_pct),  then clipped to equity * 0.25
    -> the clip binds whenever  risk / (4 * atr_pct) > 0.25
    -> i.e. whenever atr_pct < risk

So at 1.5 % requested risk, EVERY symbol with 4h ATR below 1.5 % is clipped, and its
real risk is lower - and different symbols end up carrying different risk under one
config value. That would mean `risk_per_trade` stops meaning what it says.

No backtest is run: this reads the six existing risk-frontier archives.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\effective_risk.py
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from risk_unit import _atr_frame, DATA  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RUNS = ["n40_r00025", "n40_r00040", "n40_r00050",
        "n40_r00075", "n40_r00100", "n40_r00150"]
MAX_STAKE_FRAC = 0.25
ATR_STOP = 4.0
MIN_EFFECTIVE = 0.90      # gate V1b
CONCURRENCY_CAP = 24


def head(t: str) -> None:
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def load(tag: str):
    zips = sorted((ROOT / "user_data" / "risk_out" / tag).glob("*.zip"))
    if not zips:
        return None, None
    with zipfile.ZipFile(zips[-1]) as zf:
        mj = [n for n in zf.namelist()
              if n.endswith(".json") and not n.endswith("_config.json")][0]
        d = json.loads(zf.read(mj))
    st = d["strategy"]["PerpShort4hDeploy"]
    tr = [t for t in st["trades"] if not t.get("is_open")]
    cfg = json.loads((ROOT / "user_data" / f"config_risk_{tag}.json")
                     .read_text(encoding="utf-8"))
    return tr, cfg


def concurrency(trades: list[dict]):
    """Time-sweep the open positions: mean, median, p95, max, share of events at cap."""
    ev = []
    for t in trades:
        ev.append((pd.Timestamp(t["open_date"]), 1))
        ev.append((pd.Timestamp(t["close_date"]), -1))
    # open before close on the same timestamp: a position that closes exactly when
    # another opens was occupying a slot right up to that instant
    ev.sort(key=lambda x: (x[0], -x[1]))
    cur, series = 0, []
    for _, d in ev:
        cur += d
        series.append(cur)
    s = np.array(series, dtype=float)
    return (float(s.mean()), float(np.median(s)), float(np.percentile(s, 95)),
            int(s.max()), float((s >= CONCURRENCY_CAP).mean()))


def main() -> int:
    print("V-1 DOES `risk_per_trade` MEAN WHAT IT SAYS?\n")
    print("Pre-registered in docs-myself/PREREG_EFFECTIVE_RISK_2026-09-30.md.")
    print("No backtest is run: this reads the six existing risk-frontier archives.\n")
    print(f"  position size = min(risk*equity/(4*atr%), equity*{MAX_STAKE_FRAC})")
    print(f"  so the {MAX_STAKE_FRAC:.0%} clip binds whenever 4*atr% < risk\n")

    atr_cache: dict[str, pd.DataFrame] = {}
    rows = []
    for tag in RUNS:
        tr, cfg = load(tag)
        if not tr:
            continue
        req = float(cfg["risk_per_trade"])
        eff, clipped, atr_used = [], 0, 0
        for t in tr:
            p = t["pair"]
            if p not in atr_cache:
                f = DATA / f"{p.replace('/', '_').replace(':', '_')}-4h-futures.feather"
                if not f.exists():
                    continue
                atr_cache[p] = _atr_frame(f)
            df = atr_cache[p]
            ts = pd.Timestamp(t["open_date"])
            a = np.nan
            for cand in (ts, ts - pd.Timedelta(hours=4)):
                try:
                    v = df.at[cand, "atr"]
                except KeyError:
                    continue
                if np.isfinite(v) and v > 0:
                    a = float(v)
                    break
            entry = float(t["open_rate"])
            if not (np.isfinite(a) and a > 0 and entry > 0):
                continue
            atr_used += 1
            wanted = req / (ATR_STOP * (a / entry))     # fraction of equity asked for
            if wanted > MAX_STAKE_FRAC:
                clipped += 1
            eff.append(min(wanted, MAX_STAKE_FRAC))

        e = np.array(eff)
        cm, cmed, cp95, cmax, atcap = concurrency(tr)
        rows.append({
            "tag": tag, "requested": req, "n": len(tr), "n_with_atr": atr_used,
            "clipped_frac": clipped / max(atr_used, 1),
            "eff_median": float(np.median(e)) if len(e) else np.nan,
            "eff_p10": float(np.percentile(e, 10)) if len(e) else np.nan,
            "eff_over_req": float(np.median(e)) / req if len(e) else np.nan,
            "conc_mean": cm, "conc_median": cmed, "conc_p95": cp95,
            "conc_max": cmax, "at_cap": atcap,
        })
        print(f"  ran {tag}  requested={req*100:.2f}%  trades={len(tr)}  "
              f"clipped={clipped/max(atr_used,1)*100:.1f}%  "
              f"median effective/requested={rows[-1]['eff_over_req']:.3f}")

    if not rows:
        return 1
    df = pd.DataFrame(rows).sort_values("requested")

    head("V1a/V1b - DOES THE 25% CLIP EAT THE REQUESTED RISK?")
    print(f"  {'requested':>10}{'trades':>8}{'clipped':>9}{'eff p10':>10}"
          f"{'eff median':>12}{'eff/req':>9}")
    for _, r_ in df.iterrows():
        print(f"  {r_['requested']*100:>9.2f}%{r_['n']:>8}"
              f"{r_['clipped_frac']*100:>8.1f}%{r_['eff_p10']*100:>9.2f}%"
              f"{r_['eff_median']*100:>11.2f}%{r_['eff_over_req']:>9.3f}")
    bad = df[df["eff_over_req"] < MIN_EFFECTIVE]
    print(f"\n  -> V1b {'PASS' if bad.empty else 'FAIL'}: "
          + ("no rung delivers materially less risk than its config states"
             if bad.empty else
             "at least one rung delivers materially LESS risk than the config says"))

    head("V1c - WAS THE SLOT CAP EVER BINDING?")
    print(f"  {'requested':>10}{'conc mean':>11}{'median':>9}{'p95':>7}{'MAX':>7}"
          f"{'events at cap':>15}")
    for _, r_ in df.iterrows():
        print(f"  {r_['requested']*100:>9.2f}%{r_['conc_mean']:>11.1f}"
              f"{r_['conc_median']:>9.0f}{r_['conc_p95']:>7.0f}{r_['conc_max']:>7d}"
              f"{r_['at_cap']*100:>14.2f}%")
    hit = df[df["conc_max"] >= CONCURRENCY_CAP]
    print(f"\n  -> V1c: the cap was {'REACHED' if len(hit) else 'NEVER REACHED'} "
          f"(max observed {int(df['conc_max'].max())} against a cap of "
          f"{CONCURRENCY_CAP}).")
    if len(hit):
        print("     **This CONTRADICTS C-1, which raised the cap to 96 and changed")
        print("     nothing. Re-open the C-1 explanation before using either.**")
    else:
        print("     Consistent with C-1: the 24-slot cap was never the binding")
        print("     constraint, so what limits concurrency is NOT the configured cap.")

    head("V1d - AND WHAT DOES LIMIT IT?")
    print("  Concurrency is capped far below 24, and trade count FALLS as risk rises")
    print("  (measured in the risk frontier). Both are consistent with free balance:")
    print("  `stake_amount: unlimited` still needs balance, so 3x the position size")
    print("  funds a third of the concurrency.")
    print("\n  THIS REMAINS AN INFERENCE. What was measured here is the CONCURRENCY")
    print("  DISTRIBUTION and the SIZE CLIP, not the relationship between concurrency")
    print("  and free balance. It is recorded as open, not as settled.")

    out = ROOT / "user_data" / "perp_short_out" / "effective_risk.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"\n  written: {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
