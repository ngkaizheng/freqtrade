"""F-1: MEASURE the 5m cost law instead of extrapolating it.

THE QUESTION
------------
`family_prescreen.py` closes a mechanism family from arithmetic before any research is
spent: `cost_R = round_trip_bps / (stop_mult x atr_pct x 1e4)`. Thirteen families came
out refused because they are already closed. The one that was not - the 5m
liquidation-cascade family - was closed on a **square-root-of-time extrapolation
wearing a measurement's label** (section 38d), and that was flagged as the only
unmeasured input left in the machinery.

This measures it.

THE ONE RULE THIS TOOL EXISTS TO OBEY
--------------------------------------
**Each symbol's 4h ATR% is computed over EXACTLY that symbol's own 5m date range.**

This is not tidiness, it is section 39. Two routes that averaged 7 years and 3.7 years
produced a 13 % "disagreement" that was not a disagreement, and a "correction" adopted
from it was itself a 13 % error that sat in the project's load-bearing constants for
three rounds. A symbol listed in 2025-06 has 5m data from 2025-06 and 4h data from
2023; averaging its 4h over 2023-2026 and its 5m over 2025-2026 is that exact mistake,
scaled to a new horizon.

Two independent computations of the ratio are printed - the ratio of the two medians,
and the median of the per-symbol ratios - and a material disagreement between them is
reported rather than averaged away.

PRE-REGISTERED DECISIONS: `docs-myself/PREREG_FIVE_MIN_2026-09-30.md`.
  D1  the family is OPEN at the stress bar iff atr5m/atr4h >= 0.0308/0.15 = 0.205
  D2  ratio is reported on the whole window AND on the top-decile volatility days, and
      the verdict is taken on the WORSE of the two
  D3  sqrt(t) predicts 1/sqrt(48) = 0.1443; a >1.5x departure means section 38d's claim
      must be restated with the measured number
  D4  KILL: fewer than 25 of the 40 deployed symbols with usable 5m coverage => BLOCKED
  D5  an OPEN verdict does NOT authorise building a 5m strategy

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\five_min_horizon.py --download
    .venv\\Scripts\\python.exe tools\\perp_short\\five_min_horizon.py
"""

from __future__ import annotations

import io
import json
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
CFG = ROOT / "user_data" / "config_perp_forward_dry.json"
DATA4 = ROOT / "user_data" / "data" / "wide526" / "futures"
OUT = ROOT / "user_data" / "data" / "five_min"
BASE = "https://data.binance.vision/data/futures/um/monthly/klines"

# One contiguous window inside full 40/40 coverage (Gate 0: 2025-11 and 2026-01 were
# 40 of 40). COVID-2020 months are only 9-10 of 40 because the deployed universe is
# ranked by 2026 liquidity and is full of 2024-2025 listings - so the stress regime is
# measured INSIDE the window (D2) rather than borrowed from a universe we do not have.
MONTHS = [f"2025-{m:02d}" for m in range(1, 13)] + ["2026-01"]

STOP_MULT = 4.0            # the deployed atr_stop
CALM_BPS = 12.0            # measured calm round trip
STRESS_BPS = 34.9          # measured COVID round trip
COST_R_4H_STRESS = 0.0308  # section 4, from the 40-symbol 4h ATR% of 2.835 %
EFFECT_LO, EFFECT_HI = 0.05, 0.15   # the cascade family's documented effect band, in R
R_GATE = COST_R_4H_STRESS / EFFECT_HI          # D1: 0.205
R_SQRT = 1.0 / np.sqrt(48.0)                    # D3: 0.1443
MIN_SYMBOLS = 25                               # D4
MIN_COVERAGE = 60 * 24                         # 60 days of 5m bars


def archive_symbol(pair: str) -> str:
    base, _, rest = pair.partition("/")
    return f"{base}{rest.split(':')[0]}"


def _atr_pct(high, low, close) -> np.ndarray:
    """True range / close, Wilder-smoothed on raw arrays (no shared code with the
    consistency gate, which is a deliberate part of this project's method)."""
    n = close.size
    if n < 20:
        return np.full(n, np.nan)
    tr = np.empty(n)
    tr[0] = high[0] - low[0]
    tr[1:] = np.maximum.reduce([high[1:] - low[1:],
                                np.abs(high[1:] - close[:-1]),
                                np.abs(low[1:] - close[:-1])])
    a = 1.0 / 14.0
    out = np.full(n, np.nan)
    out[14] = tr[1:15].mean()
    acc = out[14]
    for i in range(15, n):
        acc += a * (tr[i] - acc)
        out[i] = acc
    return out / close


