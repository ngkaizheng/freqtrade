"""Power check: can the available data conclude anything about a trend/vol strategy?

Per AGENTS.md §1a, an experiment must be checked for whether it CAN conclude
before it is proposed. Per Lo (2002) and this repo's FINAL-DECISION.md:

    SE(annualised Sharpe) ~= 1 / sqrt(YEARS)

independent of sampling frequency. Only calendar years buy statistical power.
Minimum Sharpe detectable at t >= 2 is therefore 2 * SE.
"""
import glob
import os

import numpy as np
import pandas as pd

FILES = sorted(glob.glob('user_data/data/binance/futures/*-1d-futures.feather'))


def load():
    out = {}
    for p in FILES:
        d = pd.read_feather(p)
        t = pd.to_datetime(d.iloc[:, 0])
        sym = os.path.basename(p).split('-')[0].replace('_USDT_USDT', '')
        if t.dt.tz is not None:
            t = t.dt.tz_convert(None)
        s = pd.Series(d['close'].to_numpy(), index=t).sort_index()
        s = s[~s.index.duplicated(keep='last')]
        out[sym] = s
    return out


def power(years):
    """Lo (2002): SE of annualised Sharpe from `years` of calendar data."""
    se = 1.0 / np.sqrt(years)
    return se, 2.0 * se


data = load()
print('=== UNIVERSE CHOICES AND THE POWER THEY BUY ===')
print()
print('A portfolio strategy is ONE return series, so the effective sample is')
print('CALENDAR YEARS of common history -- not number of coins x bars.')
print()
hdr = '{:28} {:>4} {:>9} {:>7} {:>7} {:>10}'.format(
    'universe', 'n', 'window_y', 'SE(SR)', 'min_SR', 'verdict')
print(hdr)
print('-' * len(hdr))

choices = []
choices.append(('all 26 (newest binds)', list(data)))
old = [s for s in data if data[s].index[0] <= pd.Timestamp('2020-11-01')]
choices.append(('19 coins listed <=2020-10', old))
top8 = sorted(data, key=lambda s: data[s].index[0])[:8]
choices.append(('8 oldest-listed', top8))
choices.append(('BTC only', ['BTC']))

for name, syms in choices:
    start = max(data[s].index[0] for s in syms)
    end = min(data[s].index[-1] for s in syms)
    years = (end - start).days / 365.25
    se, min_sr = power(years)
    verdict = 'CANNOT' if min_sr > 0.5 else 'marginal'
    print('{:28} {:>4} {:>9.1f} {:>7.2f} {:>7.2f} {:>10}'.format(
        name, len(syms), years, se, min_sr, verdict))

print()
print('Reading: min_SR is the smallest annualised Sharpe that would reach')
print('t=2.0 on this much calendar time. Anything below it is undetectable')
print('regardless of how good the strategy is.')
print()

# --- effective independent bets, repo convention -------------------------
print('=== EFFECTIVE INDEPENDENT BETS (cross-sectional correlation) ===')
print()
allc = pd.DataFrame({s: data[s] for s in data}).dropna()
rets = allc.pct_change().dropna()
corr = rets.corr().to_numpy()
n = corr.shape[0]
# average pairwise correlation -> effective N via the standard formula
off = corr[np.triu_indices(n, 1)]
rho = float(np.mean(off))
n_eff = n / (1.0 + (n - 1) * rho)
print('coins                       :', n)
print('mean pairwise correlation   : {:.3f}'.format(rho))
print('nominal N                   :', n)
print('effective N                 : {:.2f}'.format(n_eff))
print()
print('So 26 coins are worth about {:.1f} independent bets, not 26.'.format(n_eff))
print('Cross-sectional breadth cannot rescue the calendar-time problem:')
print('a long-short book of these coins is still one correlated series.')
