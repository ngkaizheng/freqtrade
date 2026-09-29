"""Resolve the buy-and-hold numbers directly from the raw price series."""
import numpy as np
import pandas as pd

d = pd.read_feather('user_data/data/bitstamp/BTC_USD-1d.feather')
t = pd.to_datetime(d.iloc[:, 0])
if t.dt.tz is not None:
    t = t.dt.tz_convert(None)
s = pd.Series(d['close'].to_numpy(), index=t).sort_index()
s = s[~s.index.duplicated(keep='last')]

first, last = float(s.iloc[0]), float(s.iloc[-1])
days = (s.index[-1] - s.index[0]).days
years = days / 365.25
ratio = last / first

print('first close     : {:.2f}  ({})'.format(first, str(s.index[0])[:10]))
print('last  close     : {:.2f}  ({})'.format(last, str(s.index[-1])[:10]))
print('days / years    : {} / {:.2f}'.format(days, years))
print('ratio           : {:.1f}x'.format(ratio))
print('total return    : {:,.0f}%'.format((ratio - 1) * 100))
print('CAGR            : {:+.2f}%'.format((ratio ** (1 / years) - 1) * 100))
print()
print('Note: freqtrade reports "Market change" excluding its startup candles.')
print('Sanity: ratio**(1/15.1) must equal 1+CAGR above.')
print('check           : {:+.2f}%'.format((ratio ** (1 / years) - 1) * 100))
