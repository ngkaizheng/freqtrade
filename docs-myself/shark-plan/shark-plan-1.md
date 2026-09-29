可以。你这次我建议\*\*不要让 Codex 一上来自己发挥\*\*，而是直接给 Agent 一份明确的研究规格。



我把它整理成一个 \*\*Shark Hunter Research Spec\*\*：先做最简单的 Volume-only baseline，再逐层加入 CVD / VWAP / OBV / OI / Funding / Liquidation。这样最后你能知道\*\*到底是哪一个信号提供了 edge\*\*，而不是得到一个把 8 个指标揉在一起、无法解释的策略。



另外，我查了目前的交易所数据接口：Binance 的公开衍生品数据确实可以提供 Open Interest、Funding、Taker Buy/Sell Volume 等；Bybit 也提供 5m OI 数据，并有完整 liquidation websocket。(\[Binance Developers]\[1])



下面这份你可以\*\*基本原封不动丢给 Codex Agent\*\*。



\# Shark Hunter



\## Crypto 1m / 5m Volume \& Order-Flow Strategy Research Specification



\## 0. Objective



Build and backtest a family of short-term crypto futures strategies based on the hypothesis:



> Detect abnormal market participation / aggressive order flow, enter after confirmation, and exit when momentum / participation deteriorates.



The strategy must NOT claim to literally detect "whales", "market makers", or "manipulators".



Instead, define observable proxies:



\* Relative Volume (RVOL)

\* Taker Buy/Sell imbalance

\* Cumulative Volume Delta (CVD)

\* On-Balance Volume (OBV)

\* VWAP

\* Open Interest (OI)

\* Funding Rate

\* Liquidation activity

\* Price breakout / momentum



The purpose is research:



1\. Determine whether abnormal volume contains predictive information.

2\. Determine whether order-flow confirmation improves the baseline.

3\. Determine whether OI / funding / liquidation add incremental information.

4\. Determine whether the edge survives out-of-sample testing.

5\. Avoid overfitting and indicator stacking.



Do NOT optimize everything simultaneously.



\---



\# 1. Core Philosophy



The research must proceed incrementally.



Build these strategies independently:



```text

SHARK-01  Volume Breakout

SHARK-02  Volume + VWAP

SHARK-03  Volume + CVD

SHARK-04  Volume + OBV

SHARK-05  Volume + Open Interest

SHARK-06  Volume + OI + CVD

SHARK-07  Volume + Liquidation

SHARK-08  Full Shark Hunter

```



The purpose is not to find the strategy with the highest backtest return.



The purpose is to determine:



> Which observable market signal contributes genuine incremental predictive power?



\---



\# 2. Market



Primary market:



\* Crypto perpetual futures

\* Prefer liquid USDT-margined perpetual contracts



Initial universe:



```text

BTCUSDT

ETHUSDT

SOLUSDT

BNBUSDT

XRPUSDT

DOGEUSDT

ADAUSDT

AVAXUSDT

LINKUSDT

```



Do not start with hundreds of illiquid altcoins.



First validate the strategy on highly liquid assets.



Later perform cross-sectional testing.



\---



\# 3. Timeframes



Primary:



```text

5-minute

```



Secondary:



```text

1-minute

```



Do NOT combine 1m and 5m initially.



Test them independently.



Recommended order:



```text

Phase 1:

5m



Phase 2:

1m



Phase 3:

5m signal + 1m execution

```



\---



\# 4. Data Requirements



At minimum:



```text

timestamp

open

high

low

close

volume

quote\_volume

```



Preferably also:



```text

taker\_buy\_volume

taker\_sell\_volume

open\_interest

funding\_rate

liquidation\_volume\_long

liquidation\_volume\_short

```



For Binance futures, public data includes aggregate trades, funding history, open interest statistics, and taker buy/sell volume. Binance defines taker buy/sell volume as aggressive buy/sell volume over the period. (\[Binance Developers]\[1])



Bybit also exposes OI intervals including 5min and liquidation streams. (\[Bybit Exchange]\[2])



\---



\# 5. IMPORTANT DATA RULE