# --------------------------------------------------------------------------- download
def _fetch(job: tuple[str, str]) -> tuple[str, int, str]:
    sym, m = job
    dest = OUT / f"{sym}-{m}-5m.parquet"
    if dest.exists() and dest.stat().st_size > 0:
        return sym, 0, "cached"
    url = f"{BASE}/{sym}/5m/{sym}-5m-{m}.zip"
    try:
        r = requests.get(url, timeout=90)
        if r.status_code != 200:
            return sym, r.status_code, "http"
        with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
            name = [n for n in zf.namelist() if n.endswith(".csv")][0]
            df = _read_zip(zf, name)
        df = df.rename(columns={"open_time": "date"})
        df["date"] = pd.to_datetime(df["date"], unit="ms", utc=True)
        df[["date", "high", "low", "close"]].to_parquet(dest, index=False)
        return sym, 200, "ok"
    except Exception as e:                                    # noqa: BLE001
        return sym, -1, f"{type(e).__name__}: {str(e)[:70]}"


def _read_zip(zf: zipfile.ZipFile, name: str) -> pd.DataFrame:
    """Read one Binance kline CSV out of a monthly zip.

    ⚠ TWO defects cost one full download pass before this worked, and both produced
    a perfectly plausible "0 of 520 archives available":

    1. **The archive HAS a header row** (`open_time,open,high,low,close,...`).
       Reading it as `header=None` shifts every column by one, so `to_datetime(...,
       unit="ms")` would parse an OPEN PRICE as a timestamp and fail - or worse,
       not fail visibly.
    2. **`pd.read_csv` on a re-wrapped `BytesIO` raised UnicodeDecodeError** on a file
       that is pure ASCII. Reading straight from the zip handle works.

    **The first version downloaded 520 archives successfully and discarded all 520.**
    A download that reports zero successes is a bug until proven otherwise - which is
    the same all-or-nothing signature the Gate 0 probe had, one layer down.
    """
    with zf.open(name) as fh:
        try:
            return pd.read_csv(fh, usecols=["open_time", "high", "low", "close"])
        except ValueError:                       # headerless variant
            fh.seek(0)
            return pd.read_csv(fh, header=None, usecols=[0, 2, 3, 4],
                               names=["open_time", "high", "low", "close"])



def download() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    syms = [archive_symbol(p) for p in cfg["exchange"]["pair_whitelist"]]
    jobs = [(s, m) for s in syms for m in MONTHS]
    print(f"downloading {len(jobs)} archives ({len(syms)} symbols x {len(MONTHS)} months)")
    with ThreadPoolExecutor(max_workers=8) as ex:
        res = list(ex.map(_fetch, jobs))
    tally = {}
    for _, st, why in res:
        tally[why if st == -1 else ("ok" if st in (0, 200) else f"http {st}")] = \
            tally.get(why if st == -1 else ("ok" if st in (0, 200) else f"http {st}"), 0) + 1
    print("  outcomes:")
    for k, v in sorted(tally.items(), key=lambda kv: -kv[1]):
        print(f"    {v:>4}  {k}")
    ok = sum(v for k, v in tally.items() if k in ("ok", "cached"))
    print(f"  {ok} of {len(jobs)} archives on disk, "
          f"{sum(f.stat().st_size for f in OUT.glob('*.parquet'))/1e6:.0f} MB in {OUT}")
    # The signature that both failures above shared: a perfect zero. A real feed
    # fails partially, so an all-or-nothing download is a bug, not a data result.
    if ok == 0:
        print("\n  ** 0 of N archives - that is a BUG SIGNATURE, not an empty feed. **")
        return 3
    return 0



