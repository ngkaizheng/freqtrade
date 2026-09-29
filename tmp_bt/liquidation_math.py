"""What leverage actually does: liquidation probability, measured on real data.

The user wants short-term leveraged trading to grow capital fast. Leverage does
not create edge -- it multiplies whatever edge exists, and with NO edge the
multiplied quantity is fees plus variance. Worse, it adds an ABSORBING failure
mode: liquidation (ruin), from which there is no recovery.

This script measures, on real BTC USDT-perp 5m data, the probability that a
leveraged position is liquidated before the holding period ends.

Method
------
Entry at each bar's close. Over the next H bars, take the worst adverse
excursion (MAE) for a long (lowest low) and for a short (highest high).
Isolated-margin liquidation is approximated at a 1/L adverse move.

This is an OPTIMISTIC approximation: it ignores maintenance margin, funding
and fees, all of which make liquidation come SOONER. The real numbers are worse.
"""
import numpy as np
import pandas as pd

PATH = 'user_data/data/binance/futures/BTC_USDT_USDT-5m-futures.feather'

d = pd.read_feather(PATH)
close = d['close'].to_numpy(dtype=float)
high = d['high'].to_numpy(dtype=float)
low = d['low'].to_numpy(dtype=float)
n = len(close)

print('BTC/USDT:USDT 5m  bars={:,}  {} -> {}'.format(
    n, str(d.iloc[0, 0])[:16], str(d.iloc[-1, 0])[:16]))
print()

HOLD = {'1h': 12, '4h': 48, '24h': 288, '7d': 2016}
LEV = [2, 3, 5, 10, 20, 50, 100]


def forward_extreme(arr, h):
    """Min (for lows) / max (for highs) over the NEXT h bars, aligned to entry."""
    s = pd.Series(arr)
    fwd = s[::-1].rolling(h, min_periods=1).min()[::-1].shift(-1)
    return fwd.to_numpy()


print('=== P(LIQUIDATION) for a LONG at isolated margin, entry at close ===')
print('(optimistic: ignores maintenance margin, funding, fees)')
print()
hdr = '{:>6}'.format('hold') + ''.join('{:>9}'.format('{}x'.format(l)) for l in LEV)
print(hdr)
print('-' * len(hdr))
for name, h in HOLD.items():
    fmin = forward_extreme(low, h)
    mae = (close - fmin) / close          # worst adverse move within the hold
    row = '{:>6}'.format(name)
    for L in LEV:
        p = np.nanmean(mae >= 1.0 / L) * 100
        row += '{:>8.1f}%'.format(p)
    print(row)

print()
print('=== P(LIQUIDATION) for a SHORT at isolated margin ===')
print()
print(hdr)
print('-' * len(hdr))
for name, h in HOLD.items():
    fmax = pd.Series(high)[::-1].rolling(h, min_periods=1).max()[::-1].shift(-1).to_numpy()
    mae = (fmax - close) / close
    row = '{:>6}'.format(name)
    for L in LEV:
        p = np.nanmean(mae >= 1.0 / L) * 100
        row += '{:>8.1f}%'.format(p)
    print(row)

print()
print('=== how often does BTC move that far IN ONE DAY? ===')
print()
daily = pd.Series(close, index=pd.to_datetime(d.iloc[:, 0])).resample('1D').last().dropna()
dr = daily.pct_change().dropna().abs()
for L in LEV:
    thr = 1.0 / L
    print('  {:>4}x needs a {:>5.1f}% move to liquidate  ->  '
          '{:>5.1f}% of all days exceed it'.format(L, thr * 100, (dr >= thr).mean() * 100))
