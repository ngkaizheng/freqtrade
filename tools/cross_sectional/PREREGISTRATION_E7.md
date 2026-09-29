"""
E#7 -- pre-registration: TIME-SERIES momentum at its canonical horizon, NET LONG.

WHY THIS EXPERIMENT EXISTS
--------------------------
The stated objective is "make money in a bull market". E#6 established why the
cross-sectional line cannot serve that: a dollar-neutral long-short book
captured 0.39 of the upside in +105.7% years and amplified 1.13 of the
downside in -12.2% years. Its payoff shape is structurally wrong for the
goal, independent of whether the signal is any good.

Serving the goal requires a NET LONG position whose edge is the market's
DIRECTION, not dispersion. The canonical construction for that is time-series
momentum -- Moskowitz, Ooi & Pedersen, "Time Series Momentum", JFE 104(2),
2012, 58 futures, formation ~12 months with a 1-month skip, held 1-12 months.

THE GAP THIS FILLS
------------------
Every backtest in this repository has been at 5m, 1h or 4h. Daily, weekly and
monthly have never been run. The project's own notes record the reason:
"classic time-series momentum spans 1-12 months, so the prior for a 4h edge is
lower". It knew the horizon and never tested it.

Data: 200 USD-M perpetuals, daily bars, 2020-01 -> 2026-08, built by
tools/universe/build_universe.py.

------------------------------------------------------------------------------
PRE-REGISTERED SPECIFICATION -- fixed before any result
------------------------------------------------------------------------------
Universe      top 50 USD-M perpetuals by MEDIAN DAILY QUOTE VOLUME. Fixed by
              COST, not by signal (measure_cost.py: these names have the lowest
              round trip) and by the fact that they are the names that move in a
              market-wide rally. Symbols with a single-day return below -90% are
              removed from the DATA before the test, not afterwards (G7).

Signal        time-series momentum: sign of the symbol's own trailing
              L-calendar-day return. NO cross-sectional ranking, no volume
              feature, no cross-asset input. This is the plainest possible
              version of the effect and it is registered as such.

Lookback      L in {63, 126, 252} trading days (3, 6, 12 months).
              PRIMARY is fixed in advance at **126 days (6 months)**.
              All three are reported; the family correction is applied across
              the three. Selecting the winner afterwards is forbidden.

Skip          21 trading days after the signal forms, per the canonical
              construction, so the position is not taken on the return it is
              trading on. This is a causal requirement, not a tuning knob.

Position      PRIMARY: long-only when the signal is positive, cash when
              negative. This is the structure that serves the stated objective.
              SECONDARY, reported alongside: long/short (flip to short when the
              signal is negative), because that is the canonical MOP form and
              it bounds what the long/cash version is giving up.

Rebalance     monthly, on the last trading day of each calendar month.

Cost          MEASURED book cost from measure_cost.py, reported as the frontier
              over $10k-$1M per name, plus 5 bps per side VIP0 taker.
              Headline case: $10,000 per name, 50 names = $500,000 book,
              all-in 13.6 bps (3.6 mean book + 10 fee).
              With a monthly rebalance and a 6-month lookback, turnover is
              expected to be LOW; that is the point of this experiment and it
              is not assumed -- it is measured.

Causality     signal formed at the close of the skip window, position held from
              then to the next rebalance. Truncation assertion before any number.

------------------------------------------------------------------------------
WHAT IS ACTUALLY BEING TESTED
------------------------------------------------------------------------------
The claim under test is NOT "momentum works". It is:

  "There is a net-long crypto trend rule that captures a large share of the
   upside in a market-wide rally AND reduces the drawdown in a bear, after
   measured costs."

------------------------------------------------------------------------------
GATES -- pre-registered
------------------------------------------------------------------------------
  G1  net CAGR > 0 after measured cost
  G2  |t| >= 2.0 on the dependence-adjusted statistic of monthly returns
  G3  annualised net Sharpe >= 0.75        (below the 0.95 cross-sectional bar,
      because a net-long book takes market risk and is judged against a
      different benchmark -- stated here so it cannot be moved later)
  G4  *** THE CENTRAL GATE ***
      captures >= 50% of buy-and-hold's return in the two large up years
      (2023, 2024) AND loses no more than buy-and-hold in 2022
  G5  max drawdown materially smaller than buy-and-hold on the same universe
  G6  no single symbol contributes more than 35% of total profit
  G7  no rebased/dead names in the traded book

------------------------------------------------------------------------------
THE PRIOR, STATED HONESTLY BEFORE THE RESULT
------------------------------------------------------------------------------
This is the best-supported effect available to the project, and it is still not
a sure thing:
  + Moskowitz, Ooi & Pedersen (JFE 2012) is a canonical, heavily replicated
    result across 58 futures.
  + Liu & Tsyvinski (RFS 2021) find crypto momentum real at weekly-to-monthly
    frequency.
  - Liu, Tsyvinski & Wu (JF 2022) find it is a PRICED factor, so part of it is
    compensation rather than alpha.
  - McLean & Pontiff: 58% post-publication decline overall, and greater for
    predictors with higher in-sample returns.
  - The adversarial review of this project found that in Fieberg et al. (JFQA
    2025), plain cross-sectional momentum is significantly positive in only
    49% of 55,296 design specifications. Plain momentum is the MODAL outcome,
    not a reliable one.
  - The sample here is 6.6 years containing one full cycle. A 6-year sample of
    a 1-12 month effect contains roughly 12-18 independent holding periods.
    That is enough to detect a large effect and not enough to characterise a
    small one.

Expectation: either a real and large effect that clears the gates, or a
decayed one. Do not report the intermediate case as a success.

------------------------------------------------------------------------------
FORBIDDEN
------------------------------------------------------------------------------
  choosing the lookback after seeing results
  switching between long/cash and long/short after seeing results
  reporting an IC instead of the portfolio return
  quoting a buy-and-hold comparison from a different universe
  describing a result that captures little upside as "trend following works"
"""
