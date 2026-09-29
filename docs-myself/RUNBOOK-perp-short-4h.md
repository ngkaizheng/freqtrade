# RUNBOOK — PerpShort4h（4h 永续做空突破）

**策略文件：** `user_data/strategies/PerpShort4h.py`
**配置：** `user_data/config_perp_short.json`（24 币）/ `config_perp_short_104.json`（104 币）
**结论与数据：** `docs-myself/PERP_SHORT_4H_RESULT_2026-09-28.md`

---

## 0. 先读这一段：它是什么，不是什么

| 是 | 不是 |
|---|---|
| 一条**规则固定**的 4h 做空突破策略，104 个永续合约 | 一个通过验证的 alpha |
| 毛收益 +134%，扛得住实测成本档的前半段 | 扛得住最坏成本档（见 §5） |
| 一套**会自己拒绝错误答案**的闸门 | 一条能直接上真钱的曲线 |
| 预注册门槛**已判定不通过**（104 币在 COVID 成本下为负，4 年里 1 年为正） | —— |

> **它是本项目里唯一一个「被完整拆开量过、然后诚实地判定为不通过」的策略。**
> 在拿真钱之前，请至少读完 §5 和 §6。

---

## 1. 规则（冻结，不要改）

```
入场  rvol(20) >= 2.0
     且 收盘价 < 前 20 根的最低价（不含当根）
     且 低波动 regime：vol42 < vol42 在过去 365 根的中位数
止损  入场价 + 1.5 x ATR(入场那根 K 线)     ← 关键：锚在入场 bar，不是当前 bar
止盈  入场价 − 2.0 x (止损距离)             ← 即 2R
时间止损  持满 42 根 4h K 线（约 7 天）
```

只有 `low_vol` 这一个过滤器，来自 Kurth et al. arXiv:2607.01550（**预印本，未同行评议**）。

---

## 2. 跑回测

```powershell
# 24 币（快，约 4 分钟）
.venv\Scripts\python.exe -m freqtrade backtesting `
  --config user_data\config_perp_short.json `
  --datadir user_data\data\wide_ft `
  --strategy-path user_data\strategies `
  --strategy PerpShort4h `
  --timerange 20230101-20260928 `
  --cache none

# 104 币（慢，约 7 分钟，内存约 1.5 GB）
.venv\Scripts\python.exe -m freqtrade backtesting `
  --config user_data\config_perp_short_104.json `
  --datadir user_data\data\wide104 `
  --strategy-path user_data\strategies `
  --strategy PerpShort4h `
  --timerange 20230101-20260928 `
  --cache none
```

### ⚠ 四个必踩的坑（都不是我猜的，是本仓库实际踩过的）

1. **`--datadir` 必须用命令行传。** 配置文件里的 `"datadir"` 会被**无条件覆盖**
   （`configuration.py:212`），写成 `"datadir": "xxx"` 只会静默读错数据、不报错。
2. **数据目录是「扁平」布局。** 文件名是
   `<datadir>/futures/<BASE>_<QUOTE>_<SETTLE>-<tf>-futures.feather`，
   **pair 在前、timeframe 在后**（`idatahandler.py:354-371`）。写反了不会报错，
   只会「No data found」。
3. **104 币的 1h mark 是用 4h K 线重采样近似的，只在 1x 有效。**
   mark 价格只用来算爆仓价，1x 下 3.6% 的止损远早于 ~100% 的爆仓。
   **杠杆 > 1x 时这套数据是无效的，会伪造出爆仓。** 要上杠杆必须先下真实 mark 数据。
4. **futures 模式强制要求 funding 和 mark，缺一个直接崩**（`backtesting.py:428,441`
   的 `fail_without_data=True`）。这一点是好事——它是响的，不是静默的。

---

## 3. 跑三道闸门（**任何结果在通过之前都不算数**）

