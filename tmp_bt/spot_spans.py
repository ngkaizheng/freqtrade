import glob
import os

import pandas as pd

pats = [
    'user_data/data/bitstamp/*-1d.feather',
    'user_data/data/binance/*-1d.feather',
    'user_data/data/okx/*.feather',
]
for pat in pats:
    for p in sorted(glob.glob(pat)):
        d = pd.read_feather(p)
        t = pd.to_datetime(d.iloc[:, 0])
        if t.dt.tz is not None:
            t = t.dt.tz_convert(None)
        yrs = (t.iloc[-1] - t.iloc[0]).days / 365.25
        print('{:32} {:10} -> {:10} {:>6,} bars {:>5.1f}y'.format(
            os.path.basename(p), str(t.iloc[0])[:10], str(t.iloc[-1])[:10], len(d), yrs))