Never use future information.



Every feature at candle `t` must only use information available at or before candle `t`.



If a signal is generated using the closing price of candle `t`, the earliest executable trade is:



```text

candle t+1

```



unless the backtest explicitly models intrabar execution.



Do NOT enter at the same candle close without explicitly modeling execution latency.



\---



\# 6. Feature Definitions



\## 6.1 Relative Volume



Define:



```text

RVOL\_N =

current\_volume / SMA(volume, N)

```



Default:



```text

N = 20

```



Example:



```text

RVOL = 2.5

```



means current volume is 2.5x its recent average.



Test:



```text

RVOL threshold:

1.5

2.0

2.5

3.0

4.0

```



Do not optimize continuously at first.



\---



\# 7. Volume Spike



Define:



```text

volume\_spike =

RVOL\_20 >= threshold

```



Default:



```text

threshold = 2.0

```



This is the primary "market participation" signal.



\---



\# 8. Price Breakout



For long:



```text

previous\_high\_20 =

highest(high, 20) excluding current candle



breakout\_long =

close > previous\_high\_20

```



For short:



```text

previous\_low\_20 =

lowest(low, 20) excluding current candle



breakout\_short =

close < previous\_low\_20

```



Never include the current candle in the breakout reference.



\---



\# 9. VWAP



Use session/intraday VWAP where available.



For crypto 24/7 markets, implement a clearly defined VWAP anchor.



Default:



```text

UTC daily VWAP

```



Formula:



```text

VWAP =

sum(typical\_price \* volume)

/

sum(volume)

```



where:



```text

typical\_price = (high + low + close) / 3

```



Long confirmation:



```text

close > VWAP

```



Short confirmation:



```text

close < VWAP

```



\---



\# 10. OBV



Standard OBV:



```text

if close > previous\_close:

&#x20;   OBV += volume



if close < previous\_close:

&#x20;   OBV -= volume



if close == previous\_close:

&#x20;   OBV unchanged

```



Define:



```text

OBV\_SMA20 = SMA(OBV, 20)

```



Bullish condition:



```text

OBV > OBV\_SMA20

```



Stronger bullish condition:



```text

OBV > highest(OBV, 20) excluding current candle

```



Do not assume OBV literally identifies institutional accumulation.



Treat it as a volume-price proxy.



\---



\# 11. CVD



Preferred definition:



```text

delta =

taker\_buy\_volume - taker\_sell\_volume

```



Then:



```text

CVD\_t =

CVD\_(t-1) + delta\_t

```



For Binance data, taker buy/sell volume is directly available through public futures market data. (\[Binance Developers]\[1])



Define:



```text

CVD\_SMA20 = SMA(CVD, 20)

```



Bullish:



```text

CVD > CVD\_SMA20

```



CVD momentum:



```text

CVD\_delta\_5 =

CVD\_t - CVD\_(t-5)

```



Bullish:



```text

CVD\_delta\_5 > 0

```



Important:



CVD is an aggressive order-flow proxy.



Do NOT label it as "whale buying".



\---



\# 12. Open Interest



Use:



```text

OI

```



Prefer normalized change:



```text

OI\_change\_N =

OI\_t / OI\_(t-N) - 1

```



Default:



```text

N = 3 candles

```



For 5m:



```text

3 candles = 15 minutes

```



For 1m:



```text

3 candles = 3 minutes

```



Also calculate:



```text

OI\_change\_15m

OI\_change\_30m

```



where data availability permits.



\---



\# 13. Price + OI Regimes



Classify:



\### Price UP + OI UP



```text

price\_change > 0

OI\_change > 0

```



Interpretation:



```text

new positions are entering while price rises

```



Potential trend confirmation.



\---



\### Price UP + OI DOWN



```text

price\_change > 0

OI\_change < 0

```



Possible short covering / position closing.



Do NOT automatically interpret this as bullish continuation.



\---



\### Price DOWN + OI UP



Potential new short positioning.



\---



\### Price DOWN + OI DOWN



Potential long liquidation / position closing.



These are classifications, not causal claims.