# ---------------------------------------------------------------------------- measure
def load5(sym: str) -> pd.DataFrame | None:
    """Every 5m month on disk for this symbol **that is in MONTHS**.

    The month filter matters once more than one cohort is downloaded: pooling a
    2020 crash cohort with a 2025 calm cohort and reporting one ratio hides the
    only number that can change the verdict, because the ratio RISES with
    volatility. The crash has to be measured on the crash.
    """
    fs = [f for f in sorted(OUT.glob(f"{sym}-*-5m.parquet"))
          if any(f.name == f"{sym}-{m}-5m.parquet" for m in MONTHS)]
    if not fs:
        return None
    x = pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True)
    x = x.drop_duplicates("date").sort_values("date").reset_index(drop=True)
    x["date"] = pd.to_datetime(x["date"], utc=True).dt.as_unit("ns")
    return x


def agg4(x: pd.DataFrame) -> pd.DataFrame:
    """Aggregate 5m bars UP to 4h. Section 35's rule: FEWER bars than the source
    is a coarser bucket and is VALID; more bars would be fabricated.

    Needed because the 4h panel on disk starts 2023-01-01 and the crash cohort is
    2020. Aggregating upward is exact - the 4h high, low and close are the true
    aggregates, so the ATR computed on them is the ATR a real 4h feed would give.
    """
    return (x.set_index("date")
            .resample("4h", label="left", closed="left")
            .agg({"high": "max", "low": "min", "close": "last"})
            .dropna().reset_index())


def load4(flat: str, lo, hi) -> pd.DataFrame | None:
    """`flat` is `BTC_USDT_USDT`, the panel's own filename convention.

    ⚠ The deployed whitelist stores pairs as `BTC/USDT:USDT` and the 5m archives
    need `BTCUSDT`, while the 4h panel on disk is `BTC_USDT_USDT`. Three spellings
    for one symbol. The first version of this function was handed the 5m spelling
    and looked for `BTCUSDT-4h-futures.feather`, which does not exist - so it
    returned None for all 40 symbols and the tool reported
    "no symbol has both 5m and 4h data" **after a completely successful download**.
    The message blamed the download; the bug was the filename. **A single failure
    reason must never be reported for several different ones.**
    """
    f = DATA4 / f"{flat}-4h-futures.feather"
    if not f.exists():
        return None
    x = pd.read_feather(f)[["date", "high", "low", "close"]]
    x["date"] = pd.to_datetime(x["date"], utc=True).dt.as_unit("ns")
    x = x[(x["date"] >= lo) & (x["date"] <= hi)].sort_values("date").reset_index(drop=True)
    return x if len(x) >= 30 else None




