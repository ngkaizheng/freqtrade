可以。下面这份我会直接按 \*\*“可以原样 paste 给 coding agent 实现”\*\* 的方式写。



重点不是让 agent “找一个回测赚钱的策略”，而是让它建立 \*\*Strategy Factory V2：Market Regime + Derivatives + Multi-Timeframe + OOS + Forward Validation\*\*。



我建议你\*\*不要让 agent 自己发挥改变研究规则\*\*。尤其是 hypothesis、threshold、OOS、survivor criteria 都应该预注册，否则很容易再次出现 overfitting。



\# Strategy Factory V2



\## Market Regime + Derivatives + Multi-Timeframe Research System



\## 0. Objective



Upgrade the existing `tools/strategy\_factory/` MVP into V2.



The objective is NOT:



> Find a historical strategy with the highest backtest return.



The objective is:



> Identify economically interpretable crypto market conditions that demonstrate statistically meaningful, cost-adjusted, out-of-sample edge and survive forward testing.



The system must aggressively reject false discoveries.



Do NOT optimize parameters repeatedly against the same OOS period.



Do NOT modify the existing MVP results.



Do NOT modify `freqtrade/` core code.



Do NOT modify existing market data.



Create V2 as an isolated research version.



Recommended version:



`2026-09-26-v2-regime-derivatives`



\---



\# 1. Existing MVP Must Remain Untouched



Existing implementation:



```text

tools/strategy\_factory/

```



Existing full run:



```text

user\_data/strategy\_factory\_runs/full-mvp-20260925/

```



Existing conclusions must remain reproducible.



V2 must use a separate output namespace:



```text

user\_data/strategy\_factory\_runs/v2/

```



Do not overwrite:



```text

full-mvp-20260925/

```



\---



\# 2. Research Philosophy



V2 should investigate:



1\. Market regime

2\. Derivatives positioning

3\. Order-flow imbalance

4\. Funding

5\. Basis

6\. Open interest

7\. Volatility

8\. Multi-timeframe confirmation

9\. Cross-asset confirmation

10\. Cost-adjusted forward returns



Avoid blindly combining technical indicators.



The core research question is:



> Under which observable market states does the conditional future return distribution become meaningfully different from unconditional returns?



The system should first test the predictive condition itself before converting it into a trading strategy.



\---



\# 3. Data Architecture



Create a canonical data layer.



Recommended structure:



```text

user\_data/

&#x20;   data/

&#x20;       binance/

&#x20;           futures/

&#x20;               canonical/

&#x20;                   BTC/

&#x20;                   ETH/

&#x20;                   SOL/

&#x20;                   BNB/

&#x20;                   XRP/

```



Do not delete or replace existing raw data.



\---



\# 4. Required Data



\## 4.1 Price



Required:



```text

1m OHLCV

5m OHLCV

15m OHLCV

30m OHLCV

1h OHLCV

4h OHLCV

```



At minimum V2 execution must support:



```text

5m

15m

1h

```



1m can remain available for execution simulation.



\---



\# 5. Derivatives Data



Add:



```text

funding\_rate

open\_interest

mark\_price

index\_price

basis

taker\_buy\_volume

taker\_sell\_volume

```



Where available.



Every dataset must preserve:



```text

timestamp

symbol

source

timeframe

```



\---



\# 6. Canonical Funding



Create a normalized funding table.



Example:



```text

timestamp

symbol

funding\_rate

source

```



Funding must be treated as an event occurring at a specific timestamp.



Do NOT forward-fill funding blindly.



Do NOT charge funding continuously.



Only apply funding at actual funding events.



If historical data is incomplete:



```text

funding\_available = false

```



for affected periods.



Never silently invent missing funding.



\---



\# 7. Mark Price



Create canonical mark-price data:



```text

timestamp

symbol

mark\_price

```



Use mark price where required for:



\* liquidation-aware analysis

\* funding calculations

\* execution validation

\* derivatives-specific statistics



\---



\# 8. Open Interest



Normalize:



```text

timestamp

symbol

open\_interest

```



Calculate:



```text

OI return

OI percentage change

OI z-score

OI percentile

OI slope

OI acceleration

```



Recommended windows:



```text

30 bars

60 bars

120 bars

288 bars

```



Do not optimize these windows.



Treat them as preregistered research windows.



\---



\# 9. Taker Flow



Calculate:



