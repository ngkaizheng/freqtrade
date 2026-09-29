"""Buy-and-hold benchmark for BTC/USD (Bitstamp) over the same window."""
import numpy as np
import pandas as pd

d = pd.read_feather('user_data/data/bitstamp/BTC_USD-1d.feather')
t = pd.to_datetime(d.iloc[:, 0])
if t.dt.tz is not None:
    t = t.dt.tz_convert(None)
s = pd.Series(d['close'].to_numpy(), index=t).sort_index()
s = s[~s.index.duplicated(keep='last')]

rets = s.pct_change().dropna()
years = (s.index[-1] - s.index[0]).days / 365.25

cagr = (s.iloc[-1] / s.iloc[0]) ** (1 / years) - 1
sharpe = rets.mean() / rets.std() * np.sqrt(365)
dd = (s / s.cummax() - 1).min()

print('=== BUY & HOLD  BTC/USD Bitstamp ===')
print('window          : {} -> {}'.format(str(s.index[0])[:10], str(s.index[-1])[:10]))
print('years           : {:.1f}'.format(years))
print('CAGR            : {:+.2f}%'.format(cagr * 100))
print('Sharpe (daily)  : {:.3f}'.format(sharpe))
print('max drawdown    : {:.2f}%'.format(dd * 100))
print('SE(SR) Lo 2002  : {:.2f}  -> min detectable SR {:.2f}'.format(
    1 / np.sqrt(years), 2 / np.sqrt(years)))
print()
print('=== per calendar year (buy & hold) ===')
yr = s.resample('YE').last()
prev = s.resample('YE').first()
first_year = s.index[0].year
for (ts, last), (_, fst) in zip(yr.items(), prev.items()):
    y = ts.year
    base = s[s.index.year == y].iloc[0]
    r = (last / base - 1) * 100
    print('{:5}  {:>+9.1f}%'.format(y, r))
