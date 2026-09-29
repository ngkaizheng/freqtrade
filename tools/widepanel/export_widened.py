"""Export the WIDENED panel (526 symbols) into freqtrade's datadir layout.

Layout rule, which this repo has now paid for twice:
    4h futures   -> <d>/futures/BASE_USDT_USDT-4h-futures.feather
    1h funding   -> <d>/futures/BASE_USDT_USDT-1h-funding_rate.feather
    1h mark      -> <d>/futures/BASE_USDT_USDT-1h-mark.feather
  and `to_feather()` MUST be preceded by `reset_index()`, or the `date` column
  becomes the frame index and freqtrade sees a 5-column file, logs
  "Unexpected column count 5 - expected 6", and CONTINUES on partial data.

Cohort A (the original 104) is re-exported from `shark_data/wide/features` so
all 526 come through one code path and cannot diverge. That is the replication
arm: cohort A must reproduce the delivered book, and a shared exporter is the
only way that check is meaningful.

Run:
    .venv\\Scripts\\python.exe tools\\widepanel\\export_widened.py
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / "user_data" / "data" / "wide526"
FEAT_A = ROOT / "shark_data" / "wide" / "features"
NEW_K = ROOT / "shark_data" / "widened" / "klines_4h"
NEW_F = ROOT / "shark_data" / "widened" / "funding"
TF = "4h"


def to_utc(series: pd.Series) -> pd.Series:
    """Robust timestamp parse for a column that arrives in three shapes.

    This repo has now been bitten by all three:
      * INT epoch ms  (freshly downloaded fundingRate CSVs)
      * STRING, mixed - some rows carry microseconds ('...12:00:00.001000+00:00')
        and some do not, and pandas 3 refuses to infer across them
      * proper tz-aware timestamps (the cohort A funding files)
    `unit=` and `format=` are mutually exclusive in pandas, so the dtype and a
    sample value decide which one is used. Guessing wrong raises, and the raise
    used to kill the whole export after the klines were already written - which
    printed as a clean failure but lost the run.
    """
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_datetime(series, unit="ms", utc=True)
    s = series.astype(str)
    return pd.to_datetime(s, utc=True, format="ISO8601")


def write_one(ex: Path, fname: str, d: pd.DataFrame) -> None:
    d.to_feather(ex / f"{fname}-{TF}-futures.feather")
    m = (d.set_index("date")
           .resample("1h")
           .agg({"open": "last", "high": "last", "low": "last",
                 "close": "last", "volume": "sum"})
           .ffill().dropna(subset=["close"]).reset_index())
    m.to_feather(ex / f"{fname}-1h-mark.feather")


def write_funding(ex: Path, fname: str, tcol: str, rate: str) -> int | None:
    fr = pd.DataFrame({"date": tcol, "funding_rate": rate}).sort_values("date")
    fr = fr.drop_duplicates("date").reset_index(drop=True)
    if fr["funding_rate"].isna().all() or len(fr) == 0:
        return None
    fr.to_feather(ex / f"{fname}-1h-funding_rate.feather")
    return len(fr)


def main() -> int:
    uni = json.loads((ROOT / "shark_data" / "widened" / "universe.json").read_text())
    log = pd.read_csv(ROOT / "shark_data" / "widened" / "download_log.csv")
    ok_syms = set(log[log["ok"]]["symbol"])
    cohort = {u["symbol"]: u["cohort"] for u in uni}

    ex = DEST / "futures"
    if ex.exists():
        shutil.rmtree(ex)
    ex.mkdir(parents=True, exist_ok=True)

    n_a = n_new = 0
    skipped = []
    for sym, co in sorted(cohort.items(), key=lambda kv: (kv[1], kv[0])):
        base = sym[:-4] if sym.endswith("USDT") else sym
        fname = f"{base}_USDT_USDT"
        if co == "A":
            fp = FEAT_A / f"{sym}.parquet"
            if not fp.exists():
                skipped.append((sym, co, "cohort A feature parquet missing"))
                continue
            f = pd.read_parquet(fp)
            d = pd.DataFrame({
                "date": f["open_time"].dt.tz_convert("UTC"),
                "open": f["open"].astype("float32"), "high": f["high"].astype("float32"),
                "low": f["low"].astype("float32"), "close": f["close"].astype("float32"),
                "volume": f["volume"].astype("float32")})
            fpath = ROOT / "shark_data" / "wide" / "funding" / f"{sym}.csv.gz"
            if fpath.exists():
                fd = pd.read_csv(fpath)
                tc = to_utc(fd["calc_time"])
                rc = fd["last_funding_rate"].astype("float64")
            else:
                skipped.append((sym, co, "no funding")); continue
            n_a += 1
        else:
            if sym not in ok_syms:
                skipped.append((sym, co, "not in download log (warmup/404)"))
                continue
            kp = NEW_K / f"{sym}_4h.csv.gz"
            fp = NEW_F / f"{sym}.csv.gz"
            if not kp.exists() or not fp.exists():
                skipped.append((sym, co, "file missing on disk"))
                continue
            k = pd.read_csv(kp)
            d = k[["date", "open", "high", "low", "close", "volume"]].copy()
            d["date"] = to_utc(d["date"])
            fd = pd.read_csv(fp)
            tc = to_utc(fd["calc_time"])
            rc = fd["last_funding_rate"].astype("float64")
            n_new += 1

        write_one(ex, fname, d)
        if write_funding(ex, fname, tc, rc) is None:
            skipped.append((sym, co, "funding empty -> DROPPED (unfunded book)"))
            (ex / f"{fname}-{TF}-futures.feather").unlink(missing_ok=True)
            (ex / f"{fname}-1h-mark.feather").unlink(missing_ok=True)
            if co == "A":
                n_a -= 1
            else:
                n_new -= 1

    print(f"exported cohort A: {n_a}   cohort B-E: {n_new}   total {n_a+n_new}")
    from collections import Counter
    got = Counter()
    for f in ex.glob("*-4h-futures.feather"):
        got[cohort.get(base_of(f), "?")] += 1
    print("exported by cohort    :", dict(sorted(got.items())))
    print(f"\nSKIPPED {len(skipped)} (each recorded, none silent):")
    for s, c, why in skipped[:40]:
        print(f"   {s:<18} {c}  {why}")
    if len(skipped) > 40:
        print(f"   ... and {len(skipped)-40} more, all in download_log.csv")
    return 0


def base_of(f: Path) -> str:
    # 'AAVE_USDT_USDT-4h-futures.feather' -> 'AAVEUSDT'
    stem = f.name.split("-4h-futures")[0]
    return stem[: -len("_USDT_USDT")] if stem.endswith("_USDT_USDT") else stem


if __name__ == "__main__":
    sys.exit(main())