```text

taker\_buy\_volume

taker\_sell\_volume

```



Then:



```text

taker\_imbalance =

(

&#x20;   taker\_buy\_volume - taker\_sell\_volume

)

/

(

&#x20;   taker\_buy\_volume + taker\_sell\_volume

)

```



Also calculate rolling:



```text

5-bar

15-bar

30-bar

60-bar

```



aggregations.



Do not introduce arbitrary thresholds after looking at results.



\---



\# 10. Basis



Where spot/index data is available:



```text

basis =

(mark\_price - index\_price)

/

index\_price

```



Calculate:



```text

basis z-score

basis percentile

basis change

```



\---



\# 11. Funding Features



Calculate:



```text

funding\_rate

funding\_zscore

funding\_percentile

funding\_change

rolling\_funding\_mean

rolling\_funding\_sum

```



Use only information available at decision time.



No lookahead.



\---



\# 12. Price Features



Keep only economically useful features.



Required:



```text

returns:

1 bar

3 bars

6 bars

12 bars

24 bars

48 bars



ATR:

14

30

60



realized volatility:

30

60

120



EMA:

20

50

100

200



distance from VWAP



rolling high

rolling low



range expansion

range compression

```



Do not create a giant indicator library.



\---



\# 13. Market Regime Engine



Implement a deterministic regime classifier.



\## Trend



Use normalized price movement and moving-average structure.



Possible states:



```text

STRONG\_UP

WEAK\_UP

NEUTRAL

WEAK\_DOWN

STRONG\_DOWN

```



Do not train an ML classifier in V2.



The regime engine must be interpretable.



\---



\# 14. Volatility Regime



Classify:



```text

LOW\_VOL

NORMAL\_VOL

HIGH\_VOL

EXTREME\_VOL

```



Use rolling volatility percentile.



Example conceptual definition:



```text

LOW\_VOL       <= 20th percentile

NORMAL\_VOL    20-80th percentile

HIGH\_VOL      80-95th percentile

EXTREME\_VOL   > 95th percentile

```



These thresholds are preregistered.



Do not optimize them.



\---



\# 15. Liquidity Regime



Where reliable volume data exists:



```text

LOW\_LIQUIDITY

NORMAL\_LIQUIDITY

HIGH\_LIQUIDITY

```



Use relative volume / rolling volume percentile.



\---



\# 16. Positioning Regime



Use OI:



```text

OI\_LOW

OI\_NORMAL

OI\_HIGH

OI\_EXTREME

```



Use percentile rather than absolute values so BTC/ETH/SOL/etc. can be compared.



\---



\# 17. Funding Regime



```text

FUNDING\_NEG\_EXTREME

FUNDING\_NEG

FUNDING\_NEUTRAL

FUNDING\_POS

FUNDING\_POS\_EXTREME

```



Again use percentile/z-score.



\---



\# 18. Combined Market State



Create a structured state:



```text

trend\_regime

volatility\_regime

liquidity\_regime

oi\_regime

funding\_regime

```



Example:



```text

STRONG\_UP

\+

HIGH\_VOL

\+

HIGH\_OI

\+

POS\_EXTREME\_FUNDING

```



This becomes a market state rather than a trading signal.



\---



\# 19. Research Layer



IMPORTANT:



First evaluate the conditional return.



For every hypothesis calculate:



```text

future\_return\_5m

future\_return\_15m

future\_return\_30m

future\_return\_1h

future\_return\_4h

```



Also:



```text

MAE

MFE

maximum drawdown

tail loss

```



Do this BEFORE creating entries/exits.



\---



\# 20. Baseline Distribution



For every symbol and timeframe calculate unconditional:



```text

mean return

median return

standard deviation

5th percentile

25th percentile

75th percentile

95th percentile

```



Then compare every hypothesis against the unconditional baseline.



A signal is not interesting merely because:



```text

mean\_return > 0

```



It should demonstrate improvement versus the appropriate baseline.



\---



\# 21. Hypothesis Families



Create approximately 50–100 hypotheses.



Do NOT generate thousands of random combinations.



Each hypothesis must have economic reasoning.



\---



\# 22. H1 — Trend + OI Confirmation



Examples:



```text

price trend UP

\+

OI increasing

```



Measure forward returns.



Mirror:



```text

price trend DOWN

\+

OI increasing

```



Research both directions.



\---



\# 23. H2 — Trend + OI Divergence



