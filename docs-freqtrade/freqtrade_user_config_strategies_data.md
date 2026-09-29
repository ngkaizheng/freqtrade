对，你可以把 Freqtrade 的“可调东西”理解成 \*\*4 个主要层级\*\*，而不是只有 Strategy + config。



| 层级                  | 主要负责什么                                                   | 你现在是否应该调 |

| ------------------- | -------------------------------------------------------- | -------- |

| \*\*Strategy `.py`\*\*  | Entry / Exit / 指标 / SL / TP / leverage                   | ✅ 核心研究对象 |

| \*\*`config.json`\*\*   | Exchange / Futures / pairs / stake / max trades / 下单方式   | ✅ 必须正确固定 |

| \*\*Backtest CLI 参数\*\* | timerange / fee / timeframe / pairs / starting balance 等 | ✅ 用来做实验  |

| \*\*Data\*\*            | 你到底拿什么历史数据来测试                                            | ✅ 非常重要   |



另外还有 \*\*Hyperopt / Protections / Pairlist\*\*，它们更像是在上述层面之上的实验工具/组件。Freqtrade 官方目前把 backtesting、hyperopt、dry-run、live 等视为不同运行模式；配置文件中的很多 Strategy 参数会覆盖 Strategy 本身的设置。(\[Freqtrade]\[1])



对于你现在这个研究，我建议你把它严格分成：



```text

┌───────────────────────────────────────┐

│ Strategy                              │

│ ------------------------------------- │

│ 什么时候入场                          │

│ 什么时候退出                          │

│ SL / TP                               │

│ 指标                                  │

│ leverage                             │

└───────────────────┬───────────────────┘

&#x20;                   │

┌───────────────────▼───────────────────┐

│ config.json                           │

│ ------------------------------------- │

│ Binance                               │

│ Futures                               │

│ USDT                                  │

│ 哪些交易对                            │

│ 每次下多少钱                          │

│ 同时几仓                              │

│ isolated / cross                      │

│ order type                            │

└───────────────────┬───────────────────┘

&#x20;                   │

┌───────────────────▼───────────────────┐

│ Backtest command                      │

│ ------------------------------------- │

│ 时间范围                              │

│ fee                                   │

│ starting balance                      │

│ timeframe override                    │

│ export                                │

└───────────────────────────────────────┘

```



而且有一个很重要的规则：



> \*\*config > strategy > defaults\*\*



也就是说，如果 Strategy 写：



```python

timeframe = "5m"

```



但 config 或 CLI 又指定了别的 timeframe，最终可能按外部配置/命令执行。官方文档明确说明，配置文件中的值会覆盖 Strategy 中对应的 Strategy Override 参数。(\[Freqtrade]\[2])



\---



\# 1. 你的 Strategy 负责什么？



我们刚才写的：



```text

RegimeVolBreakout5m.py

```



负责：



```text

1H regime

5m breakout

volume

ATR expansion

RSI

ADX



&#x20;       ↓



ENTRY



&#x20;       ↓



ATR trailing stop

1.8% TP

90min time stop

momentum failure



&#x20;       ↓



EXIT

```



也就是说：



> \*\*Strategy = “交易思想”\*\*



你以后研究：



```text

Breakout 24 → 18

Volume 1.30 → 1.50

TP 1.8% → 1.2%

```



这些属于 Strategy。



\---



\# 2. `config.json` 是什么？



这个非常重要。



它不是用来告诉 bot：



> “什么时候买 BTC。”



它是告诉 bot：



> \*\*“在哪个交易环境里运行这个 Strategy。”\*\*



例如：



```json

{

&#x20;   "max\_open\_trades": 5,

&#x20;   "stake\_currency": "USDT",

&#x20;   "stake\_amount": 100,

&#x20;   "trading\_mode": "futures",

&#x20;   "margin\_mode": "isolated",



&#x20;   "exchange": {

&#x20;       "name": "binance",

&#x20;       "pair\_whitelist": \[

&#x20;           "BTC/USDT:USDT",

&#x20;           "ETH/USDT:USDT",

&#x20;           "SOL/USDT:USDT"

&#x20;       ]

&#x20;   }

}

```



大概就是：



> “用 Binance USDT perpetual futures，每次 $100，最多同时 5 个仓位，只交易 BTC/ETH/SOL。”



Futures pair 在 Freqtrade 里采用类似 `BTC/USDT:USDT` 的命名；`trading\_mode` 用 `futures`，而 `margin\_mode` 可设 `isolated` 或 `cross`。(\[Freqtrade]\[3])



\---



\# 3. 对你这个策略，我建议这样写 config



我建议你\*\*不要拿一个 config 既做研究 backtest，又直接拿去 live\*\*。



至少：



