============================================================================================================
EVENT-TRADE EXECUTION COST, Binance USD-M perpetuals (live book)
  2026-09-28T21:12:37+00:00   hold assumption: 30 days
============================================================================================================

  Round trip = walk-the-book cost to enter AND exit the same notional.
  It EXCLUDES taker fees (VIP0 = 5 bps/side = 10 bps round trip, added below)
  and excludes adverse selection while the order works.

symbol      spread   RT@$500 RT@$2,500 RT@$5,000RT@$10,000RT@$50,000  fund8h%  fund30d%   L10x%  BE long%  BE short%
--------------------------------------------------------------------------------------------------------------------
AEROUSDT      1.20       1.5       4.8       7.5      10.7      25.7   0.0117     1.052   10.52     1.228      0.175
ENAUSDT       0.39       0.4       1.9       2.7       4.0      10.9   0.0050     0.450    4.50     0.577      0.127
SEIUSDT       1.29       1.7       5.3       7.6      11.0      22.8   0.0091     0.816    8.16     0.992      0.176
2ZUSDT        1.49       3.8      10.6      18.1      28.4      82.7   0.0050     0.450    4.50     0.732      0.281
KNTQUSDT    ERROR: depth fetch failed: HTTP Error 400: Bad Request
LITUSDT       0.23       3.6       4.1       5.8      10.2      32.8   0.0050     0.450    4.50     0.608      0.158
AVAUSDT       4.16       5.9      17.3      24.7      37.9     120.5   0.0022     0.198    1.98     0.545      0.347
BTCUSDT       0.01       0.0       0.0       0.0       0.0       0.0   0.0036     0.326    3.26     0.426      0.100

  RT = round trip in bps (enter + exit, walk the book, NO fees).
  fund30d% = funding over 30 days as % of NOTIONAL (positive = longs pay).
  L10x%    = the same funding as % of MARGIN at 10x.
  BE = break-even move the price must travel to clear round trip +
       funding + 10 bps VIP0 taker fees, before any edge.

  *** LEVERAGE DOES NOT CHANGE THE BE. Both the move and the funding
      scale linearly with notional, so the ratio is identical at 1x and
      10x. What leverage changes is LIQUIDATION RISK, not economics. ***

  Book depth actually available (ask levels/bid levels consumed):
    AEROUSDT   $500=1/2  $2,500=4/4  $5,000=5/5  $10,000=8/7  $50,000=19/18
               -> LONG candidate - seven-chain launch 2026-10-21 20:00 EDT (primary src)
    ENAUSDT    $500=1/1  $2,500=1/7  $5,000=3/9  $10,000=6/12  $50,000=26/20
               -> SHORT candidate - ~1.5B ENA (~14.3% of float) unlock 2026-10-05
    SEIUSDT    $500=2/1  $2,500=5/2  $5,000=6/4  $10,000=8/6  $50,000=15/10
               -> SHORT candidate - 113.0M SEI (~$5.53M) unlock 10-15 and 11-15
    2ZUSDT     $500=1/3  $2,500=7/5  $5,000=14/7  $10,000=19/10  $50,000=50/42
               -> SHORT candidate - 47.7% of float unlock 2026-10-02
    LITUSDT    $500=10/2  $2,500=10/3  $5,000=10/27  $10,000=28/32  $50,000=140/105
               -> SHORT candidate - weekly unlock 1.28% of float per week
    AVAUSDT    $500=2/2  $2,500=3/4  $5,000=5/5  $10,000=7/10  $50,000=23/27
               -> LONG candidate - monthly buyback, no discrete event date
    BTCUSDT    $500=1/1  $2,500=1/1  $5,000=1/1  $10,000=1/1  $50,000=1/1
               -> reference - the benchmark for what a liquid book looks like