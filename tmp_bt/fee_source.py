"""What fee did freqtrade actually use, and what is the real fee?

freqtrade/optimize/backtesting.py:268 set_fee():
    fees = [exchange.get_fee(symbol=whitelist[0], taker_or_maker=mt) for mt in ("taker","maker")]
    self.fee = max(fee for fee in fees if fee is not None)

i.e. it takes the MAX of taker and maker from ccxt market data.

Binance has SEPARATE schedules for spot and USDT-M futures, and they differ by
roughly 2x. This script prints both so the comparison is grounded, not assumed.
"""
import ccxt

for label, factory, sym in [
    ('SPOT    ', ccxt.binance, 'BTC/USDT'),
    ('FUTURES ', ccxt.binanceusdm, 'BTC/USDT:USDT'),
]:
    try:
        ex = factory()
        m = ex.load_markets()
        mk = m[sym]
        taker = mk.get('taker')
        maker = mk.get('maker')
        use = max(f for f in (taker, maker) if f is not None)
        print('{} {}'.format(label, sym))
        print('    maker = {:.4%}'.format(maker))
        print('    taker = {:.4%}'.format(taker))
        print('    freqtrade would use max = {:.4%}'.format(use))
        print()
    except Exception as e:
        print('{} FAILED: {}: {}'.format(label, type(e).__name__, e))
        print()