```powershell
# 闸门 1：止损是否真的按 1.5xATR(入场) 生效
.venv\Scripts\python.exe -m freqtrade backtesting --config ... --export trades `
  --export-directory user_data\perp_short_out
.venv\Scripts\python.exe tools\perp_short\verify_stop.py

# 闸门 2：因果性（截断重算，比引擎自带的 lookahead-analysis 更强）
.venv\Scripts\python.exe tools\perp_short\test_causality.py

# 闸门 3：成本前沿 + R 统计
$env:PERP_SHORT_DATADIR="user_data/data/wide104"
.venv\Scripts\python.exe tools\perp_short\cost_frontier.py
.venv\Scripts\python.exe tools\perp_short\r_stats.py
```

`verify_stop.py` 会从**成交明细**反查每笔止损的实际价格。
**不要用读代码代替它**——本仓库那个「3 个月前的 ATR」就是这么抓到���，
读代码是读不出来的（见结果文档 §1）。

---

## 4. 参数怎么定

配置里三个数决定了你实际在赌什么：

```jsonc
"perp_leverage": 1.0,     // 杠杆。1x 之外先读下面的警告
"risk_per_trade": 0.01,   // 每笔拿总权益的 1% 去赌一个 R
"max_stake_frac": 0.25    // 单个仓位不超过总权益的 25%
```

**组合风险预算 = `risk_per_trade` × `max_open_trades`**。
10 个仓位 × 1% = **所有止损同时被打也只亏 10%**。
先定这个乘积，再拆成两个数。

> **⚠ `max_stake_frac` 会吃掉波动率定仓。** 本面板 1.5×ATR% 的中位数是 3.61%，
> 于是 `risk_per_trade / (1.5 × atr_pct)` ≈ 0.28，**几乎总是被 0.25 的上限截住**，
> 等于退化成固定 25% 仓位。想让波动率定仓真正起作用，把 `max_stake_frac` 调大，
> 改用 `risk_per_trade` 控风险。（回测里 24 币和 104 币的 `max_open_trades`
> 分别是 24 和 104，**交易数完全相同**，所以仓位数量不是约束。）

**杠杆警告：** `RESEARCH_STATE.md` 的杠杆矩阵已经量过——收益大致随 L 线性增长，
回撤涨得更快；**手续费在 36x 附近就等于整个 3.6% 的止损**；20x 时一笔止损吃掉
72% 的保证金，一个「所有仓位同时止损」的事件要掉 69% 的账户。
**约束是破产，不是收益。**

---

## 5. 成本现实（本项目实测，不是拍的）

freqtrade 的回测器**没有滑点模型**，`docs/backtesting.md:562` 原文：
*"All orders are filled at the requested price (no slippage)"*，
`:571`：*"Stoploss exits happen exactly at stoploss price, even if low was lower"*。
**所以它印出来的每个净值都是上界。**

本仓库用 Binance 真实盘口深度（30 秒快照）实测的往返成本：

| 档 | 往返 | 日期 |
|---|---:|---|
| 平静 | 12.0 bps | 2026-09-20 |
| 长尾崩塌 | 15.6 bps | 2024-08-05 |
| 波动 | 22.8 bps | 2025-10-10 |
| COVID 崩盘 | **34.9 bps** | 2020-03-12 |

**结果（104 币）：** 毛 +134.4% → 平静 +36.4% → 波动 +4.5% → **COVID −22.4%**。
**24 币：** 毛 +144.3% → 平静 +75.0% → 波动 +48.6% → **COVID +23.7%**。

> **⚠ 104 币那一行的成本是统一 bps，而长尾的真实盘口比 BTC 薄 1–3 个数量级
> （`RESEARCH_STATE.md` §1b）。也就是说 104 币的真实成本比表里更高，
> 方向只会更差。24 币那行相反——它偏保守。**

---

## 6. 判决（照抄，不要重新解释）

预注册门槛 `PREREG_104_FT_COSTS_2026-09-28.md`，跑数字之前冻结：

| 门槛 | 104 币 | 24 币 | 判定 |
|---|---|---|---|
| G1 t ≥ 2.0 @COVID 成本 | −0.17 | 0.24 | **FAIL** |
| G1b t ≥ 2.0 @平静 | 0.53 | 0.92 | **FAIL** |
| G2 净 R > 0 @COVID | **−0.016** | +0.028 | **FAIL（104）** |
| G3 个体为正的币 ≥ 50% | **42%** | 62% | **FAIL（104）** |
| G4 去掉最好的币仍为正 | 通过 | 通过 | PASS |
| G5 4 年中 ≥3 年为正 | **1/4** | 2/4 | **FAIL** |

**分年（104 币，COVID 成本）：** 2023 −37.5% ｜ 2024 **+86.8%** ｜ 2025 −12.7% ｜ 2026 −24.9%

**R 的定义**（与仓位大小无关）：`该笔净盈亏 ÷ 该笔若精确停在自身冻结止损上会亏掉的美元`。
**不是**除以固定的「权益 1%」——那样在波动率上限生效时会把低波动币算得虚高。

---

## 7. 为什么它没抓住最大的那类行情（已预注册的下一条线）

同期等权买入持有，**104 个币的中位数是 −80.9%**。
**一个做空账，标的跌了 80%，策略在 COVID 成本下还亏 22%**——
因为冻结规则**在 2R（约 +7.2%）就落袋**。

出口拆解（104 币，COVID 成本）：

| 出口 | 笔数 | 盈亏 |
|---|---:|---:|
| 2R 止盈 | 307 | +566,863 |
| 时间止损 | 88 | +38,447 |
| 止损 | 713 | **−627,456** |

**⚠ 这是一个「看到结果之后」才想到的假设。**
`PREREG_TARGET_R_2026-09-28.md` 在跑任何数字之前就冻结了，规定：
`target_r ∈ {1.5, 2, 3, 5, 10, 无}`，**整条曲线都要公布，不许挑一个格子**，
而且**写明：即使某个格子通过，也只是 lead 不是确认**——
因为假设是从这个样本上长出来的。

---

## 8. 还想继续往下走，先读这些（都别重复踩）

`docs-myself/RESEARCH_STATE.md` 里已经付费买过票的坑：

- **`entry_atr` 的 fallback 必须用 `iloc[-1]`**——入场那根 K 线上分析帧还没推进到那根，
  按时间戳查必然 miss。原来用 `iloc[0]`（最老的一根）会拿到 3 个月前的 ATR，
  **而止损只会收紧不会放宽，这个错永远纠不回来**。
- **退出原因里 `custom_stoploss` 设的止损叫 `trailing_stop_loss`**，不叫 `stop_loss`。
  按 `== "stop_loss"` 统计会得到「止损一次都没触发」的错误结论。
- **`--export-directory` 的路径不能带小数点。** `frontier_out\1.5` 会被当成
  `1` + 扩展名剥掉，回测跑完导出全丢。
- **别用 mtime 挑回测归档**，两个策略写同一个目录时会挑到别的运行。
- **绝不要把 `strategy-updater` 指向 `user_data/strategies/`**，
  它会把里面所有手工维护的研究策略全部重写。

---

## 9. 如果要上 dry-run

```powershell
Copy-Item user_data\config_perp_short.json user_data\config_perp_short_dry.json
# 把 dry_run_wallet 改成你真实的模拟金额，exchange.key/secret 留空
.venv\Scripts\python.exe -m freqtrade trade --config user_data\config_perp_short_dry.json
```

**dry-run 的前提：**
- 账户至少能承受 `risk_per_trade × max_open_trades` 的**全部止损同时被打**。
- **先跑满一个完整的低波动 regime 周期再决定要不要加钱**——
  过滤器只在低波动时开仓，高波动时它是空仓的，而空仓正是它保护你的方式。
- **不要用回测的净值曲线做预期。** 引擎没有滑点，实测成本表在 §5。
