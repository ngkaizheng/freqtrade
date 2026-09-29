# 交付物规格：4h 永续空头账本（可复现的完整记录）

日期：2026-09-30 · 状态：**已部署、已验证、dry-run 运行中**
· 本文是**自包含**的：不点开其它文件也能照着复现。

---

## 1. 交付的是什么（一句话）

**在流动性窄的加密永续宇宙上、做空「放量下跌时段」的系统择时工具。**
**不是选币 alpha**（中性化后超额为负）。详见 §8。

## 2. 文件清单（要跑的就是这些）

| 角色 | 路径 | 说明 |
|---|---|---|
| **部署策略** | `user_data/strategies/PerpShort4hDeploy.py` | 继承冻结基线，**只加了一个回撤熔断** |
| **冻结基线** | `user_data/strategies_frontier/PerpShort4hStop.py` | 止损倍数从配置读，其余继承 |
| **信号本体** | `user_data/strategies/PerpShort4h.py` | **冻结，勿改** |
| **配置** | `user_data/config_perp_forward_dry.json` | **一字不改即为部署配置** |
| **数据** | `user_data/data/wide526/futures/` | 515 币 × (4h klines + 1h funding + 1h mark)，1,545 文件 / 224 MB |
| **一键检查** | `tools/perp_short/release_check.py` | 验证交付物仍然完好 |

**策略血统（改任何一层都会让结果不可比）：**

```
PerpShort4h                 冻结信号本体：放量破位 + 低波过滤，止损/目标/时间止损
   └─ PerpShort4hStop       冻结基线：止损倍数 = 配置的 atr_stop（部署 = 4.0）
        └─ PerpShort4hDeploy   部署版：+ 回撤熔断 breaker（唯一的新增）
```

`user_data/strategies/PerpShort4hStrength.py`（rvol≥3.0）和 `PerpShort4hSwitch.py`
是**已否定的研究分支，不是部署物**（见 §8.3）。

> ✅ **三层的路径是从 `__file__` 解析的，所以在任何工作目录下都能启动**
> （2026-09-30 修正）。之前用的是两行**相对** `sys.path.insert`，从仓库根目录以外启动
> 会直接 `ModuleNotFoundError: No module named 'PerpShort4hStop'`——已实测，不是推测。
> 改的只是 import 前导，**策略逻辑一个字节没动**，11 道闸门改后重跑全绿。


## 3. 配置全文（部署版，一个字节都没改）

```json
{
  "max_open_trades": 24,
  "stake_currency": "USDT",
  "stake_amount": "unlimited",
  "tradable_balance_ratio": 0.99,
  "dry_run": true,
  "dry_run_wallet": 10000,
  "trading_mode": "futures",
  "margin_mode": "isolated",
  "liquidation_buffer": 0.05,
  "perp_leverage": 1.0,
  "risk_per_trade": 0.005,
  "max_stake_frac": 0.25,
  "unfilledtimeout": { "entry": 10, "exit": 10, "exit_timeout_count": 0, "unit": "minutes" },
  "entry_pricing": { "price_side": "other", "use_order_book": true, "order_book_top": 1,
                     "price_last_balance": 0.0,
                     "check_depth_of_market": { "enabled": false, "bids_to_ask_delta": 1 } },
  "exit_pricing":  { "price_side": "other", "use_order_book": true, "order_book_top": 1,
                     "price_last_balance": 0.0 },
  "exchange": {
    "name": "binance",
    "key": "", "secret": "",
    "pair_whitelist": [ /* 40 个，按中位成交额降序；顺序是决策，不是格式 */ ],
    "pair_blacklist": [],
    "pairlists": [ { "method": "StaticPairList" } ]
  },
  "dataformat_ohlcv": "feather",
  "datadir": "E:\\FreqTrader\\freqtrade\\user_data\\data\\wide526",
  "fee": 0.0005,
  "logfile": "user_data/logs/forward_perp.log",
  "db_url": "sqlite:///user_data/forward_perp.dryrun.sqlite",
  "timeframe": "4h",
  "initial_state": "running",
  "strategy": "PerpShort4hDeploy",
  "strategy_path": "user_data/strategies",
  "atr_stop": 4.0,
  "breaker_max_dd": 0.20,
  "breaker_cooldown_bars": 42,
  "exportfilename": "user_data/forward_exports"
}
```

