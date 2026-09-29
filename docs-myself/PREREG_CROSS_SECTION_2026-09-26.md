# Pre-registration — cross-sectional momentum on Binance USD-M perpetuals

**Written:** 2026-09-26, **before** the 527-symbol universe finished downloading and
before any cross-sectional result was computed on it.

**Why this document exists.** Four research lines in this project died because a
configuration was chosen after seeing the result. This one is being fixed in
advance so that cannot happen here.

---

## 1. The hypothesis

On a cross-section of liquid crypto perpetuals, a trailing one-week return
ranks assets; the top of the cross-section outperforms the bottom over the
following week, net of transaction costs.

**Mechanism claimed:** slow-moving capital, leverage constraints, and a
tendency for large liquid names to exhibit momentum rather than the
cross-sectional reversal documented for illiquid small coins (Pham et al.,
IRFA 2021, found the cross-section of crypto to reverse on average but
explicitly found the largest and most tradeable coins to exhibit momentum).

**Falsifiable prediction, stated now:** on 2025 data the portfolio's net
annualised Sharpe will be **≥ 0.95** and its net return per rebalance will be
**positive**, and the sign will be **positive in the 2026 final-unseen split**.

## 2. Frozen specification — none of these may change after the data is seen

| item | value | note |
|---|---|---|
| universe | all USD-M perps with **≥ 26 weeks** of continuous history in the panel | listing-age filter; see §4 |
| bars | native 4h from Binance Vision | |
| signal | trailing **42-bar (7-day)** return, computed cross-sectionally | |
| direction | **momentum** (long the top) | the reversal leg is not traded |
| portfolio | long top tercile, short bottom tercile, **dollar-neutral, equal weight** | |
| rebalance | every **42 bars (7 days)** | |
| cost | **20 bps of traded notional per rebalance** = 4 legs × 5 bps taker | no maker assumption, no BNB discount |
| split | develop 2023–2024 · **OOS 2025** · final unseen 2026-01 → 2026-08 | chronological, never shuffled |
| sizing | reported as portfolio return, not compounded over a position book | |

**The direction was chosen from a 9-symbol pilot, where the reversal leg was
uniformly negative and momentum was not.** That is a selection, and it is
counted in §5 rather than hidden.

## 3. Why the cross-section, given that every single-asset line failed

Not for the edge — for the **sample size**. A cross-sectional portfolio
produces essentially independent observations: the 9-symbol pilot measured
lag-1 autocorrelation between −0.11 and +0.05 and an effective sample size
equal to the nominal count to within 1%. Every single-asset rule in this
project had the opposite property, and that is what made them unprovable
rather than merely unprofitable.

## 4. The bias this design cannot escape

`exchangeInfo` returns only **currently-listed** contracts. This is a survivor
universe, and the tokens that squeeze hardest are disproportionately the ones
now absent from it. Nothing corrects that; it is disclosed with every result.

The ≥26-week listing-age filter reduces but does not remove the bias: it
removes the effect of *recent* listings, not the absence of *dead* ones.

## 5. Multiple testing — declared before the run

| stage | configurations |
|---|---:|
| 9-symbol pilot (momentum leg) | 9 (3 lookbacks × 3 rebalance frequencies) |
| 9-symbol pilot (reversal leg, tested and rejected) | 9 |
| earlier 1-bar-return pilot iteration | 6 |
| **total before the 527-name run** | **24** |
| this pre-registered configuration | 1 (no search) |

The reported Sharpe is deflated for a search of **at least 24 configurations**.
If any parameter search is run on the 527-name panel, that count must be
raised here *before* the run and the run repeated from scratch.

## 6. Decision rule, fixed in advance

**PASS** requires **all** of:
1. net annualised Sharpe on **2025 OOS ≥ 0.95**;
2. net return per rebalance **positive** in 2025 OOS;
3. net return per rebalance **positive** in the **2026 final-unseen** split;
4. the sign is **not** driven by a single symbol (report the leave-one-out
   range; a result that disappears when one coin is dropped fails);