Example:



```text

price rising

\+

OI falling

```



versus:



```text

price falling

\+

OI falling

```



Test whether these conditions correspond to:



\* short covering

\* long liquidation

\* exhaustion

\* continuation



Do not assume the interpretation is correct.



\---



\# 24. H3 — Funding Extremes



Test:



```text

extreme positive funding

```



and



```text

extreme negative funding

```



against forward returns.



Test:



```text

5m

15m

30m

1h

4h

```



Do not automatically assume mean reversion.



Measure the data.



\---



\# 25. H4 — Funding + Price Divergence



Examples:



```text

price rising

\+

funding becoming increasingly positive

```



versus:



```text

price rising

\+

funding becoming less positive

```



and corresponding bearish conditions.



\---



\# 26. H5 — Funding + OI



Examples:



```text

positive funding

\+

OI increasing

```



```text

positive funding

\+

OI decreasing

```



```text

negative funding

\+

OI increasing

```



```text

negative funding

\+

OI decreasing

```



Measure conditional distributions.



\---



\# 27. H6 — Price + OI + Taker Flow



Test combinations such as:



```text

price ↑

OI ↑

taker imbalance ↑

```



and bearish mirror.



Use only preregistered thresholds:



```text

top 20%

top 10%

bottom 20%

bottom 10%

```



\---



\# 28. H7 — Liquidation-Type Conditions



Research:



```text

large price move

\+

large OI decrease

```



This is a proxy for forced deleveraging.



Measure what happens over:



```text

5m

15m

30m

1h

4h

```



Do not label it as liquidation unless actual liquidation data confirms it.



Call it:



```text

OI contraction after large price move

```



when actual liquidation data is unavailable.



\---



\# 29. H8 — Volatility Compression → Expansion



Test:



```text

low volatility percentile

\+

range compression

\+

volume expansion

```



Then measure breakout continuation versus mean reversion.



Do not use the direction of the breakout unless it is explicitly defined at signal time.



\---



\# 30. H9 — Volatility Shock



Test:



```text

volatility transitions

LOW → HIGH

NORMAL → EXTREME

```



Measure post-shock returns.



\---



\# 31. H10 — Basis Extremes



Where valid basis data exists:



```text

extreme positive basis

extreme negative basis

```



Measure subsequent returns.



\---



\# 32. H11 — Cross-Asset Confirmation



Use BTC as a market regime reference.



Examples:



```text

BTC trend UP

\+

ETH relative strength

```



or:



```text

BTC trend UP

\+

SOL trend UP

```



Test whether cross-asset confirmation improves conditional returns.



\---



\# 33. H12 — Cross-Asset Divergence



Examples:



```text

BTC ↑

ETH ↓

```



```text

BTC ↓

ETH ↑

```



Measure subsequent convergence/divergence.



Do not assume mean reversion.



\---



\# 34. H13 — BTC Market Regime Filter



For altcoin strategies:



Only allow trades when:



```text

BTC regime = STRONG\_UP

```



or other preregistered states.



Test whether BTC regime improves altcoin signal quality.



\---



\# 35. H14 — Multi-Timeframe Confirmation



Example:



```text

1h trend UP

\+

15m pullback

\+

5m momentum recovery

```



Mirror for short.



Do not optimize arbitrary EMA combinations.



Use existing preregistered trend definitions.



\---



\# 36. H15 — Regime-Specific Strategy Activation



Instead of one universal strategy:



```text

Trend strategy only during strong trend

Mean reversion only during neutral/low-vol regime

Breakout strategy only during volatility expansion

```



Measure whether regime filtering improves the base strategy.



\---



\# 37. Hypothesis Metadata



Every hypothesis must contain:



```json

{

&#x20; "hypothesis\_id": "...",

&#x20; "family": "...",

&#x20; "economic\_reason": "...",

&#x20; "features": \[],

&#x20; "timeframe": "...",

&#x20; "entry\_definition": "...",

&#x20; "exit\_definition": "...",

&#x20; "thresholds": {},

&#x20; "expected\_direction": "long|short|both",

&#x20; "preregistered": true

}

```



The economic reason must be written BEFORE results are generated.



\---



\# 38. Timeframes



V2 should primarily test:



```text

5m

15m

1h

```



Optional:



```text

30m

4h

```



1m should primarily be used for execution simulation, not as the primary alpha discovery timeframe.



\---



