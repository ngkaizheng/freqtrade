"""Locate the exact bars where native higher-timeframe klines disagree with the
aggregation of the lower-timeframe ones.

28 mismatching values out of ~1.1M is 0.0025%, so the study's conclusions are
almost certainly unaffected.  But "almost certainly" is not a number anyone
should ship, and identical deviations across two symbols suggest a single
systematic event worth naming.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from shark_hunter.data import loader

ROWS = []


def compare(sym: str, base_tf: str, target_tf: str) -> None:
    b = loader.load_klines(sym, base_tf)
    t = loader.load_klines(sym, target_tf)
    agg = (b.resample(target_tf)
           .agg({"open": "first", "high": "max", "low": "min",
                 "close": "last", "volume": "sum"})
           .dropna())
    j = agg.join(t, how="inner", rsuffix="_native")
    for col in ("open", "high", "low", "close", "volume"):
        rel = (j[col] - j[f"{col}_native"]).abs() / j[f"{col}_native"].abs().clip(lower=1e-12)
        bad = j.index[rel > 1e-6]
        for ts in bad:
            ROWS.append({
                "symbol": sym, "pair": f"{base_tf}->{target_tf}", "ts": ts,
                "field": col,
                "aggregated": float(j.loc[ts, col]),
                "native": float(j.loc[ts, f"{col}_native"]),
                "rel_diff": float(rel.loc[ts]),
            })


def main() -> int:
    for base_tf, target_tf in (("5m", "1h"), ("1h", "4h")):
        for sym in ("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
                    "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT"):
            compare(sym, base_tf, target_tf)

    df = pd.DataFrame(ROWS).sort_values(["ts", "symbol"])
    print(f"total mismatches: {len(df)}\n")
    if df.empty:
        return 0
    print("--- distinct timestamps ---")
    for ts, grp in df.groupby("ts"):
        print(f"  {ts}  {len(grp)} values across "
              f"{grp['symbol'].nunique()} symbols, fields={sorted(grp['field'].unique())}")
    print("\n--- full detail (first 40) ---")
    print(df.head(40).to_string(index=False))

    # How much total volume is affected, relative to the whole sample?
    print("\n--- materiality ---")
    for ts, grp in df.groupby("ts"):
        for _, r in grp[grp["field"] == "volume"].iterrows():
            base = loader.load_klines(r["symbol"], r["pair"].split("->")[0])
            total = base["volume"].sum()
            affected = abs(r["native"] - r["aggregated"])
            print(f"  {r['ts']} {r['symbol']}: affected volume {affected:,.0f} "
                  f"= {affected / total * 1e6:.3f} ppm of the sample's total volume")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
