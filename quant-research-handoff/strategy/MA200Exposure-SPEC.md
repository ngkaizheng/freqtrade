# Strategy Specification: MA200Exposure

> **状态**：生产候选（仅最简 baseline）
> **来源**：本研究项目 H1–H3（全部预注册实验）
> **撰写时间**：2026-09-17
> **目标平台**：FreqTrader（dry-run / paper → forward testing）

---

## 1. 策略陈述

**核心思想**：不预测崩盘，而是**管理市场暴露（exposure）**。

| 市场状态 | 目标股票暴露 |
|---|---|
| `Close > MA200` | **100%** |
| `Close < MA200` | **50%** |

- **MA200** = 200 个交易日简单移动平均（SMA），基于**日收盘价**（复权）
- **纯状态映射**，无路径依赖、无状态记忆：`暴露 = f(Close, MA200)`
- 无额外信号、无分层、无择时叠加

### 这是什么，不是什么

| ✅ 是 | ❌ 不是 |
|---|---|
| 暴露管理规则 | 崩盘预测器 |
| 风险控制层 | alpha 生成器 |
| 经历史验证的回撤削减 | 收益增强策略 |

---

## 2. 为什么只有这一条规则

这是 H1–H3 三个预注册实验的结论，**每一条被排除的规则都有预注册记录**：

| 实验 | 假设 | 结果 | 是否纳入 |
|---|---|---|---|
| H1 | `MA50<MA200` 慢确认替代 `Close<MA200` | **部分支持**：换手降 75-88%，但回撤保护跨期不稳定 | ❌ 不纳入 |
| H2 | `Close<MA200`→75%、`MA50<MA200`→50% 分层 | **不支持**：两信号 75-78% 同步，分层退化为延迟 | ❌ 不纳入 |
| H3 | 叠加波动率/信用/广度信号进一步降险 | **不支持**：方向相反（信号指向超跌反弹），且未超出安慰剂 | ❌ 不纳入 |

> ⚠️ **不要因为"研究做了三个实验"就觉得生产策略必须复杂。**
> 被排除的三条规则都是**在严格实验下失效**的，把它们加回来会重新引入
> "看起来很聪明，但不知道到底是什么产生了结果"的问题。

---

## 3. 证据摘要（生产规则的历史表现）

来源：`results/`、`outputs/`。样本 SPY 1993-2026（33.6 年），含 2000 / 2008 崩盘。

| 指标 | 一直持有 | MA200 → 50% |
|---|---:|---:|
| CAGR | 10.81% | 7.49% |
| Sharpe | 0.77 | 0.70 |
| **最大回撤** | **-55.19%** | **-30.13%** |
| 恢复天数 | 1773 | 2706 |
| 换手 | 0 | 6.39 |

### 这个规则真正有用的地方：崩盘保护

| 期间 | 一直持有 | MA200 → 50% |
|---|---:|---:|
| 2000-2002 互联网泡沫 | -36.93% | -20.26% |
| **2008-2009 金融危机** | **-19.43%** | **+16.97%** |
| 2022 加息熊市 | -18.65% | -14.98% |

### 它的代价：牛市落后

| 期间 | 一直持有 | MA200 → 50% |
|---|---:|---:|
| 2010-2026 长期牛市 | +799.77% | +277.83% |

### 跨资产一致性

| 资产 | 择时提高收益 | 择时降低回撤 |
|---|:--:|:--:|
| SPY / QQQ / IWM / EEM（8 个市场） | 1/8 | **7/8** |

**用 8 个市场验证：这个规则稳定地降低回撤，但通常牺牲收益。**
这是**风险偏好问题，不是收益优化问题**。

---

## 4. 已知风险与限制

### 4.1 统计层面

| 项目 | 说明 |
|---|---|
| **回撤改善的统计检验** | ⚠️ **未做**。最大回撤的抽样分布难以处理，本报告**不使用「统计显著」**这一表述，只说「在 N/M 个窗口中一致改善」 |
| Sharpe 差异 | SPY 上 0.70 vs 0.77，95% CI 重叠，**无法区分** |
| 幸存者偏差 | ⚠️ **未修正**。yfinance 无 point-in-time 退市数据。但本规则只用 SPY/ETF，**不受股票池偏差影响** |
| 样本外 | 已做 walk-forward（多窗口），但 SPY 单一市场历史 |

### 4.2 机制层面

| 风险 | 说明 |
|---|---|
| **信号是滞后的** | 退场信号滞后约 16 天（7 次崩盘平均）。它**跟随**而非**预测**。2008 年也要先承受约 -20% 才离场 |
| **whipsaw** | 33.6 年发出 107 次退场信号（约每年 3.2 次），其中不少是反复摇摆 |
| **牛市拖累** | 长期牛市会显著落后一直持有（见上表） |
| **快速崩盘保护有限** | 2020 新冠期间仍承受 -25.67% |
| **2008 是最好案例** | 不要把它当作典型；它是该规则最有利的一次 |

### 4.3 ⚠️ 最重要的一条方法论警示

> **「降低回撤」本身不证明信号有价值。**
>
> H3 的 **200 次置换检验**证明：**随机减仓也能得到类似的回撤改善**。
> 也就是说，回撤下降的很大一部分来自「暴露减少」这个机械效果，
> 而不是「信号知道何时该减仓」。

**因此未来任何新信号都必须回答：**

```
Signal → Exposure change → Performance improvement
                                    ↓
              Would random exposure change have produced the same result?
```

**这个 placebo 思维必须永久保留在 FreqTrader 的回测框架里。**