\# 39. Execution Model



Keep the MVP execution principles:



```text

signal at candle close

entry at next available execution price

```



Never enter using the same candle close unless explicitly modelling executable closing price.



\---



\# 40. Stop Handling



Use:



```text

stop-first

```



when both stop and target occur inside the same candle.



If gap crosses stop:



```text

execute at realistic gap price

```



Do not assume ideal stop execution.



\---



\# 41. Costs



Base case:



```text

fee = 5 bps per side

slippage = 1 bp per side

```



Stress case:



```text

fee = 10 bps per side

slippage = 3 bps per side

```



Also test:



```text

2x base cost

```



as a robustness check.



Do not optimize costs to make strategies pass.



\---



\# 42. Funding



Apply funding only at actual funding events.



Use adverse-payer treatment for conservative research.



Do not count funding credits unless explicitly enabled in a separate analysis.



\---



\# 43. Leverage



Research layer should default to:



```text

1x

```



Do not use leverage to manufacture returns.



A strategy must first demonstrate positive expectancy at 1x.



\---



\# 44. Walk Forward



Maintain the existing rolling walk-forward architecture.



Minimum:



```text

15 folds

```



Each fold must contain:



```text

training

validation

OOS

```



The OOS period must never be used for parameter selection.



\---



\# 45. Final Holdout



V2 must reserve a final untouched forward period.



Example:



```text

Historical development data

&#x20;       ↓

Walk-forward research

&#x20;       ↓

Model/spec freeze

&#x20;       ↓

FINAL HOLDOUT

```



The final holdout must not be inspected for parameter tuning.



\---



\# 46. Anti-Overfitting Rules



Absolutely forbidden:



```text

Run result

↓

change threshold

↓

rerun

↓

choose better result

```



unless the changed hypothesis receives a NEW hypothesis ID and is explicitly registered as a new experiment.



No hidden optimization.



No manually selected winners.



No cherry-picking.



\---



\# 47. Minimum Sample Size



A hypothesis must not be considered statistically useful with tiny samples.



Default:



```text

minimum total observations = 200

```



For trade-based strategies:



```text

minimum OOS trades = 200

```



If fewer:



```text

status = INSUFFICIENT\_SAMPLE

```



Do not rank it as a winner.



\---



\# 48. Metrics



Every hypothesis must report:



```text

sample\_count



mean\_return

median\_return



win\_rate



profit\_factor



expectancy



volatility



max\_drawdown



MAE

MFE



Sharpe

Sortino



DSR



Reality Check p-value

```



Also:



```text

base\_cost\_expectancy

stress\_cost\_expectancy

```



\---



\# 49. Statistical Significance



Use the existing:



```text

block bootstrap

Monte Carlo

Deflated Sharpe Ratio

White Reality Check

```



Maintain:



```text

2000 resamples

```



unless computationally impossible.



If changed, record the reason in manifest.



\---



\# 50. Multiple Testing



This is critical.



The system must account for the fact that V2 tests many hypotheses.



A hypothesis that looks good individually is NOT automatically valid.



Report:



```text

number\_of\_hypotheses\_tested

number\_positive

number\_survivors

multiple\_testing\_adjustment

```



\---



\# 51. Survivor Criteria



A hypothesis can only become a survivor if ALL conditions pass.



Default:



```text

OOS expectancy > 0



stress expectancy > 0



base PF > 1.05



stress PF > 1.00



minimum OOS sample met



positive expectancy in >= 60% of OOS folds



DSR > 0



Reality Check p < 0.05



no single fold contributes > 35% of total OOS profit

```



Do not loosen these thresholds after seeing results.



\---



\# 52. Stability Requirement



Calculate fold-level metrics.



Example:



```text

Fold 1

Fold 2

...

Fold 15

```



A strategy that only makes money in one exceptional period should fail.



Require:



```text

>= 60% profitable OOS folds

```



and inspect:



```text

worst fold

median fold

best fold

```



\---



\# 53. Stress Requirement



Every survivor must remain positive after:



```text

2x cost

```



If:



```text

base PF = 1.20

stress PF = 0.80

```



then:



```text

FAIL

```



This prevents selecting fragile micro-edge strategies.



\---



\# 54. Regime Stability



For each survivor report performance under:



```text

bull

bear

sideways

high-vol

low-vol

```



A strategy does not necessarily need to work in every regime.



But the system must explicitly show where the edge exists.



