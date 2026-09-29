import pandas as pd, glob, os

rows = []
for p in sorted(glob.glob('user_data/data/binance/futures/*-1d-futures.feather')):
    d = pd.read_feather(p)
    t = pd.to_datetime(d.iloc[:, 0])
    sym = os.path.basename(p).split('-')[0].replace('_USDT_USDT', '')
    yrs = (t.iloc[-1] - t.iloc[0]).days / 365.25
    rows.append((sym, str(t.iloc[0])[:10], str(t.iloc[-1])[:10], len(d), yrs))

rows.sort(key=lambda r: -r[4])
hdr = '{:7} {:11} {:11} {:>6} {:>6}'.format('sym', 'start', 'end', 'bars', 'years')
print(hdr)
print('-' * len(hdr))
for s, a, b, n, y in rows:
    print('{:7} {:11} {:11} {:>6,} {:>6.1f}'.format(s, a, b, n, y))

print()
print('total pairs     :', len(rows))
print('>=3y history    :', sum(1 for r in rows if r[4] >= 3.0))
print('>=5y history    :', sum(1 for r in rows if r[4] >= 5.0))
print('common start    :', max(r[1] for r in rows))
print('common end      :', min(r[2] for r in rows))