\---



\# 14. Funding



Store:



```text

funding\_rate

```



Normalize if necessary:



```text

funding\_zscore

```



using a rolling historical window.



Do NOT use funding as a primary entry signal initially.



Use it as a regime/filter variable.



Example:



```text

extremely\_positive\_funding

```



may indicate crowded longs.



Example:



```text

extremely\_negative\_funding

```



may indicate crowded shorts.



Do not hardcode economic interpretations without testing.



\---



\# 15. Liquidation Data



Track:



```text

long\_liquidation\_volume

short\_liquidation\_volume

total\_liquidation\_volume

```



Also calculate:



```text

liquidation\_ratio =

liquidation\_volume /

rolling\_average\_liquidation\_volume

```



Default:



```text

20-period average

```



Example:



```text

liquidation\_ratio > 3

```



means liquidation activity is unusually high.



Bybit's current public liquidation stream provides liquidation side, quantity, and bankruptcy price at high frequency. (\[Bybit Exchange]\[3])



Important:



Liquidation data from one exchange is NOT the entire crypto market.



Do not treat exchange-specific liquidation volume as global liquidation volume.



\---



\# 16. SHARK-01 — Volume Breakout Baseline



This is the most important baseline.



\## Long Entry



```text

RVOL\_20 >= 2.0



AND



close > previous\_high\_20

```



\## Short Entry



```text

RVOL\_20 >= 2.0



AND



close < previous\_low\_20

```



\## Exit



Test separately:



```text

E1:

close < VWAP

```



```text

E2:

close < breakout\_level

```



```text

E3:

ATR stop + 2R target

```



```text

E4:

trailing ATR

```



Do not combine exits initially.



\---



\# 17. SHARK-02 — Volume + VWAP



\## Long



```text

RVOL\_20 >= 2.0



AND



close > previous\_high\_20



AND



close > VWAP

```



\## Short



```text

RVOL\_20 >= 2.0



AND



close < previous\_low\_20



AND



close < VWAP

```



Exit:



```text

Long:

close < VWAP



Short:

close > VWAP

```



\---



\# 18. SHARK-03 — Volume + CVD



\## Long



```text

RVOL\_20 >= 2.0



AND



close > previous\_high\_20



AND



CVD > CVD\_SMA20



AND



CVD\_delta\_5 > 0

```



\## Short



```text

RVOL\_20 >= 2.0



AND



close < previous\_low\_20



AND



CVD < CVD\_SMA20



AND



CVD\_delta\_5 < 0

```



Exit:



```text

CVD crosses its SMA

```



or separately test:



```text

price crosses VWAP

```



\---



\# 19. SHARK-04 — Volume + OBV



\## Long



```text

RVOL\_20 >= 2.0



AND



close > previous\_high\_20



AND



OBV > OBV\_SMA20

```



\## Short



```text

RVOL\_20 >= 2.0



AND



close < previous\_low\_20



AND



OBV < OBV\_SMA20

```



This tests whether accumulated volume direction adds information beyond raw volume.



\---



\# 20. SHARK-05 — Volume + OI



\## Long



```text

RVOL\_20 >= 2.0



AND



close > previous\_high\_20



AND



OI\_change\_15m > 0

```



\## Short



```text

RVOL\_20 >= 2.0



AND



close < previous\_low\_20



AND



OI\_change\_15m > 0

```



The purpose is to test whether breakout + increasing OI behaves differently from breakout alone.



Do NOT assume OI increase is automatically bullish or bearish.



\---



\# 21. SHARK-06 — Volume + CVD + OI



\## Long



```text

RVOL\_20 >= 2.0



AND



close > previous\_high\_20



AND



CVD\_delta\_5 > 0



AND



OI\_change\_15m > 0

```



\## Short



```text

RVOL\_20 >= 2.0



AND



close < previous\_low\_20



AND



CVD\_delta\_5 < 0



AND



OI\_change\_15m > 0

```



This is the first strategy intended to approximate:



```text

abnormal participation

\+

aggressive directional flow

\+

new positioning

```



\---