5. the gross edge exceeds the 20 bps cost by a margin that survives the
   multiple-testing haircut in §5.

**FAIL** is any other outcome, including "directionally right but below 0.95".
A FAIL is recorded as a FAIL and the line is closed. There is no third
outcome, and a marginal result is not rounded up.

## 7. What would make me distrust a PASS anyway

- A gross edge of a few bps against a 20 bps cost is inside the error bars of
  the cost assumption itself. A PASS on a thin margin is a FAIL.
- If the result is driven by symbols listed late in the sample, the
  listing-age filter has not done its job.
- If removing the 2021-style squeeze regime changes the sign, the result is a
  regime artefact, not an edge.

## 8. Kill criterion

If the OOS net return is negative, **the line is closed permanently** and
recorded as such. The cross-sectional route is the last design with a
structural answer to the sample-size problem, so a failure here ends the
project's search for a tradeable edge, not just this design.

---

# RESULT: FAIL. The line is closed.

Executed 2026-09-26. **All five criteria failed.** OOS net Sharpe −0.31 against
a 0.95 bar; OOS net return negative; final-unseen negative; leave-one-out
range −0.95 to +0.44, so the sign is not even stable to dropping one name.

| split | gross bps/rebal | net bps/rebal | net Sharpe | net total |
|---|---:|---:|---:|---:|
| develop 2023–24 | +162.6 | +142.8 | +1.05 | +180.6% |
| **OOS 2025** | −19.2 | **−39.2** | **−0.31** | −33.1% |
| final unseen 2026 | −219.2 | −239.2 | −0.79 | −100.2% |

**The kill criterion is met and the line is closed permanently.**

Three amendments were made to this document *before* the run, each on
literature grounds and each recorded in the code that executed it:

1. **Weighting: equal → cap** (trailing dollar volume). Ammann et al. (SSRN
   4287573) measure crypto survivorship/delisting bias at 62.19%/yr
   equal-weighted against 0.93%/yr cap-weighted — 67× larger — because a dead
   coin's omitted return is its terminal −100% and the damage scales with
   weight. Fieberg et al. (JFQA 2025) construct value-weighted for the same
   reason. The pre-registered equal-weighted run is reported and **also
   failed**.
2. **Liquidity screen**, added after the data demanded it: only 32 of 190
   symbols clear $5m median 4h dollar volume. `exchangeInfo` still lists coins
   down 80–99% (AEVO −98.9%, ACE −98.9%, 1000SATS −97.8%), and a long leg
   holding one of those loses its whole weight — the source of a −10,020 bps
   rebalance.
3. **Data screen**: 15 symbols whose price series jumps ≥100% in a single 4h
   bar (redenominations and relistings) are dropped whole.

**What was *not* amended: the signal, the horizon, the rebalance frequency,
the cost, the splits, or the decision rule.** Those are the test.

## The result that makes this worth having run

For the first time in this project, a design was **capable of concluding**.
The cross-section solved the sample-size objection that killed every
single-asset line: the 9-symbol pilot measured lag-1 autocorrelation between
−0.11 and +0.05 and an effective sample size equal to the nominal count to
within 1%. A 1R/2R bracket could never do that.

So the null is not "we could not measure it". **The measurement worked and the
answer was no.** The gross edge was real and large in 2023–24 and had decayed
to negative by 2025 — which is the same compression the funding line showed
(§3.21, administered via Binance's 2021 leverage cut) and the same decay the
literature reports for crypto factors since 2022.

The bar was also checked against published work rather than an internal
constant: Fieberg et al. report **median Sharpe 0.83 for plain cross-sectional
momentum** across 55,296 design specifications, insignificant in 49% of them,
with 100 names sufficient breadth. The 0.95 bar used here sits just *above*
that published median — so a FAIL was the statistically expected outcome for
this family, and is reported as one.