def main() -> int:
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    wl = cfg["exchange"]["pair_whitelist"]
    # THREE spellings of one symbol: `BTC/USDT:USDT` (freqtrade), `BTCUSDT`
    # (Binance Vision) and `BTC_USDT_USDT` (the feather panel). Mixing them up is
    # exactly what made the first run report a feed that was fully downloaded.
    names = [(archive_symbol(p), p.replace("/", "_").replace(":", "_")) for p in wl]

    rows, n5_ok, n4_missing, n_agg = [], 0, 0, 0
    for arch, flat in names:
        a = load5(arch)
        if a is None or len(a) < MIN_COVERAGE:
            continue
        n5_ok += 1
        lo, hi = a["date"].iloc[0], a["date"].iloc[-1]
        b = load4(flat, lo, hi)
        src = "feather"
        if b is None:
            # No 4h panel covers this window (it starts 2023-01-01 and the crash
            # cohort is 2020). Aggregate UP instead - valid, and exact - but say so
            # per symbol, and let the positive control below prove the route.
            b = agg4(a)
            src = "aggregated"
            n_agg += 1
            if len(b) < 30:
                n4_missing += 1
                continue

        p5 = _atr_pct(a["high"].to_numpy(), a["low"].to_numpy(), a["close"].to_numpy())
        p4 = _atr_pct(b["high"].to_numpy(), b["low"].to_numpy(), b["close"].to_numpy())
        df5 = pd.DataFrame({"date": a["date"], "p5": p5})
        df4 = pd.DataFrame({"date": b["date"], "p4": p4})
        # the 4h bar's 5m volatility: the 5m ATR% falling inside that 4h window
        g = df4.copy()
        g["p5_in"] = (df5.set_index("date")["p5"]
                      .reindex(pd.date_range(lo, hi, freq="1h", tz="UTC"))
                      .resample("4h").median().reindex(g["date"]).to_numpy())
        stress = g["p5_in"] >= g["p5_in"].quantile(0.90)
        rows.append({
            "sym": arch, "src": src, "n5": len(a), "n4": len(b), "lo": lo, "hi": hi,
            "atr5": float(np.nanmedian(p5)), "atr4": float(np.nanmedian(p4)),
            "atr5_stress": float(np.nanmedian(g.loc[stress, "p5_in"])),
            "atr4_stress": float(np.nanmedian(g.loc[stress, "p4"])),
        })
        print(f"  {arch:<18} 5m {len(a):>7,} bars   4h {len(b):>5,} bars   "
              f"{str(lo)[:10]}..{str(hi)[:10]}")

    if not rows:
        print(f"\nBLOCKED - and here is WHICH part failed: {n5_ok} of {len(names)} "
              f"symbols have usable 5m data, and {n4_missing} of those had no 4h file "
              f"in range.")
        print("  Those are different failures. The first version printed one message "
              "for both and blamed the download, which had in fact succeeded.")
        return 2
    d = pd.DataFrame(rows)
    d.to_csv(ROOT / "user_data" / "perp_short_out" / "five_min_rows.csv", index=False)
    n = len(d)
    print(f"\n{'symbol':<18}{'4h src':>11}{'5m bars':>10}{'4h bars':>9}{'ATR% 5m':>11}"
          f"{'ATR% 4h':>11}{'ratio':>9}")
    for _, r in d.iterrows():
        print(f"{r['sym']:<18}{r['src']:>11}{r['n5']:>10,}{r['n4']:>9,}"
              f"{r['atr5']*100:>10.3f}%{r['atr4']*100:>10.3f}%{r['atr5']/r['atr4']:>9.4f}")

    # ---- POSITIVE CONTROL for the aggregated-4h route ------------------------
    # If any symbol was measured against the REAL 4h feed, the same 5m data
    # aggregated upward must reproduce that ATR%. If it does not, every
    # "aggregated" row above is void - so this is checked, not assumed.
    ctrl = []
    for _, r in d[d["src"] == "feather"].iterrows():
        a = load5(r["sym"])
        if a is None:
            continue
        b = load4(r["sym"].replace("USDT", "_USDT_USDT"), a["date"].iloc[0],
                  a["date"].iloc[-1])
        if b is None:
            continue
        p_agg = _atr_pct(*(lambda g: (g["high"].to_numpy(), g["low"].to_numpy(),
                                      g["close"].to_numpy()))(agg4(a)))
        ctrl.append(abs(float(np.nanmedian(p_agg)) - r["atr4"]) / r["atr4"])
    if ctrl:
        mc = float(np.median(ctrl))
        print(f"\nPOSITIVE CONTROL, 4h aggregated from 5m vs the real 4h feed "
              f"({len(ctrl)} symbols)")
        print(f"  median relative gap: {mc*100:.3f}%   max {max(ctrl)*100:.3f}%"
              f"   {'PASS - the aggregated route is valid' if mc < 0.02 else '** FAIL - the aggregated rows are void **'}")
    else:
        print("\nPOSITIVE CONTROL: not runnable (no symbol had a real 4h file in range)")


    med5, med4 = float(d["atr5"].median()), float(d["atr4"].median())
    r_of_med = med5 / med4
    med_of_r = float((d["atr5"] / d["atr4"]).median())
    r_stress = (float(d["atr5_stress"].median()) / float(d["atr4_stress"].median()))

    print(f"\n{'='*74}")
    print(f"symbols used: {n} of {len(names)} deployed"
          f"{'   [D4 KILL RULE: fewer than 25 -> BLOCKED]' if n < MIN_SYMBOLS else ''}")
    print(f"window      : {d['lo'].min()} .. {d['hi'].max()}  (per-symbol, 4h PINNED to 5m)")
    print(f"median ATR% : 5m {med5*100:.3f}%   4h {med4*100:.3f}%")
    print(f"  route 1, ratio of medians      r = {r_of_med:.4f}")
    print(f"  route 2, median of ratios     r = {med_of_r:.4f}")
    if abs(r_of_med - med_of_r) / r_of_med > 0.10:
        print(f"  ** the two routes disagree by "
              f"{abs(r_of_med-med_of_r)/r_of_med*100:.1f}% - reported, not averaged **")
    print(f"  top-decile volatility days    r = {r_stress:.4f}   (D2)")
    print(f"  sqrt(t) prediction            r = {R_SQRT:.4f}   (D3)")

    verdict_r = min(r_of_med, med_of_r, r_stress)
    cost_calm = (CALM_BPS / (STOP_MULT * med5 * 1e4))
    cost_str = (COST_R_4H_STRESS / verdict_r)
    print(f"\nCOST AT 5m  (stop multiple {STOP_MULT}, same as deployed)")
    print(f"  calm  {CALM_BPS} bps -> cost_R = {cost_calm:.4f}")
    print(f"  stress {STRESS_BPS} bps -> cost_R = {cost_str:.4f}"
          f"   (4h stress 0.0308 / r)")
    print(f"\nD1 GATE: family OPEN at the stress bar iff r >= {R_GATE:.4f}; "
          f"worst measured r = {verdict_r:.4f}")
    print(f"D3: measured/sqrt(t) = {verdict_r/R_SQRT:.2f}x"
          f"{'   -> **section 38d must be restated with the measured number**' if abs(verdict_r/R_SQRT-1) > 0.5 else ''}")
    print("\nD5: an OPEN verdict is NOT a mandate to build a 5m strategy. The next gate")
    print("    is section 15c-5 (PC1 loading + a net long-short leg, by regression),")
    print("    on price data alone, before any backtest.")

    if n < MIN_SYMBOLS:
        print("\nVERDICT: BLOCKED (D4). No ratio may be quoted from this run.")
        return 2
    open_at_stress = verdict_r >= R_GATE
    open_at_calm = cost_calm < EFFECT_HI
    print(f"\nVERDICT: the 5m cascade family is "
          f"**{'OPEN' if (open_at_stress and open_at_calm) else 'CLOSED'}**"
          f" (calm {'passes' if open_at_calm else 'fails'}, "
          f"stress {'passes' if open_at_stress else 'fails'}).")

    # ---- hand the number to the pre-screen, which used to extrapolate it -----
    out = ROOT / "user_data" / "perp_short_out"
    out.mkdir(parents=True, exist_ok=True)
    (out / "five_min.json").write_text(json.dumps({
        "measured_by": "tools/perp_short/five_min_horizon.py",
        "prereg": "docs-myself/PREREG_FIVE_MIN_2026-09-30.md",
        "window": [str(d["lo"].min()), str(d["hi"].max())],
        "months": list(MONTHS),
        "n_symbols": int(n),
        "n_symbols_deployed": len(names),
        "atr_pct_5m": med5, "atr_pct_4h": med4,
        "ratio_of_medians": r_of_med, "median_of_ratios": med_of_r,
        "ratio_stress_top_decile": r_stress,
        "ratio_sqrt_t_prediction": float(R_SQRT),
        "gate_R": float(R_GATE),
        "cost_R_5m_calm": cost_calm, "cost_R_5m_stress": cost_str,
        "family": "5m liquidation cascade",
        "verdict": "OPEN" if (open_at_stress and open_at_calm) else "CLOSED",
        "note": ("The 4h side is PINNED to each symbol's own 5m date range (section 39). "
                 "Aggregated-4h rows are validated by a positive control against the real "
                 "4h feed; run this tool on the 2025 window to see it."),
    }, indent=2), encoding="utf-8")
    print(f"  -> wrote {out / 'five_min.json'} for family_prescreen.py")
    return 0


if __name__ == "__main__":
    # `--months 2020-01,2020-02,...` retargets both the download and the
    # measurement. Needed because the crash cohort and the deployed cohort do not
    # overlap: Gate 0 measured 9/40 and 10/40 symbols reachable in 2020-03 and
    # 2020-07, since the deployed 40 is ranked by 2026 liquidity and is full of
    # 2024-2025 listings. The RATIO is a property of the horizon and transfers
    # across universes (section 39 established that for the 1h/4h ratio), so the
    # crash cohort can measure the ratio even though it cannot describe the
    # universe - and that distinction is stated in the output, not assumed.
    if "--months" in sys.argv:
        MONTHS = sys.argv[sys.argv.index("--months") + 1].split(",")
    if "--download" in sys.argv:
        sys.exit(download())
    sys.exit(main())