```text

user\_data/

├── strategies/

│   └── RegimeVolBreakout5m.py

│

├── config.backtest.json

└── config.dryrun.json

```



这样会干净很多。



\---



\# 4. `config.backtest.json`



这是我建议你现在使用的版本。



```json

{

&#x20;   "max\_open\_trades": 5,



&#x20;   "stake\_currency": "USDT",

&#x20;   "stake\_amount": 100,



&#x20;   "tradable\_balance\_ratio": 0.99,



&#x20;   "dry\_run": true,

&#x20;   "dry\_run\_wallet": 10000,



&#x20;   "cancel\_open\_orders\_on\_exit": false,



&#x20;   "trading\_mode": "futures",

&#x20;   "margin\_mode": "isolated",



&#x20;   "exchange": {

&#x20;       "name": "binance",



&#x20;       "key": "",

&#x20;       "secret": "",



&#x20;       "ccxt\_config": {},

&#x20;       "ccxt\_async\_config": {},



&#x20;       "pair\_whitelist": \[

&#x20;           "BTC/USDT:USDT",

&#x20;           "ETH/USDT:USDT",

&#x20;           "SOL/USDT:USDT",

&#x20;           "BNB/USDT:USDT",

&#x20;           "XRP/USDT:USDT",

&#x20;           "DOGE/USDT:USDT",

&#x20;           "ADA/USDT:USDT",

&#x20;           "AVAX/USDT:USDT",

&#x20;           "LINK/USDT:USDT",

&#x20;           "SUI/USDT:USDT"

&#x20;       ],



&#x20;       "pair\_blacklist": \[]

&#x20;   },



&#x20;   "pairlists": \[

&#x20;       {

&#x20;           "method": "StaticPairList"

&#x20;       }

&#x20;   ],



&#x20;   "entry\_pricing": {

&#x20;       "price\_side": "same",

&#x20;       "use\_order\_book": true,

&#x20;       "order\_book\_top": 1

&#x20;   },



&#x20;   "exit\_pricing": {

&#x20;       "price\_side": "same",

&#x20;       "use\_order\_book": true,

&#x20;       "order\_book\_top": 1

&#x20;   },



&#x20;   "order\_types": {

&#x20;       "entry": "market",

&#x20;       "exit": "market",

&#x20;       "stoploss": "market",

&#x20;       "stoploss\_on\_exchange": false

&#x20;   },



&#x20;   "order\_time\_in\_force": {

&#x20;       "entry": "GTC",

&#x20;       "exit": "GTC"

&#x20;   },



&#x20;   "unfilledtimeout": {

&#x20;       "entry": 10,

&#x20;       "exit": 10,

&#x20;       "unit": "minutes",

&#x20;       "exit\_timeout\_count": 0

&#x20;   },



&#x20;   "internals": {

&#x20;       "process\_throttle\_secs": 5

&#x20;   },



&#x20;   "db\_url": "sqlite:///tradesv3.backtest.sqlite"

}

```



这里最关键的是：



```json

"trading\_mode": "futures"

```



以及：



```json

"margin\_mode": "isolated"

```



因为我们这个 Strategy 有：



```python

can\_short = True

```



所以它不是普通 spot Strategy。



\---



\# 5. 为什么我用 StaticPairList？



这个对你现在的\*\*研究阶段\*\*非常重要。



我建议：



```json

"pairlists": \[

&#x20;   {

&#x20;       "method": "StaticPairList"

&#x20;   }

]

```



而不是：



```text

VolumePairList

MarketCapPairList

PercentChangePairList

```



原因是：



> \*\*你现在要研究 Strategy，而不是研究“历史上哪些币进入了排行榜”。\*\*



Freqtrade 官方也特别提醒，动态 pairlist 在 backtest 中依赖当前市场条件，不能自然代表历史上的 pairlist，因此可能影响可重复性；StaticPairList 更适合做可重复的 backtest。(\[Freqtrade]\[4])



这跟你之前一直做的：



> pre-registration → OOS → DSR → Reality Check



思路是完全一致的。



\---



\# 6. 但是有一个问题：为什么我选这10个？



这里我要特别纠正一下：



\*\*不要把这10个币当成神圣名单。\*\*



它们只是一个方便开始的 liquidity universe。



真正研究的时候，我甚至更建议：



```text

BTC

ETH

SOL

BNB

XRP

```



先跑。



然后：



```text

BTC + ETH + SOL

```



再扩充。



因为如果你一开始放：



```text

30\~100 coins

```



你其实是在同时测试：



```text

Strategy

\+

Asset selection

\+

Liquidity

\+

Volatility regime

```



这样很容易让结果变得难解释。



\---



\# 7. `max\_open\_trades` 也是一个非常重要的参数



比如：



```json

"max\_open\_trades": 5

```



意思不是：