\---



\# 55. Asset Stability



Report separately:



```text

BTC

ETH

SOL

BNB

XRP

...

```



A signal that works only on one asset should not be described as universal.



Label:



```text

asset\_specific

```



if appropriate.



\---



\# 56. Timeframe Stability



Report:



```text

5m

15m

1h

```



If a signal works only on one timeframe, preserve that information.



Do not average it away.



\---



\# 57. Economic Interpretation



Every survivor must generate an explanation report:



```text

Why might this edge exist?



Which observable behavior is being captured?



Which market participants might create it?



What invalidates the hypothesis?



What regime causes failure?

```



This is qualitative research documentation, not proof of causality.



\---



\# 58. Strategy Conversion



Only hypotheses that pass the research layer may become executable strategies.



Pipeline:



```text

Hypothesis

↓

Conditional return test

↓

Statistical validation

↓

OOS validation

↓

Cost stress

↓

Strategy conversion

```



Do NOT create executable strategies for every hypothesis.



\---



\# 59. Paper Trading



Survivors must enter paper trading.



Create:



```text

tools/strategy\_factory/paper/

```



Paper trader must record:



```text

signal timestamp

expected entry

actual simulated entry

exit

PnL

fees

slippage

funding

market regime

```



\---



\# 60. Forward Validation



Minimum suggested forward period:



```text

30 days

```



Prefer:



```text

60–90 days

```



depending on signal frequency.



No live capital during this stage.



\---



\# 61. Paper Trading Kill Rules



A strategy should be paused if:



```text

forward expectancy becomes materially negative

```



or:



```text

live/paper distribution strongly diverges from research distribution

```



or:



```text

execution assumptions are invalidated

```



The exact thresholds should be documented, not manually improvised.



\---



\# 62. Research Dashboard



Generate:



```text

report.md

report.html

```



Include:



```text

hypothesis leaderboard

```



but do NOT produce an overall "best strategy" ranking.



Instead classify:



```text

PASS

FAIL

INSUFFICIENT\_SAMPLE

PROMISING\_BUT\_UNVERIFIED

```



\---



\# 63. Required Reports



Generate:



```text

hypothesis\_summary.csv

trial\_results.csv

fold\_results.csv

regime\_results.csv

asset\_results.csv

timeframe\_results.csv

cost\_stress.csv

conditional\_returns.csv

paper\_trading\_specs.csv

survivors.json

manifest.json

```



\---



\# 64. Required Visualizations



Generate HTML charts for:



```text

conditional return distributions



OOS equity curves



fold expectancy



regime performance



asset performance



cost sensitivity



funding regime performance



OI regime performance



taker imbalance performance



drawdown



MAE/MFE

```



Do not create misleading cumulative charts that hide individual fold behavior.



\---



\# 65. Data Audit



Before every V2 run:



```text

check duplicate timestamps

check missing candles

check OHLC validity

check timestamp ordering

check timezone

check funding event ordering

check OI continuity

check mark/index consistency

check cross-timeframe alignment

```



Produce:



```text

data\_audit.json

```



\---



\# 66. Lookahead Tests



Add automated tests proving that:



```text

future candles cannot affect current features

future funding cannot affect current signal

future OI cannot affect current signal

future cross-asset data cannot affect current signal

```



Create explicit synthetic tests.



For example:



```text

modify future candle dramatically

```



The signal before that candle must remain identical.



\---



\# 67. Data Leakage Test



For every feature:



```text

feature\_timestamp <= decision\_timestamp

```



must be guaranteed.



Add assertions.



Fail loudly.



Never silently shift data.



\---



\# 68. Determinism



Given identical:



```text

data fingerprint

spec version

random seed

```



the result must be reproducible.



Store:



```text

random\_seed

data\_hash

source\_hash

spec\_version

code\_version

```



in `manifest.json`.



\---



\# 69. CLI



Implement:



```powershell

python -m tools.strategy\_factory audit-v2 `

&#x20; --data-dir user\_data\\data\\binance\\futures



python -m tools.strategy\_factory discover-v2 `

&#x20; --data-dir user\_data\\data\\binance\\futures `

&#x20; --output user\_data\\strategy\_factory\_runs\\v2\\YYYYMMDD



python -m tools.strategy\_factory report-v2 `

&#x20; --run user\_data\\strategy\_factory\_runs\\v2\\YYYYMMDD



python -m tools.strategy\_factory paper-v2 `

