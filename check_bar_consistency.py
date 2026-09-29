"""Cross-check: do Binance's native 1h bars equal the aggregation of its 5m bars?

The study uses NATIVE 1h/4h klines rather than resampling. That was a
deliberate choice (the exchange's own aggregation, not mine), but it was
assumed correct rather than verified. If the two disagree, every 4h result in
phases 2-4 is built on a different bar series than the 5m study used.

This is the kind of check that has to be run, not reasoned about.
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from shark_hunter.data import loader

PAIRS = [("5m", "1h", 12), ("1h", "4h", 4)]


def main() -> int:
    failures = 0
    for base_tf, target_tf, per in PAIRS:
        for sym in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
            b = loader.load_klines(sym, base_tf)
            t = loader.load_klines(sym, target_tf)
            agg = (b.resample(target_tf)
                   .agg({"open": "first", "high": "max", "low": "min",
                         "close": "last", "volume": "sum"})
                   .dropna())
            j = agg.join(t, how="inner", rsuffix="_native")
            print(f"\n=== {sym}  {base_tf} -> {target_tf}  "
                  f"({len(j)} overlapping bars) ===")
            for col in ("open", "high", "low", "close", "volume"):
                a, n = j[col].to_numpy(), j[f"{col}_native"].to_numpy()
                rel = np.abs(a - n) / np.maximum(np.abs(n), 1e-12)
                bad = int((rel > 1e-6).sum())
                failures += bad
                print(f"  {col:<7} max rel diff {rel.max():.3e}   "
                      f"bars differing >1e-6: {bad}")
            # Volume is the sensitive one: a different bucket boundary or a
            # dropped sub-bar shows up here first.
            v = np.abs(j["volume"].to_numpy() - j["volume_native"].to_numpy())
            v = v / np.maximum(j["volume_native"].to_numpy(), 1e-12)
            worst = int(np.argmax(v))
            if v[worst] > 1e-6:
                print(f"  worst volume bar: {j.index[worst]} "
                      f"agg={j['volume'].iloc[worst]:.4f} "
                      f"native={j['volume_native'].iloc[worst]:.4f}")
    print(f"\nTOTAL mismatching values: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