> 最多 5 笔交易一天。



而是：



> \*\*任何时候最多同时 5 个 open trades。\*\*



官方文档也是这样定义的，而且每个 pair 原则上只能有一个 open trade。(\[Freqtrade]\[2])



所以：



```text

BTC  LONG

ETH  LONG

SOL  SHORT

BNB  LONG

XRP  SHORT

```



已经达到：



```text

max\_open\_trades = 5

```



新的信号要等仓位关闭。



\---



\# 8. `stake\_amount`



我给你：



```json

"stake\_amount": 100

```



也就是每笔：



```text

$100

```



假设：



```text

max\_open\_trades = 5

```



那么最多大约：



```text

$500

```



同时进入市场。



这对研究非常方便。



\---



\# 9. 等以后测试 compounding，再考虑 unlimited



Freqtrade 支持：



```json

"stake\_amount": "unlimited"

```



这种模式会把可用余额按 `max\_open\_trades` 分配，而且 backtesting/dry-run 都会跟着余额变化产生复利效果。官方文档明确说明这种设置会让后续 stake 随资金变化。(\[Freqtrade]\[2])



但是：



\*\*我现在不建议你用。\*\*



因为我们当前的问题是：



> Strategy 有没有 edge？



不是：



> 复利以后能不能变成 30000%。



先固定：



```text

$100 / trade

```



会更干净。



\---



\# 10. Fee 怎么办？



这里特别重要。



你的 backtest：



```bash

freqtrade backtesting ...

```



Freqtrade 默认会使用 exchange 的默认手续费，也可以用：



```bash

\--fee

```



强制指定手续费，而且官方说明这个 fee ratio 会在 entry 和 exit 各应用一次。(\[Freqtrade]\[4])



例如：



```bash

\--fee 0.0006

```



就是：



```text

0.06% entry

0.06% exit

```



总 round trip：



```text

0.12%

= 12 bps

```



而你之前的研究一直采用：



> \*\*12 bps round-trip\*\*



所以如果你想让这个 Freqtrade 回测和你之前的研究严格一致：



```bash

\--fee 0.0006

```



非常重要。



\---



\# 11. 所以你的第一次 backtest，我会这样跑



假设：



```text

Strategy:

RegimeVolBreakout5m



Config:

config.backtest.json



Pair:

BTC ETH SOL BNB XRP ...

```



可以：



```bash

freqtrade backtesting \\

&#x20;   --config user\_data/config.backtest.json \\

&#x20;   --strategy RegimeVolBreakout5m \\

&#x20;   --timeframe 5m \\

&#x20;   --fee 0.0006 \\

&#x20;   --timerange 20240101-20251231 \\

&#x20;   --dry-run-wallet 10000 \\

&#x20;   --export trades

```



Freqtrade 当前 backtesting CLI 支持 `--strategy`、`--timeframe`、`--timerange`、`--fee`、`--pairs`、`--max-open-trades`、`--stake-amount`、`--dry-run-wallet` 等覆盖参数。(\[Freqtrade]\[4])



\---



\# 12. 甚至 config 都不是最终控制层



比如 config：



```json

"max\_open\_trades": 5

```



但你运行：



```bash

freqtrade backtesting \\

&#x20;   ... \\

&#x20;   --max-open-trades 2

```



那么这次实验就是：



```text

max\_open\_trades = 2

```



而不是 5。



同样：



```bash

\--fee 0.0008

```



就可以快速做：



```text

12 bps

16 bps

20 bps

```



的成本压力测试。



这对你的研究特别有用。



\---



\# 13. 你其实可以把整个 Freqtrade 实验看成这些东西



```text

&#x20;                    Freqtrade Experiment

&#x20;                             │

&#x20;       ┌─────────────────────┼──────────────────────┐

&#x20;       │                     │                      │

&#x20;       ▼                     ▼                      ▼

&#x20;  STRATEGY                CONFIG                 DATA

&#x20;       │                     │                      │

&#x20;       │                     │                      │

&#x20;Entry / Exit           Exchange                 OHLCV

&#x20;Indicators             Futures                  5m

&#x20;Stoploss               Margin                   1h

&#x20;TP                     Pairs                    Funding\*

&#x20;Leverage               Stake

&#x20;                       Max trades

&#x20;                       Orders

&#x20;                             │

&#x20;                             ▼

&#x20;                       BACKTEST CLI

&#x20;                             │

&#x20;             ┌───────────────┼────────────────┐

&#x20;             ▼               ▼                ▼

&#x20;         Timerange          Fee          Starting balance

```



\* Funding 数据如果 Strategy 自己读取的话，是额外数据源。



\---



\# 14. 对你目前的研究，我建议“哪些固定，哪些允许调”



这个其实比怎么写 config 更重要。



\### 第一阶段：完全不优化