&#x20; --run user\_data\\strategy\_factory\_runs\\v2\\YYYYMMDD

```



Also preserve existing MVP CLI.



\---



\# 70. Testing



Add tests:



```text

tests/tools/test\_strategy\_factory\_v2\_data.py

tests/tools/test\_strategy\_factory\_v2\_features.py

tests/tools/test\_strategy\_factory\_v2\_regime.py

tests/tools/test\_strategy\_factory\_v2\_hypotheses.py

tests/tools/test\_strategy\_factory\_v2\_engine.py

tests/tools/test\_strategy\_factory\_v2\_validation.py

tests/tools/test\_strategy\_factory\_v2\_runner.py

tests/tools/test\_strategy\_factory\_v2\_leakage.py

```



Test:



```text

feature causality

funding event handling

OI alignment

cross-asset alignment

next-open execution

gap handling

stop-first

fee calculation

slippage

funding

walk-forward boundaries

bootstrap determinism

```



\---



\# 71. Important: pytest



If pytest is not installed, DO NOT claim the test suite passed.



Report:



```text

pytest unavailable

```



or install it only if the environment/project instructions explicitly allow dependency installation.



Do not silently modify the environment.



\---



\# 72. Experiment Registry



Create:



```text

PREREGISTRATION\_V2.md

```



before running the full experiment.



It must contain:



```text

hypothesis list

thresholds

timeframes

cost assumptions

sample requirements

OOS design

survivor criteria

statistical tests

random seed

```



After the run starts, do not modify it.



If a change is needed:



```text

PREREGISTRATION\_V2\_1.md

```



with a new version.



\---



\# 73. No Parameter Mining



Do not implement a generic parameter optimizer in V2.



Do NOT run:



```text

EMA 19

EMA 20

EMA 21

EMA 22

...

```



and select the highest PF.



Do NOT search hundreds of thresholds automatically.



The goal is hypothesis validation, not curve fitting.



\---



\# 74. Expected Output Interpretation



If all hypotheses fail:



```text

This is a valid research result.

```



Do not force survivors.



If only a few pass:



```text

Do not immediately call them profitable strategies.

```



Label:



```text

RESEARCH SURVIVOR

```



until forward tested.



\---



\# 75. Important Final Principle



The system must optimize for:



```text

robustness

```



not:



```text

backtest return

```



A strategy with:



```text

10% CAGR

stable OOS

low drawdown

survives cost stress

multiple assets

multiple regimes

```



is more scientifically interesting than a strategy with:



```text

300% historical return

```



that depends on one historical period.



\---



\# 76. Implementation Order



Implement in this exact order.



\## Phase A



```text

canonical data

↓

data audit

↓

funding normalization

↓

OI

↓

mark/index

↓

taker flow

↓

basis

```



\## Phase B



```text

feature engine

↓

regime engine

↓

causality tests

↓

leakage tests

```



\## Phase C



```text

conditional return engine

↓

50–100 preregistered hypotheses

↓

baseline comparison

```



\## Phase D



```text

walk-forward

↓

cost stress

↓

DSR

↓

Reality Check

↓

multiple-testing analysis

```



\## Phase E



```text

survivor extraction

↓

strategy conversion

↓

paper trading

```



Do not skip directly to Phase E.



\---



\# 77. Definition of Success



V2 is successful even if:



```text

survivors = 0

```



provided that:



```text

data is correct

features are causal

experiments are reproducible

hypotheses are properly tested

false positives are rejected

```



The ultimate goal is to find a strategy that survives:



```text

historical OOS

\+

cost stress

\+

multiple testing

\+

regime analysis

\+

asset analysis

\+

forward paper trading

```



Only after all of those should real capital be considered.



\---



\# 78. Coding Agent Instructions



Before implementing:



1\. Inspect the existing `tools/strategy\_factory/`.

2\. Inspect existing tests.

3\. Inspect existing data formats.

4\. Do not duplicate existing functionality unnecessarily.

5\. Do not modify `freqtrade/`.

6\. Do not modify existing datasets.

7\. Do not overwrite MVP results.

8\. Reuse existing validated execution/validation components where appropriate.

9\. Add V2 functionality incrementally.

10\. Run compile/tests after each major phase.

11\. Do not claim tests passed unless they actually ran.

12\. Do not silently install dependencies.

13\. Do not alter research criteria based on observed results.

14\. Do not generate a trading strategy merely because it has positive historical PnL.



Before the full experiment, show:



```text

