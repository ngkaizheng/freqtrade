"""Fee drag under leverage -- the second half of the short-term-leverage reality.

Key point that is easy to miss: fees are charged on NOTIONAL, not on equity.
So a round trip costs `fee_rate * leverage` in units of YOUR equity. Leverage
multiplies the fee drag exactly as much as it multiplies a gain -- but the gain
is uncertain and the fee is not.

freqtrade reported in this repo's own backtests: "Using fee 0.0500% - worst case
fee from exchange (lowest tier)". Round trip = 0.10% of notional.
"""

FEE_SIDE = 0.0005          # 0.05% per side, from this repo's own backtest logs
ROUND_TRIP = FEE_SIDE * 2  # 0.10% of notional

print('round-trip fee = {:.2f}% of NOTIONAL'.format(ROUND_TRIP * 100))
print()

# turnover scenarios, in round trips per year
scen = [
    ('daily rebalance (365/yr)', 365),
    ('2-day hold (182/yr)', 182),
    ('weekly (52/yr)', 52),
    ('monthly (12/yr)', 12),
]
LEV = [1, 2, 3, 5, 10, 20, 50]

print('=== ANNUAL FEE DRAG AS % OF YOUR EQUITY ===')
print()
hdr = '{:>26}'.format('turnover')
for L in LEV:
    hdr += '{:>9}'.format('{}x'.format(L))
print(hdr)
print('-' * len(hdr))

for name, trips in scen:
    row = '{:>26}'.format(name)
    for L in LEV:
        drag = trips * ROUND_TRIP * L * 100
        row += '{:>8.0f}%'.format(drag)
    print(row)

print()
print('Read the 10x column: a strategy that round-trips once a day pays')
print('{:.0f}% of equity per year in fees ALONE, before any loss.'.format(365 * ROUND_TRIP * 10 * 100))
print('At 20x, {:.0f}%/yr. At 50x, {:.0f}%/yr.'.format(
    365 * ROUND_TRIP * 20 * 100, 365 * ROUND_TRIP * 50 * 100))

print()
print('=== what the strategy must earn JUST TO BREAK EVEN ===')
print()
print('{:>26} {:>14} {:>14} {:>14}'.format('turnover', 'at 3x', 'at 10x', 'at 20x'))
print('-' * 72)
for name, trips in scen:
    print('{:>26} {:>13.1f}% {:>13.1f}% {:>13.1f}%'.format(
        name,
        trips * ROUND_TRIP * 3 * 100,
        trips * ROUND_TRIP * 10 * 100,
        trips * ROUND_TRIP * 20 * 100))