\# 22. SHARK-07 — Liquidation Momentum



This strategy is different.



It tests whether liquidation cascades can create short-term continuation.



\## Long



Potential setup:



```text

RVOL\_20 >= 2.0



AND



close > previous\_high\_20



AND



short\_liquidation\_ratio >= 3

```



\## Short



```text

RVOL\_20 >= 2.0



AND



close < previous\_low\_20



AND



long\_liquidation\_ratio >= 3

```



Important:



This is NOT:



```text

"liquidations = buy"

```



It tests whether directional liquidation pressure combined with breakout creates continuation.



\---



\# 23. SHARK-08 — Full Shark Hunter



This is the most complex strategy.



Do NOT assume it is superior.



\## Long



Required:



```text

RVOL\_20 >= 2.0



AND



close > previous\_high\_20



AND



close > VWAP



AND



CVD\_delta\_5 > 0

```



Then require at least ONE:



```text

OI\_change\_15m > 0

```



OR:



```text

short\_liquidation\_ratio >= 2

```



Optional regime filter:



```text

funding\_zscore < +2.0

```



The funding filter exists to avoid entering extremely crowded long conditions.



\## Short



```text

RVOL\_20 >= 2.0



AND



close < previous\_low\_20



AND



close < VWAP



AND



CVD\_delta\_5 < 0

```



Then require at least ONE:



```text

OI\_change\_15m > 0

```



OR:



```text

long\_liquidation\_ratio >= 2

```



Optional:



```text

funding\_zscore > -2.0

```



\---



\# 24. Entry Timing



Default:



```text

Signal generated at candle close t.



Entry at next candle open t+1.

```



Alternative execution model:



```text

Signal generated at t close.



Enter at t+1 open + slippage.

```



Never enter using future candles.



\---



\# 25. Stop Loss



Do NOT optimize stop loss separately for every strategy at first.



Use:



```text

ATR(14)

```



Default:



```text

Stop = 1.0 ATR

```



Test:



```text

0.75 ATR

1.0 ATR

1.5 ATR

2.0 ATR

```



\---



\# 26. Take Profit



Test:



```text

1.5R

2.0R

3.0R

```



where:



```text

R = initial stop distance

```



Example:



```text

Entry = 100

ATR = 2



1 ATR stop:

98



2R target:

104

```



\---



\# 27. Trailing Stop Variant



Separate experiment:



```text

Initial stop = 1 ATR

```



After price reaches:



```text

+1R

```



activate:



```text

1 ATR trailing stop

```



Do not mix this with fixed TP in the same experiment.



\---



\# 28. Time Stop



Because this is a short-term momentum strategy, test:



```text

max holding period

```



5m:



```text

6 candles = 30 min

12 candles = 60 min

24 candles = 120 min

```



1m:



```text

15 min

30 min

60 min

```



If neither TP nor SL is reached:



```text

exit at market / next available candle

```



\---



\# 29. Cooldown



After an exit:



```text

cooldown = 3 candles

```



Do not immediately re-enter the same signal.



Test:



```text

0

3

6

```



\---



\# 30. Position Rules



Initially:



```text

one position per symbol

```



No pyramiding.



No averaging down.



No martingale.



No adding to losing positions.



Maximum:



```text

1 long OR 1 short

```



per symbol.



\---



\# 31. Shorting



All strategies should have:



```text

LONG

SHORT

```



versions.



Do NOT assume symmetry.



Report:



```text

Long-only

Short-only

Long+Short

```



separately.



\---



\# 32. Fees



Backtest must include realistic trading fees.



Create configurable:



```text

maker\_fee

taker\_fee

```



Default to a conservative taker-fee assumption appropriate to the selected exchange/account tier.



Do NOT assume zero fees.



\---



\# 33. Slippage



At minimum test:



```text

0 bps

2 bps

5 bps

10 bps

```



For highly liquid BTC/ETH:



use realistic lower slippage.



For altcoins:



use higher slippage.



Do not use one universal slippage assumption without testing.



\---



\# 34. Funding Cost



For perpetual futures:



include funding payments when a position crosses the funding timestamp.



Do not simply subtract funding every candle.



Funding is event-based according to the underlying exchange schedule.



\---



\# 35. Avoid Lookahead Bias



This is mandatory.



Examples of forbidden behavior:



```text

Using today's completed daily VWAP

to make an earlier intraday decision.

```



Wrong.



Use only the VWAP value available at that timestamp.



Likewise:



```text

Using final candle high

before the candle closes.

```



Forbidden.



\---



\# 36. Baseline Comparisons



Every Shark strategy must be compared against:



\### Baseline A



Buy-and-hold.



\### Baseline B



Random entry with same holding period.



\### Baseline C



Pure breakout:



```text

close > previous\_high\_20

```



without volume filter.



\### Baseline D



Pure volume spike:



```text

RVOL > 2

```



without breakout.



This is extremely important.



The goal is to discover whether:



```text

Volume

```



actually adds information beyond:



```text

Breakout

```



\---



\# 37. Ablation Testing



For every successful strategy, perform:



```text

Full strategy

Full - Volume

Full - CVD

Full - OI

Full - VWAP

Full - OBV

Full - Liquidation

Full - Funding

```



Example:



```text

SHARK-08



vs



SHARK-08 without CVD

```



If performance barely changes, CVD is probably not contributing much.



If removing CVD destroys OOS performance consistently, CVD may contain useful incremental information.



\---



\# 38. Parameter Testing



Do not optimize hundreds of parameters.



Start with:



```text

RVOL:

1.5 / 2 / 2.5 / 3



Breakout:

10 / 20 / 40 candles



CVD:

3 / 5 / 10 candles



OI:

5 / 15 / 30 minutes



ATR stop:

0.75 / 1 / 1.5 / 2



TP:

1.5R / 2R / 3R

```



Keep the parameter grid small.



\---



\# 39. Walk-Forward Testing



Do NOT randomly shuffle time-series data.



Use chronological splits.



Example:



```text

Train:

2023



Validation:

2024



Out-of-sample:

2025



Final unseen:

2026

```



If sufficient data exists, use rolling walk-forward:



```text

Train → Validate → OOS

&#x20;       ↓

move window

&#x20;       ↓

Train → Validate → OOS

```



\---



\# 40. Cross-Asset Validation



A strategy should not only work on one coin.



Test separately:



```text

BTC

ETH

SOL

BNB

XRP

DOGE

ADA

AVAX

LINK

```



Report:



```text

per-symbol

aggregate

median symbol performance

positive-symbol fraction

```



A strategy that only works on one coin should be flagged as potentially asset-specific.



\---



\# 41. Regime Analysis



Split results by:



```text

bull market

bear market

sideways market

high volatility

low volatility

high funding

low funding

high liquidation

low liquidation

```



Use objective definitions.



Example:



```text

ATR percentile > 80%

=

high volatility

```



Do not manually label periods after seeing the results.



\---



\# 42. Metrics



Report at minimum:



```text

Total trades

Win rate

Average win

Average loss

Expectancy

Profit factor

Total return

Annualized return

Maximum drawdown

Sharpe

Sortino

Calmar

Average holding time

Median holding time

Long trades

Short trades

```



Also:



```text

Exposure

Turnover

Fees paid

Funding paid

Slippage cost

```



\---



\# 43. Statistical Validation



For promising strategies run:



```text

Deflated Sharpe Ratio

```



```text

White's Reality Check / equivalent multiple-testing correction

```



```text

Monte Carlo trade reshuffling

```



At minimum:



```text

10000 Monte Carlo simulations

```



Report:



```text

terminal return P05

terminal return P50

terminal return P95



max drawdown P05

max drawdown P50

max drawdown P95

```



Also report:



```text

probability of losing money

```



under the Monte Carlo model.



\---



\# 44. Multiple Testing



This research will test many variants.



Therefore:



DO NOT report:



> "The best strategy made +X%."



without accounting for the number of strategies/parameter combinations tested.



Track:



```text

number\_of\_trials

```



and use appropriate multiple-testing controls.



