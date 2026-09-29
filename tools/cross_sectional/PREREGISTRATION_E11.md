"""
E#11 -- the ACTUAL Moskowitz-Ooi-Pedersen construction.

WHY THIS EXPERIMENT EXISTS
--------------------------
E#7 tested "time-series momentum" as LONG/CASH, fixed size, single market, and
found it gave essentially no protection in 2022 (loss ratio 0.96x versus
buy-and-hold). The project's own memory noted the canonical horizon but never
ran it, and the run that did used the wrong construction.

MOP (JFE 104(2), 2012, 1380 citations) is not long/cash:

    1. LONG-SHORT.  Flat is not the alternative to short; short is.
    2. VOLATILITY SCALED.  Each position's return is divided by its own
       realised volatility and multiplied by a target -- the paper's central
       innovation, and the reason it has a leverage effect.
    3. DIVERSIFIED ACROSS TIMEFRAMES.  Positions are formed in each of 1, 2, 3,
       4, 5, 6, 8, 10 and 12 month lookbacks and combined.
    4. Volatility SCALED ACROSS TIMEFRAMES, with the same procedure.

MOP also reports the result this project most conspicuously failed to find:
**"A diversified portfolio of time series momentum strategies ... performs best
during extreme markets."**  E#7 found the opposite. The most likely reason is
that E#7 was not MOP.

The 2026-09-26 literature interim flagged this as "the one place the
literature positively predicts protection and the project found none".

------------------------------------------------------------------------------
PRE-REGISTERED
------------------------------------------------------------------------------
Signal        sign of the asset's own trailing k-month return, k in
              {1, 2, 3, 4, 6, 9, 12} months (21, 42, 63, 84, 126, 189, 252
              trading days). All reported; the aggregate is primary.
Position      LONG if the signal is positive, SHORT if negative. Not
              long/cash. The short leg is 50% of gross exposure, the long 50%.
Vol scaling   each name's daily position return divided by its own 30-day
              realised vol, times a target vol. Targets swept {0.10, 0.15,
              0.20}. Reported as a frontier, none selected.
Aggregate     all lookbacks equally weighted, then a portfolio vol target
              applied to the aggregate -- MOP's second-stage scaling.
Rebalance     the signal is re-evaluated daily; positions are held until the
              signal changes, and each change is a round trip.
Cost          measured 13.6 bps round trip, charged on turnover.
Causality     the signal at t uses prices through t; the position earns t to
              t+1. One-bar decision lag, enforced in code.
Universe      the 50 most liquid perpetuals. MOP's universe is diversified
              futures; this is the crypto analogue and it is a real difference,
              recorded rather than glossed.

------------------------------------------------------------------------------
WHAT WOULD FALSIFY IT
------------------------------------------------------------------------------
MOP's specific prediction: the aggregate should hold up in a down market. On
this sample that means 2022. If a faithful MOP construction still shows a loss
ratio near 1.0x in 2022, then the implementation was not the problem, and the
honest conclusion is that MOP's result does not transfer to crypto perps at this
universe width.

------------------------------------------------------------------------------
MULTIPLE-TESTING EXPOSURE -- stated before the run
------------------------------------------------------------------------------
This is the seventh experiment in the E# series on the same 200-symbol download,
and this file is not a formal pre-registration. **No cell chosen here is a
discovery.** The forward data already being collected is the arbiter.
"""
