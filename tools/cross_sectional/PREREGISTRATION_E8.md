"""
E#8 -- pre-registration: volatility targeting, and whether ANY leverage works.

The question behind this experiment
------------------------------------
"If I lever it 10x or 20x, does that fix it?"

No, not by itself, and the arithmetic is worth writing down before running
anything. Leverage multiplies return AND drawdown by the same factor, and an
account is liquidated when the loss reaches roughly 1/L:

    leverage   liquidated after a market move of about
    1x            -100%
    2x             -50%
    3x             -33%
    5x             -20%
    10x            -10%
    20x             -5%

Buy-and-hold on this universe drew down **-79.8%** over 2020-2026. At 10x the
account is gone after a -10% move, which in this sample happens constantly. So
**leverage is not a lever on the return; it is a hard constraint on how much
drawdown the strategy is allowed to have.**

That is why volatility targeting and leverage belong in ONE experiment rather
than two. Volatility targeting is the only mechanism available that reduces the
drawdown WITHOUT requiring a directional prediction -- and E#7 established
that directional prediction is what keeps failing here.

    E#6 cross-sectional momentum   capture 0.39 up / 1.13 down  (wrong shape)
    E#7 time-series momentum       capture 0.15 up / 0.96 in 2022 (no protection)

Neither reduces the bear. Volatility targeting does not try to: it reduces
exposure into high-volatility regimes, where the bear lives.

------------------------------------------------------------------------------
PRE-REGISTERED SPECIFICATION -- fixed before any result
------------------------------------------------------------------------------
Universe      top 50 USD-M perpetuals by median daily quote volume. Survivor
              only, disclosed. Symbols with a single-day return below -90% are
              removed from the DATA first (G7).

Base position equal-weight LONG-ONLY basket. Primary base.
              Secondary base: the E#7 long/cash 126-day time-series trend,
              reported alongside because "trend + vol target + leverage" is the
              classic combination and it would be dishonest to test the overlay
              only on buy-and-hold. The base is fixed in advance; neither is
              chosen after the fact.

Volatility     Realised volatility over a 30-day window, annualised, computed
target          on the EQUAL-WEIGHT BASKET (not per name -- the target applies
               to the portfolio).
               Exposure = target_vol / realised_vol, clipped to [0, 3].
               Targets swept: 0.20, 0.35, 0.50, 0.70. The target that equals
               the unlevered basket's own average volatility is reported so
               the reader can see the no-overlay case.

Leverage       1x, 2x, 3x, 5x, 10x, 20x. Swept, all reported, NONE selected.

Cost           MEASURED book cost at $10,000 per name (3.6 bps mean) plus
               10 bps VIP0 taker per round trip, charged on the TURNOVER the
               volatility overlay actually generates. The overlay is itself a
               source of turnover and it is not free; that has to be priced.

Liquidation     Modelled, not assumed away. A fully-invested account at leverage
                L is liquidated when the cumulative move against it reaches
                1/L. Reported as the FIRST liquidation date, computed on the
                DAILY levered return series, before any compounding. A
                configuration that liquidates is not a low-risk
                configuration, it is a dead one, and it is marked as such.

Rebalance      Daily for the volatility overlay (it must react to vol, and
               monthly would let vol double before the size changes);
               monthly for the trend base. Both costs are charged.

------------------------------------------------------------------------------
THE MEASUREMENT
------------------------------------------------------------------------------
Reported for every (base, vol target, leverage) cell:

  CAGR, max drawdown, Sharpe, and the TORTURE RATIO = CAGR / |max drawdown|,
  which is the only number that compares "more return" against "more risk"
  across leverage levels.

  Plus: whether it survives, and the date it dies if it does not.

------------------------------------------------------------------------------
GATES -- pre-registered
------------------------------------------------------------------------------
  G1  a configuration exists with CAGR strictly greater than unlevered
      buy-and-hold's (+7.90%)
  G2  that configuration's torture ratio strictly greater than
      buy-and-hold's (+7.90 / 79.8 = 0.10)
  G3  that configuration SURVIVES -- no liquidation at any point
  G4  max drawdown no worse than buy-and-hold's -79.8%
  G5  |Newey-West t| >= 2.0 on the monthly return series

------------------------------------------------------------------------------
THE PRIOR, BEFORE THE RESULT
------------------------------------------------------------------------------
- **Leverage does not create an edge.** If the unlevered return is negative, 10x
  of it is more negative and the account is gone first. Nothing in this
  experiment can make a negative Sharpe positive.
- Volatility targeting is a RISK overlay, not a return source. Its realistic
  value here is that crypto volatility is strongly regime-dependent -- the
  2022 drawdown coincided with a volatility regime that a fixed-size long book
  rides straight into.
- The sample is 6.6 years, one cycle. Volatility targeting is a low-turnover,
  slowly-adapting overlay, so the number of effectively independent periods is
  small -- fewer than the monthly count suggests.
- **The prior is that most leverage cells die and the survivors are the
  low-leverage ones.** A grid in which only 1x survives is a legitimate and
  expected result, not a failure of the experiment.

------------------------------------------------------------------------------
FORBIDDEN
------------------------------------------------------------------------------
  selecting a leverage, a vol target, or a base after seeing results
  reporting a liquidated configuration as low-risk
  reporting CAGR without the drawdown and the torture ratio beside it
  describing "10x" as an improvement without the survival check
  reusing a vol target from a prior run
"""