The purpose is to determine whether the observed edge is distinguishable from data-mining luck.



\---



\# 45. Signal Quality Analysis



For every signal, measure forward returns.



For example:



```text

After RVOL > 2:



5m forward return

10m forward return

15m forward return

30m forward return

60m forward return

```



Do this BEFORE introducing stops and take profits.



This answers:



> Does the signal itself predict anything?



Then separately test:



> Can a trading rule monetize it?



\---



\# 46. Signal Bucket Analysis



Bucket RVOL:



```text

1.0–1.5

1.5–2.0

2.0–2.5

2.5–3.0

3.0–4.0

4.0+

```



For each bucket report:



```text

trade count

mean forward return

median forward return

win rate

max adverse excursion

max favorable excursion

```



Do the same for:



```text

CVD delta

OI change

liquidation ratio

```



This may reveal nonlinear relationships.



\---



\# 47. Important Experiment: Does Volume Actually Matter?



Compare:



```text

A:

breakout only

```



against:



```text

B:

breakout + RVOL > 1.5

```



```text

C:

breakout + RVOL > 2

```



```text

D:

breakout + RVOL > 3

```



If adding volume does not improve OOS expectancy after fees/slippage, discard the volume hypothesis.



Do not force the hypothesis to work.



\---



\# 48. Important Experiment: CVD Incremental Value



Compare:



```text

Breakout

```



vs:



```text

Breakout + Volume

```



vs:



```text

Breakout + Volume + CVD

```



The question is:



```text

Does CVD provide information beyond volume?

```



\---



\# 49. Important Experiment: OI Interpretation



Create a 2x2 matrix:



```text

&#x20;                 OI UP        OI DOWN



Price UP          A             B



Price DOWN        C             D

```



Calculate future returns for every state.



Do NOT assume:



```text

A = bullish

D = bearish

```



until the data demonstrates it.



\---



\# 50. Important Experiment: Liquidation Cascade



Create:



```text

No liquidation spike

Liquidation spike

Extreme liquidation spike

```



Then compare forward returns.



Separate:



```text

long liquidation

short liquidation

```



This determines whether liquidation events are associated with:



```text

continuation

```



or:



```text

reversal

```



rather than assuming either.



\---



\# 51. Important Experiment: Whale Proxy



Create a composite "participation score":



```text

participation\_score =

normalized(RVOL)

\+

normalized(abs(CVD\_delta))

\+

normalized(abs(OI\_change))

\+

normalized(liquidation\_ratio)

```



BUT:



Do NOT immediately trade this score.



First test whether high participation score predicts future volatility/returns.



Then test whether a threshold provides incremental predictive power.



This is an exploratory feature, not a predefined trading strategy.



\---



\# 52. Do Not Overfit "Whale Score"



Never create:



```text

whale\_score > 7.35

```



because that happened to maximize historical profit.



Instead use simple thresholds first:



```text

low

medium

high

extreme

```



and validate them out-of-sample.



\---



\# 53. Execution Model



For every trade record:



```text

signal\_time

entry\_time

entry\_price

exit\_time

exit\_price

direction

quantity

gross\_pnl

fees

funding

slippage

net\_pnl

MFE

MAE

holding\_period

```



\---



\# 54. Trade Attribution



Every trade must record WHY it entered.



Example:



```text

entry\_reason =



RVOL\_BREAKOUT

```



or:



```text

RVOL\_BREAKOUT\_VWAP

```



or:



```text

RVOL\_BREAKOUT\_CVD\_OI

```



This will make later analysis much easier.



\---



\# 55. Recommended Architecture



Separate:



```text

data/

features/

signals/

strategies/

execution/

backtest/

validation/

reports/

```



Suggested Python structure:



```text

shark\_hunter/

│

├── data/

│   ├── loader.py

│   ├── normalization.py

│   └── exchange\_adapters/

│

├── features/

│   ├── volume.py

│   ├── vwap.py

│   ├── obv.py

│   ├── cvd.py

│   ├── open\_interest.py

│   ├── funding.py

│   └── liquidation.py

│

├── signals/

│   ├── breakout.py

│   ├── volume.py

│   └── order\_flow.py

│

├── strategies/

│   ├── shark01.py

│   ├── shark02.py

│   ├── shark03.py

│   ├── shark04.py

│   ├── shark05.py

│   ├── shark06.py

│   ├── shark07.py

│   └── shark08.py

│

├── backtest/

│   ├── engine.py

│   ├── execution.py

│   ├── costs.py

│   └── portfolio.py

│

├── validation/

│   ├── walk\_forward.py

│   ├── monte\_carlo.py

│   ├── dsr.py

│   └── reality\_check.py

│

└── reports/

```



\---



\# 56. Data Versioning



Every backtest must record:



```text

dataset\_version

exchange

symbols

timeframe

start\_date

end\_date

fees

slippage

funding\_model

strategy\_version

parameter\_set

```



This prevents accidentally comparing incomparable experiments.



\---



\# 57. Reproducibility



Every experiment must have:



```text

experiment\_id

random\_seed

git\_commit

strategy\_version

data\_version

```



Save results as machine-readable JSON/CSV.



\---



\# 58. Output Format



Create:



```text

strategy\_summary.csv

trade\_log.csv

parameter\_results.csv

walk\_forward\_results.csv

monte\_carlo\_results.csv

```



Also create a human-readable:



```text

REPORT.md

```



\---



\# 59. Required Report



The final report must answer:



\## Question 1



Does abnormal volume predict short-term continuation?



\## Question 2



Does breakout + volume outperform breakout alone?



\## Question 3



Does CVD add incremental information?



\## Question 4



Does OBV add incremental information?



\## Question 5



Does OI add incremental information?



\## Question 6



Does liquidation data add incremental information?



\## Question 7



Does funding improve the strategy as a filter?



\## Question 8



Does the edge survive transaction costs?



\## Question 9



Does the edge survive OOS testing?



\## Question 10



Does the edge survive multiple-testing correction?



\---



\# 60. Strategy Ranking Policy



Do NOT rank strategies simply by total return.



Create categories:



```text

FAILED

PROMISING

ROBUST

```



But these labels must be based on predefined statistical criteria BEFORE inspecting the final results.



Suggested initial criteria:



\### FAILED



Any of:



```text

negative OOS expectancy

PF <= 1 after realistic costs

severe degradation OOS

unstable across assets

```



\### PROMISING



All of:



```text

positive OOS expectancy

PF > 1

reasonable trade count

survives realistic costs

```



\### ROBUST



Require additional evidence:



```text

positive OOS expectancy

stable across multiple assets

stable across multiple periods

reasonable parameter neighborhood

acceptable drawdown

Monte Carlo robustness

DSR evidence

multiple-testing robustness

```



These labels are research classifications, not guarantees of future profitability.



\---



\# 61. Critical Rule



Do NOT automatically conclude:



```text

"Shark Hunter works."

```



The correct possible conclusions include:



```text

Volume has no edge.

```



```text

Volume works only during high-volatility regimes.

```



```text

CVD adds no incremental information.

```



```text

OI improves breakout confirmation.

```



```text

Liquidation events predict reversal rather than continuation.

```



```text

The apparent edge disappears after fees.

```



```text

The strategy works in-sample but fails OOS.

```



A negative result is a valid research result.



\---



\# 62. Development Order



Implement in exactly this order:



```text

STEP 1

Data loader



STEP 2

5m OHLCV



STEP 3

RVOL



STEP 4

20-bar breakout



STEP 5

SHARK-01



STEP 6

Transaction costs



STEP 7

OOS framework



STEP 8

SHARK-02



STEP 9

CVD



STEP 10

SHARK-03



STEP 11

OBV



STEP 12

SHARK-04



STEP 13

OI



STEP 14

SHARK-05



STEP 15

SHARK-06



STEP 16

Liquidation



STEP 17

SHARK-07



STEP 18

Funding



STEP 19

SHARK-08



STEP 20

Ablation



STEP 21

Walk-forward



STEP 22

DSR



STEP 23

Reality Check



STEP 24

Monte Carlo



STEP 25

1m validation

```