固定：



```text

Strategy parameters   ✅ 固定

Pair universe         ✅ 固定

Fee                   ✅ 固定 12 bps

max\_open\_trades       ✅ 固定

leverage              ✅ 1x

Timeframe             ✅ 5m

```



只改变：



```text

OOS date

```



目的：



> \*\*判断这个 idea 有没有生命。\*\*



\---



\### 第二阶段：Cost Stress



Strategy 不变。



只改：



```text

12 bps

16 bps

20 bps

30 bps

```



你会得到：



```text

&#x20;               Net Expectancy

12 bps ──────────────── +

16 bps ───────────────  ?

20 bps ──────────────   ?

30 bps ────────────     -

```



这实际上非常有价值。



\---



\### 第三阶段：Universe robustness



先：



```text

BTC ETH SOL

```



然后：



```text

BTC ETH SOL BNB XRP

```



然后：



```text

10 assets

```



看 edge 是否仍然存在。



\---



\### 第四阶段才 Hyperopt



这里是很多人犯错的地方。



不要：



```text

BACKTEST

&#x20;  ↓

LOSS

&#x20;  ↓

HYPEROPT 5000 epochs

&#x20;  ↓

SHARPE 4.8 🎉

```



而应该：



```text

固定 hypothesis

&#x20;       ↓

baseline

&#x20;       ↓

OOS

&#x20;       ↓

验证有 edge

&#x20;       ↓

只允许少数参数优化

&#x20;       ↓

再次 OOS

&#x20;       ↓

DSR / Reality Check

```



\---



\# 15. 还有一个东西你现在应该加入：`lookahead-analysis`



这个我非常建议你跑。



因为 Freqtrade 官方明确提供：



```bash

freqtrade lookahead-analysis

```



来检查 Strategy 是否不小心使用未来数据。官方文档也特别警告，backtesting 是把整个 dataframe 一次性传给 `populate\_\*()`，所以不正确的 dataframe 操作很容易产生 lookahead bias。(\[Freqtrade]\[1])



我们刚才这个策略已经特意用了：



```python

.shift(1)

```



比如：



```python

dataframe\["breakout\_high"] = (

&#x20;   dataframe\["high"]

&#x20;   .shift(1)

&#x20;   .rolling(24)

&#x20;   .max()

)

```



这是为了避免：



```text

当前 candle

&#x20;  ↓

自己定义自己的 breakout level

```



但我仍然会让工具验证它，而不是相信我们自己。



\---



\# 16. 你现在真正需要准备的其实只有 3 个文件



```text

user\_data/

│

├── strategies/

│   └── RegimeVolBreakout5m.py

│

├── config.backtest.json

│

└── config.dryrun.json

```



然后：



```text

Strategy

&#x20;  ↓

config

&#x20;  ↓

historical data

&#x20;  ↓

backtesting

&#x20;  ↓

lookahead-analysis

&#x20;  ↓

OOS

&#x20;  ↓

stress

```



这就已经是一套相当完整的研究环境了。



\---



\### 还有一个我认为对你很重要的设计决定



\*\*不要把 `fee`、`pairs`、`max\_open\_trades`、`timerange` 这些实验变量偷偷写死在 Strategy 里。\*\*



例如不要：



```python

PAIR\_LIST = \[...]

FEE = ...

```



Strategy 应该尽量描述：



> \*\*“价格行为假设。”\*\*



而 config / CLI 描述：



> \*\*“实验环境。”\*\*



这样以后你才能很干净地回答：



> “策略本身有效，还是只是因为我选择了某一批币、某一种 fee、某一个时间段？”



这正是你现在这套 \*\*pre-registration → OOS → DSR → Reality Check\*\* 研究方法最需要的结构。



另外，StaticPairList 目前是 Freqtrade 官方支持的标准 pairlist，并且可通过 `exchange.pair\_whitelist` 配置；Binance Futures 当前还需要注意 orderbook 定价设置，官方 exchange notes 对 Binance Futures 明确建议使用 order book。(\[Freqtrade]\[5])



\[1]: https://docs.freqtrade.io/en/2026.8/strategy-customization/?utm\_source=chatgpt.com "Strategy Customization - Freqtrade"

\[2]: https://docs.freqtrade.io/en/2026.3/configuration/?utm\_source=chatgpt.com "Configuration - Freqtrade"

\[3]: https://docs.freqtrade.io/en/latest/leverage/?utm\_source=chatgpt.com "Short / Leverage - Freqtrade"

\[4]: https://docs.freqtrade.io/en/stable/backtesting/?utm\_source=chatgpt.com "Backtesting - Freqtrade"

\[5]: https://docs.freqtrade.io/en/2026.5/plugins/?utm\_source=chatgpt.com "Plugins - Freqtrade"