**白名单（前 10 个，完整 40 个见配置文件）：**
BTC · ETH · SOL · XRP · DOGE · 1000PEPE · HYPE · BNB · SUI · WIF · … · GALA

### ⚠ 配置里四个必须存在的键（每一个都对应一次真实故障）

| 键 | 写错会怎样 |
|---|---|
| `db_url` | 写成 `database_url` → **freqtrade 不报错**，静默打开仓库根目录的旧 DB，里面有未平仓的模拟交易，于是拒绝启动 |
| `initial_state: "running"` | 缺它 → **进程活着、每 60 秒心跳、状态停在 STOPPED**。这是本项目最危险的一种故障：**它不产出任何数字，只看起来健康** |
| `timeframe: "4h"` | 缺它会用类默认值，**恰好也是 4h**，所以看不出问题，但任何一次配置漂移都会静默生效 |
| `atr_stop: 4.0` | **类默认值是 1.5。** 缺它会静默收集一个**完全不同的策略**的数据 |

**改动任何一项之后必须重启进程**——freqtrade 只在启动时读一次配置。
`verify_collector.py` 会打印「运行中的进程」与「磁盘配置」的币数并比对。

## 4. 怎么跑

```powershell
# 1) 回测（就是部署配置本身）
.venv\Scripts\python.exe -m freqtrade backtesting `
  --config user_data\config_perp_forward_dry.json `
  --datadir user_data\data\wide526 `
  --timerange 20230101-20260928 --cache none

# 2) 模拟盘（无凭证、无真实订单）
.venv\Scripts\python.exe -m freqtrade trade --config user_data\config_perp_forward_dry.json

# 3) 确认交付物完好（一条命令）
.venv\Scripts\python.exe tools\perp_short\release_check.py
```

**内存**：所有回测走 `tools/perp_short/run_capped.ps1 -CapGB 4`。
**实测峰值 119 MB**，远低于 4 GB 上限。

## 5. 实测表现（部署配置，N=40，每笔 0.5%）

**1,111 笔 · 2023-03-22 → 2026-08-31 · 起始 10,000**

| 成本档 | 往返 bps | 总收益 | CAGR | Sharpe | PF | 胜率 |
|---|---:|---:|---:|---:|---:|---:|
| 引擎默认 | 10.0 | +113.7% | 24.8% | 2.62 | 1.36 | 52.8% |
| 实测平静 | 12.0 | +111.9% | 24.5% | 2.58 | 1.36 | 52.7% |
| 实测 COVID（压力端） | **34.9** | **+90.3%** | **20.7%** | **2.10** | **1.28** | **51.8%** |
| 横截面公开基准 | 70.0 | +57.3% | 14.1% | 1.37 | 1.17 | 50.1% |
| 毛（零成本） | 0 | +123.1% | — | — | — | — |

**分年（COVID 档）：2023 +8.3% ｜ 2024 +23.4% ｜ 2025 +31.7% ｜ 2026 +8.2% —— 4/4 年为正。**

**引擎盯市最大回撤 14.16%**（不是 47%；47% 是 1% 风险下的旧数字）。

**风险档实测六档——0.5% 是收益峰值：**

| 每笔风险 | 交易数 | 实测 COVID 收益 | 引擎回撤 | 最差滚动 12m |
|---:|---:|---:|---:|---:|
| 0.25% | 1,192 | +50.7% | 8.15% | +3.8% |
| **0.50%（部署）** | **1,111** | **+90.3%（峰值）** | **14.16%** | **+5.6%** |
| 0.75% | 922 | +69.6% | 25.04% | −0.4% |
| 1.00% | 778 | +78.1% | 28.15% | +0.3% |
| 1.50% | 636 | +83.3% | 32.76% | −4.9% |

**超过 0.5% 之后，加风险买到的是更多回撤，不是更多收益**——
因为约束是「24 个槽位」和「可用余额」这两个天花板在 0.5% 处交叉。

**对照：同一窗口同一 40 币的等权买入持有，均值 −7.1%、中位 −48.5%、仅 35% 为正。**

## 6. 策略逻辑（`PerpShort4h.py` 冻结部分）

```
三条件合取（全部为因果，Donchian 与波动中位数都 shift(1)）：
    rvol   = volume / volume_sma(20)          >= 2.0     放量
    close  < low.rolling(20).min().shift(1)              20 根 bar 破位
    vol42  < vol42.rolling(365).median().shift(1)         低波动过滤