Do NOT skip directly to SHARK-08.



\---



\# 63. First Milestone



The first implementation milestone is ONLY:



```text

5m BTCUSDT

\+

OHLCV

\+

RVOL

\+

20-bar breakout

\+

next-bar execution

\+

1 ATR stop

\+

2R target

\+

fees

\+

slippage

```



This is:



```text

SHARK-01

```



Once SHARK-01 works correctly, expand to the remaining strategies.



\---



\# 64. Final Research Principle



The hypothesis is:



```text

Abnormal participation

&#x20;       ↓

Directional breakout

&#x20;       ↓

Short-term continuation

```



The research question is NOT:



```text

"Can we find whales?"

```



The research question is:



```text

"Can observable abnormal market participation

provide a statistically robust, tradeable edge

after costs and out-of-sample validation?"

```



That is the objective of this project.



\### 我特别建议你让 Codex 遵守这几个原则



\*\*第一，不要一开始就上完整版。\*\*



你真正应该让 Agent 跑出来的第一个结果是：



```text

SHARK-01



RVOL > 2

\+

20-bar breakout

```



如果连这个最原始的假设都没有 edge，就没必要堆 CVD、OI、Funding、Liquidation。



\*\*第二，CVD 我建议优先于 OBV。\*\*



因为 Binance 的公开衍生品数据可以直接提供 taker buy/sell volume，这让 CVD 有比较明确的数据来源，而不是自己从普通 OHLCV 猜主动买卖。(\[Binance Developers]\[1])



\*\*第三，OI 是第二层非常值得测试的变量。\*\*



尤其是你要研究“鲨鱼进场”这种东西，我会特别关注：



```text

Price ↑

Volume ↑

CVD ↑

OI ↑

```



和：



```text

Price ↑

Volume ↑

CVD ↑

OI ↓

```



这两个状态的 \*\*未来 5m / 15m / 30m return distribution\*\* 到底有什么差异。



不要先假定答案。



\*\*第四，Liquidation 是一个很有意思的独立实验。\*\*



因为它可能不是“鲨鱼进场”，而是：



> \*\*鲨鱼先推动价格 → 杠杆仓位爆掉 → liquidation cascade → 进一步推动价格。\*\*



所以 `SHARK-07` 我特意没有把它简单定义成“看到 short liquidation 就做多”。Bybit 现在甚至提供完整 liquidation stream，而不是过去那种低频的 liquidation 推送。(\[Bybit Exchange]\[3])



最后一个重点：\*\*不要让 Codex 把“Volume + CVD + OBV + VWAP + OI + Funding + Liquidation”直接做成一个神策略。\*\* 你之前做 DSR / Reality Check 已经碰到过 multiple-testing 问题了；这次最有价值的其实是做 \*\*ablation\*\*：



```text

Breakout

&#x20;  ↓

\+ Volume

&#x20;  ↓

\+ CVD

&#x20;  ↓

\+ OI

&#x20;  ↓

\+ Liquidation

```



这样最后你才能回答一个真正有意义的问题：



> \*\*到底什么东西在赚钱？\*\*



而不是得到一个“历史回测很漂亮”的黑盒。



如果 Codex 按这个 spec 做，我会把\*\*SHARK-01 → SHARK-08 当成一组实验，而不是 8 个独立的“策略推荐”\*\*。这会非常适合你后面继续接你之前的 OOS + DSR + Reality Check pipeline。



\[1]: https://developers.binance.com/docs/derivatives/coin-margined-futures/market-data/rest-api/Get-Funding-Info?utm\_source=chatgpt.com "Market Data - Futures (COIN-M) REST API | Binance Developer Docs"

\[2]: https://bybit-exchange.github.io/docs/v5/market/open-interest?utm\_source=chatgpt.com "Get Open Interest | Bybit API Documentation"

\[3]: https://bybit-exchange.github.io/docs/zh-TW/v5/websocket/public/all-liquidation?utm\_source=chatgpt.com "完整強平推送 | Bybit API Documentation"



