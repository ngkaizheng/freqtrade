"""
E#9 -- pre-registration: does a FAST exit rule rescue the drawdown, and does
leverage on top of it survive?

THE QUESTION BEING ASKED
------------------------
"If I lever up and put a stop loss on, I don't get liquidated. After all you
need a strategy."

That is correct, and it identifies the actual defect in E#7. E#7's exit rule
had a 126-day lookback: by the time it went to cash the drawdown had already
happened (2022 ratio 0.96x, i.e. it lost what buy-and-hold lost). **The missing
piece is EXIT SPEED, not leverage.**

THE TRAP, STATED BEFORE ANYTHING IS RUN
----------------------------------------
This basket's daily volatility is about 4% (annualised 62%, p10 32%, p90 90%).
A 10x position with a -10% stop is being stopped out at roughly 2.5 sigma. In
crypto that happens often, and it tends to happen immediately before the next
rally. **A tight stop plus high leverage is a well-known way to lose money
steadily, and it must be shown rather than assumed.**

So the experiment is not "add a stop and lever up". It is: measure whether the
stop fires on information or on noise, and only then ask what leverage the
surviving edge supports.

------------------------------------------------------------------------------
PART A -- THE DIAGNOSTIC, WHICH MUST COME FIRST
------------------------------------------------------------------------------
For each stop level in {10%, 15%, 20%, 30%} measured on the unlevered
equal-weight basket:

  * how many times it fires
  * the basket's return over the FOLLOWING 20 trading days after each fire
  * the same for a random-day placebo at the same frequency

If the post-stop return is not reliably negative, the stop is noise and no
amount of leverage makes it a strategy. **Part A is a gate on Part B, not a
formality.**

------------------------------------------------------------------------------
PART B -- THE STRATEGY, RUN ONLY IF PART A PASSES
------------------------------------------------------------------------------
Base          equal-weight long basket, the 50 most liquid perpetuals.
Exit          position goes to CASH when the basket falls `stop` from its
              running high since entry (a trailing stop on the position, not on
              the price level).
Re-entry      re-enter after `cooldown` trading days. Cooldowns {5, 20}.
Leverage      1x, 2x, 3x, 5x, 10x, 20x. ALL REPORTED, none selected.
Liquidation   modelled on the DAILY levered path at 1/L, as in E#8.
Cost          measured 13.6 bps round trip, charged on EVERY exit and re-entry.
              A stop-and-re-enter loop is a turnover machine and that cost is
              the whole point of the measurement.
Benchmark     buy-and-hold, same universe, same cost, unlevered.

------------------------------------------------------------------------------
GATES -- pre-registered, in order
------------------------------------------------------------------------------
  A1  the post-stop 20-day return is reliably negative (t <= -1.645 one-sided
      on the trigger-conditioned sample)
  A2  it is MORE negative than the same-frequency placebo (t <= -1.645 on the
      difference)
  B1  a surviving configuration has CAGR > buy-and-hold
  B2  ... with max drawdown materially smaller (at least 25% smaller)
  B3  ... and it is NOT liquidated
  B4  Sharpe > 0.75   (the level E#8's clean result did not reach, 0.585)

------------------------------------------------------------------------------
THE RUNNING MULTIPLE-TESTING EXPOSURE -- stated plainly
------------------------------------------------------------------------------
This is not a fresh panel. E#3, E#4, E#5, E#6, E#7 and E#8 have all been run on
the same 200-symbol download, on overlapping universes, and E#8's "trend" base
was itself a post-hoc variant of E#7's. **That is a substantial search, and the
D5-6 group of cells below is not independent of the E#6-E#8 result.**

The consequence is stated in advance: **nothing in this file is a discovery.**
Whatever passes here is a candidate for a forward test on the forward data
already being collected, and that forward test is the only thing that settles
it. A backtest result on this panel, after this many looks at it, is a
hypothesis.

------------------------------------------------------------------------------
FORBIDDEN
------------------------------------------------------------------------------
  adding a stop level, cooldown or leverage after seeing this run
  reporting B if A failed
  reporting a liquidated configuration as low-risk
  quoting a Sharpe without the drawdown beside it
  treating the E#8 "trend" base as pre-registered -- it is not
"""