implementation summary

files changed

data sources detected

data gaps

hypothesis registry

preregistration file

validation methodology

```



Then run the experiment.



The final response must include:



```text

files changed

tests executed

data audit result

number of hypotheses

number of observations

number of OOS trades

number of research survivors

number of paper-trading candidates

```



If there are zero survivors, explicitly report zero.



Do not manufacture a strategy.



\---



\# 79. End Goal



The desired architecture is:



```text

&#x20;                   ┌──────────────────┐

&#x20;                   │  Binance Data    │

&#x20;                   └────────┬─────────┘

&#x20;                            ↓

&#x20;                   ┌──────────────────┐

&#x20;                   │ Canonical Data   │

&#x20;                   └────────┬─────────┘

&#x20;                            ↓

&#x20;            ┌───────────────┼────────────────┐

&#x20;            ↓               ↓                ↓

&#x20;         Price             OI             Funding

&#x20;            ↓               ↓                ↓

&#x20;         Volume          Taker Flow        Basis

&#x20;            └───────────────┼────────────────┘

&#x20;                            ↓

&#x20;                   ┌──────────────────┐

&#x20;                   │ Feature Engine   │

&#x20;                   └────────┬─────────┘

&#x20;                            ↓

&#x20;                   ┌──────────────────┐

&#x20;                   │ Regime Engine    │

&#x20;                   └────────┬─────────┘

&#x20;                            ↓

&#x20;                ┌────────────────────────┐

&#x20;                │ Conditional Research  │

&#x20;                └────────────┬───────────┘

&#x20;                             ↓

&#x20;                ┌────────────────────────┐

&#x20;                │ 50–100 Hypotheses      │

&#x20;                └────────────┬───────────┘

&#x20;                             ↓

&#x20;                ┌────────────────────────┐

&#x20;                │ Walk Forward OOS       │

&#x20;                └────────────┬───────────┘

&#x20;                             ↓

&#x20;                ┌────────────────────────┐

&#x20;                │ Cost + Funding Stress  │

&#x20;                └────────────┬───────────┘

&#x20;                             ↓

&#x20;                ┌────────────────────────┐

&#x20;                │ DSR + Reality Check    │

&#x20;                └────────────┬───────────┘

&#x20;                             ↓

&#x20;                    ┌─────────────────┐

&#x20;                    │ Research Pass   │

&#x20;                    └────────┬────────┘

&#x20;                             ↓

&#x20;                    ┌─────────────────┐

&#x20;                    │ Paper Trading   │

&#x20;                    └────────┬────────┘

&#x20;                             ↓

&#x20;                    ┌─────────────────┐

&#x20;                    │ Forward Test    │

&#x20;                    └────────┬────────┘

&#x20;                             ↓

&#x20;                    ┌─────────────────┐

&#x20;                    │ Real Capital    │

&#x20;                    └─────────────────┘

```



The system must always prefer:



```text

NO TRADE

```



over:



```text

FALSE POSITIVE

```



and:



```text

RESEARCH SURVIVOR

```



must never automatically mean:



```text

PROFITABLE LIVE STRATEGY

```



\### 我另外给你一个很重要的建议



你把这份给 coding agent 后，\*\*第一轮不要让它直接跑完整 50–100 hypotheses\*\*。



让它先完成：



```text

Phase A → canonical data

Phase B → features + regime

```



然后让 agent 停下来，把：



1\. 它实际找到哪些数据

2\. 每个数据的时间范围

3\. 缺哪些字段

4\. funding 是否完整

5\. OI 的实际粒度

6\. taker flow 的实际粒度

7\. BTC/ETH/SOL 等哪些币真正可以用



先报告给你。



\*\*因为数据完整性比多跑 100 个 strategy 重要得多。\*\*



而且这一次我建议你特别盯着一个东西：\*\*不要让 coding agent 偷偷把“research hypothesis”变成“参数优化器”。\*\* 这是整个 V2 最容易走歪的地方。



如果 V2 最后真的找到几个 survivor，我们再做下一层：\*\*把 survivor 转成 Freqtrade strategy + paper-trading engine + 每日自动扫描/报告\*\*。那时候才开始真正接近你说的“我要赚钱”的阶段，而不是单纯做回测。