---

## 5. 实现架构要求

### 5.1 关键架构变化：Signal → Target Exposure（不是 BUY/SELL）

```python
# ❌ 不要这样
if close < ma200:
    sell()

# ✅ 要这样
signal = market_regime(prices)
target_exposure = exposure_policy(signal)
# → 再由执行层负责 position sizing → order → fill
```

**理由**：本研究的核心问题已经不是「什么时候买？」，而是
**「我现在应该承担多少 market exposure？」** —— 这是一个暴露管理问题。

### 5.2 策略接口（建议）

```python
class ExposurePolicy:
    """研究与执行解耦：研究决定 target_exposure，FreqTrader 负责怎么执行"""

    def target_exposure(self, market_state) -> float:
        if market_state.close < market_state.ma200:
            return 0.50
        return 1.00
```

> 未来若 H4 有证据，只需替换 `ExposurePolicy` 实现，
> **无需改动执行层**。

### 5.3 执行层需要处理的（研究无法回答的）问题

这些问题**必须**在 dry-run 阶段回答：

- MA200 信号实际执行时滑点多少？
- 信号发生在**盘中还是收盘**？（本研究的假设是「收盘计算，次日开盘成交」）
- 次日开盘执行会损失多少？ETF gap 对暴露调整有什么影响？
- API failure / broker downtime 怎么办？
- 部分仓位调整的 rounding issue？
- 实时数据下的信号与历史回测是否一致？
- 组合已经是 50% 时，重复信号会不会重复下单？
- bot 重启后状态是否正确恢复？

---

## 6. 冻结参数（不得随意改动）

| 项目 | 值 | 说明 |
|---|---|---|
| 均线 | **MA200 SMA，日收盘** | 不做 150/180/220/250 优化 |
| 暴露 | **100% / 50%** | 不做 75/25 变体 |
| 信号时点 | 收盘计算 | |
| 执行 | **次日开盘** | |
| 标的 | 大盘指数 ETF（SPY 等） | 规则在小盘/新兴市场成本敏感（见下） |

### ⚠️ 成本敏感度（重要）

| 资产 | 在多少 bps 下失效 |
|---|---|
| SPY / QQQ | 20 bps 内仍有效 |
| IWM | **5 bps 就失效** |
| EEM | **10 bps 就失效** |

**小盘与新兴市场波动大、假信号多，成本吃掉优势。生产建议只用大盘 ETF。**

---

## 7. Strategy Origin（供 FreqTrader 注明）

```
Strategy origin: Research H1-H3 (this project)

Validated concept:
  MA200 exposure management
  (Close > MA200 -> 100%, Close < MA200 -> 50%)

Not included (studied and failed):
  H1 slow confirmation (MA50 < MA200)
  H2 layered MA (100/75/50)
  H3 volatility / credit / breadth overlay

Key caveat:
  Drawdown reduction is partly mechanical (proven by permutation test).
  This is a RISK MANAGEMENT rule, not an alpha signal.
```

---

## 8. 停止规则（Stop Rule）

**建议**：H4 是**最后一个** research hypothesis。

| H4 结果 | 行动 |
|---|---|
| ❌ 不成立 | **暂停寻找 signal** |
| ⚠️ 只在一个 asset 成立 | 不进入 production |
| ⚠️ 只有 Sharpe 改善 | 不进入 production |
| ⚠️ 只改善 CAGR | 不进入 production |
| ❌ placebo 无法区分 | 不进入 production |
| ✅ cross-asset + OOS + placebo 都支持 | 才考虑加入 strategy |

**目的**：避免无限进入 H5/H6/H7/VIX threshold/breadth 20%/30%……
最终变成 backtest overfitting machine。

### H4 的精确定义（若将来做）

> **H4**：在 `Close < MA200` 的条件下，H3 signal 所识别的状态是否提供
> **incremental information**，使**增加** exposure 相比
> **matched random exposure** 能产生可重复的 forward-return improvement？

⚠️ **不要把 H3 的"信号有信息但方向相反"直接写成 `signal = BUY`。**
目前的证据只是「条件子样本里 signal 后 63 日收益较高」，
**还没有证明它是一个可用于加仓的交易信号**。

---

## 9. 交接清单

| 内容 | 位置 |
|---|---|
| 策略规格（本文件） | `strategy/MA200Exposure-SPEC.md` |
| 决策记录 / 研究沿革 | `DECISIONS.md` |
| 预注册假设 | `hypotheses/H1,H2,H3-preregistration.md` |
| 判定报告 + 图表 | `results/` |
| 方法论与代码验证 | `methodology/` |
| 引擎与策略代码 | `code/quant/` |
| 研究脚本 | `code/run_*.py` |
| 数据（可复现） | `data/` |
| 全部回测产出 | `outputs/` |

---

## 10. 复现方式

```bash
# 回归测试（12/12 应通过）—— 运行任何回测前先跑
python methodology/test_regressions.py

# 引擎自检（无未来函数 / 无杠杆 / 无 off-by-one）
python code/quant/engine.py

# H1 / H2 / H3 复现
python code/run_h1.py
python code/run_h2.py
python code/run_h3.py
```

**依赖**：Python 3.11+、pandas、numpy、scipy、yfinance（仅重新拉数据时需要）
**注意**：`yf.set_tz_cache_location()` 必须指向可写目录，否则报 sqlite 错误。

---

*本研究在 H1–H3 完成后冻结。生产策略仅包含最简 baseline，
所有被排除的规则均有预注册记录与失败证据。*