出场：
    止损   = 入场价 + 4 × ATR(14, 入场 bar)
    目标   = 入场价 − 2R
    时间止损 = 持有 42 根 bar（7 天）
    熔断   = 回撤 ≥ 20% 时，停止入场 42 根 bar（仅 PerpShort4hDeploy 有）
```

**回撤熔断的坑**：`bot_loop_start` 在回测里**会被调用多次**，
用它初始化状态会让熔断**永远不触发**（回测却照常打印 +78% 的正常曲线）。
`PerpShort4hDeploy` 用**惰性单次初始化**。另外 `custom_stoploss` 抛出的异常会被
freqtrade 吞掉并**放行**——所以熔断自己记录触发次数，运行后要检查 `breaker_trips` 非零。

## 7. 验证（全部可复算）

```powershell
tools/perp_short/verify_stop.py        # 383 笔止损全部落在 4×ATR，容差 0.40%，零笔落到兜底
tools/perp_short/test_causality.py     # 截断重算，指标逐位一致
tools/perp_short/beta_check.py         # 基准线：永远做空等权面板
tools/perp_short/state_gate.py         # 状态文件与其源一致、113+ 链接全部有效
tools/perp_short/tool_paths_gate.py    # 每个在用工具指向的面板能读部署宇宙
tools/perp_short/stop_fill.py <zip>    # 334 笔止损：跳空 0 次，最险余量 0.081%
tools/perp_short/cost_reprice.py <zip> # 重定价，且必须先复现引擎（0.00 pp）
tools/perp_short/release_check.py      # 以上 + 配置逐字段 + 采集器 + 页面数字一致性
```

**成本数字的来源**：freqtrade 自己的 5 bps/边**低估了实测成本**。
真实往返成本按 regime 分档为 **12.0 / 15.6 / 22.8 / 34.9 bps**（本仓库实测）。
`cost_reprice.py` 用「引擎费用 × 倍数」计价，**在引擎自己的成本上精确复现引擎**，
因此它的其它成本档也可信。

## 8. 边界（必须一起读，否则会误用）

**8.1 它是择时工具，不是 alpha。**
市场中性化后超额**为负**（N=25 处 −1.300%，t=−2.54）。

**8.2 它不统计显著，而且这在本样本上不可证伪。**
t ≈ 0.58。原因是量出来的：成本只占毛值 11%（不是瓶颈）、
**77% 的单笔 R 方差是共同因子**、横截面在**每个周期上都是单一因子**
（50–99 币只值约 3 个独立下注）。**最终保留集已于 2026-09-26 烧毁。**

**8.3 已被否定的分支（保留作为可复现的反证，不要当成交付物用）**

| 分支 | 结果 |
|---|---|
| `PerpShort4hSwitch`（牛市加多头腿） | +52.4% → **−58.7%**，2023 比要修的 −40.5% 更差 |
| `PerpShort4hStrength`（只做 rvol≥3.0） | 组合 t 从 0.58 → **0.36**，收益 +90.3% → **+29.0%** |
| 宇宙放到全部 439 币 | **−34.1%**（实测成本） |
| 加杠杆超过 **3×** | 几何上限：高波动新币（WIF 2.64×）的止损先于爆仓被吃掉 |

**8.4 数字的口径别混：**
* **成本**（12–35 bps）和**执行**（止损跳空）是两件事，可加、不可替代；
* **前瞻收益上的 t**（Q-1 的 −4.37）和**组合 t**（0.36）不是同一个统计量；
* **净值曲线上的 Sharpe** 和**按时间戳的 t** 也不是同一个。
* `HOW_TO_RUN` §5b 的 89% 在水下是 **N=50/1% 档**；部署版 N=40/0.5% 是 **81.8%**。

## 9. 现状

* **dry-run 正在运行**（PID 随重启变化），`dry_run: true`，**凭证为空**。
* **0 笔成交**属正常：实测事件率 40 币 1.62 次/天，
  `verify_collector.py` 会按已运行时长算出期望值并判断沉默是否合理。
* **前瞻检验需要 6.8 年。** 期间**不要改配置**——改了会污染序列。
