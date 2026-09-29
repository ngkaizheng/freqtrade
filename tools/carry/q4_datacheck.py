"""Check Binance 8h -> 1h funding-interval change and the clamp-binding share, on repo data."""
import glob
import os

import numpy as np
import pandas as pd

pd.set_option("display.width", 200)
ROOT = r"E:\FreqTrader\freqtrade\user_data\data\binance_funding"
files = sorted(glob.glob(os.path.join(ROOT, "*-funding.feather")))
print(f"files={len(files)}")

f0 = files[0]
df = pd.read_feather(f0)
print(f"\n=== {os.path.basename(f0)}  shape={df.shape}")
print("columns:", list(df.columns))
print(df.head(3))
print(df.tail(3))

# infer the index
idx = df.index
print("index dtype:", idx.dtype, "unit:", getattr(idx.dtype, "unit", None))
