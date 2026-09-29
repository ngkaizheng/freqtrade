# Quant Research Handoff — MA200 暴露管理

> **本文件夹用途**：把 `ta-workflow` 中完成的量化研究（H1–H3）冻结并移交给 FreqTrader。
> **冻结日期**：2026-09-17
> **下一步**：复制进 FreqTrader workspace，据此实现 dry-run / forward testing。

---

## 30 秒速览

**研究结论**：没有找到可靠的 alpha signal，但找到了一个**有历史风险管理证据的 exposure-control rule**。

**生产策略（唯一）**：

```
Close > MA200  →  100% 股票暴露
Close < MA200  →   50% 股票暴露
```

**效果**：SPY 1993-2026（33.6 年）最大回撤从 **-55.19% 降到 -30.13%**，代价是 CAGR 从 10.81% 降到 7.49%。
8 个市场中 **7 个**回撤改善，**1 个**收益提高 —— 这是**风险偏好问题，不是收益优化问题**。

**三个失败的假设**（全部有预注册记录，见 `hypotheses/`）：

| | 假设 | 为什么失败 |
|---|---|---|
| H1 | 用 `MA50<MA200` 慢确认减少 whipsaw | 换手降 75-88% ✓，但回撤保护跨期不稳定 ✗ |
| H2 | 双层 MA（100/75/50）兼顾保护与低摩擦 | 两信号 75-78% 同步，分层退化为延迟 ✗ |
| H3 | 叠加 VIX/信用/广度进一步降险 | 方向上指向**超跌反弹**，且未超出安慰剂 ✗ |

---

## ⚠️ 最重要的一件事

> **「降低回撤」本身不证明信号有价值。**
>
> H3 的 **200 次置换检验**证明：**随机减仓也能得到类似的回撤改善**。
> 回撤下降很大一部分来自「暴露减少」这个**机械效果**，
> 而不是「信号知道何时该减仓」。

**因此**：任何新信号都必须回答 ——

```
Signal → Exposure change → Performance improvement
                                    ↓
              Would random exposure change have produced the same result?
```

**这个 placebo 思维必须永久保留在 FreqTrader 的回测框架里。**

---

## 从哪开始读

| 顺序 | 文件 | 内容 |
|---|---|---|
| 1 | **`DECISIONS.md`** | **研究决策记录**：完整研究沿革、每个决策及其证据、方法论遗产 |
| 2 | **`strategy/MA200Exposure-SPEC.md`** | **生产策略规格**：规则、证据、限制、实现架构、Stop Rule |
| 3 | `hypotheses/` | 三个预注册（运行前冻结），看"我们承诺了什么" |
| 4 | `results/` | 三个判定报告 + 分析图 + 机器可读 JSON |
| 5 | `methodology/` | 回归测试、回测陷阱清单、策略全景 |
| 6 | `data/` + `outputs/` | 原始数据与全部回测产出（可追溯） |

---

## 关键警示（实现前必读）

### 1. 架构：暴露管理，不是买卖信号

```python
# ❌ 不要
if close < ma200: sell()

# ✅ 要
signal = market_regime(prices)
target_exposure = exposure_policy(signal)
# → 执行层负责 position sizing → order → fill
```

**理由**：研究的核心问题不是「什么时候买？」，而是**「我现在应该承担多少暴露？」**

### 2. 成本敏感度：只用大盘 ETF

| 资产 | 在多少 bps 下策略失效 |
|---|---|
| SPY / QQQ | 20 bps 内仍有效 |
| **IWM** | **5 bps 就失效** |
| **EEM** | **10 bps 就失效** |

### 3. 这条规则是滞后的

- 退场信号平均滞后约 **16 天**
- 它**跟随**而非**预测**——2008 年也要先承受约 -20% 才离场
- 33.6 年发出 **107 次**退场信号（约每年 3.2 次），不少是反复摇摆
- **2008 年（-19.43% → +16.97%）是该规则最有利的一次，不要当典型**

### 4. 回撤改善未经统计显著性检验

最大回撤的抽样分布难以处理，本报告**不使用「统计显著」**表述，
只说「在 N/M 个窗口中一致改善」。**不要对外声称"统计显著"。**

---

## 复现方式

```bash
# 1. 运行任何回测之前，先跑回归测试（应 12/12 通过）
python methodology/test_regressions.py

# 2. 引擎自检（无未来函数 / 无杠杆 / 无 off-by-one）
python code/quant/engine.py

# 3. 复现三个假设
python code/run_h1.py
python code/run_h2.py
python code/run_h3.py
```

**依赖**：Python 3.11+、`pandas`、`numpy`、`scipy`、`yfinance`（仅重新拉数据时需要）

**已知环境问题**：`yf.set_tz_cache_location()` 必须指向可写目录，
否则报 `sqlite3.OperationalError: unable to open database file`。
脚本已处理；若在新环境运行失败，先检查这一项。

**数据已全量附带**（113 个 CSV），**无需联网即可复现全部结果**。

---

## 文件夹结构

```
quant-research-handoff/
├── README.md                  ← 本文件
├── DECISIONS.md               ← 研究决策记录（含完整研究沿革）
├── hypotheses/                ← 预注册（3 份，运行前冻结）
├── results/                   ← 判定报告 + 分析图 + JSON（9 份）
├── methodology/               ← 回归测试 + 陷阱清单 + 策略全景（3 份）
├── strategy/                  ← 生产策略规格（1 份）
├── code/
│   ├── quant/                 ← 引擎、指标、策略库、数据层（5 个模块）
│   └── run_*.py               ← 研究脚本（29 个）
├── data/                      ← 113 个 CSV（109 标的历史 + VIX/HYG/LQD 等）
└── outputs/                   ← 68 个回测产出（CSV + SVG + 配套 md）
```

**总大小约 45 MB。**

---

## 研究的价值在哪

**不是**「找到了一个 Sharpe 0.92 的万能策略」。

**而是**：

1. **一套排除错误假设的方法论** —— 预注册 → 条件子样本 → 置换检验 → 样本外
2. **6 类代码级陷阱的回归测试**（12/12 通过），它们"跑得通、不报错、数字漂亮"
3. **一个永久有效的判据**：降低回撤 ≠ 信号有价值，必须先过 placebo
4. **一个诚实的边界**：MA200 是风险管理工具，不是预测工具

> 研究的价值在于**知道哪些路走不通，以及为什么**。
> 全部被排除的规则都有预注册记录与失败证据。

---

*研究轨道在此冻结。后续工作在 FreqTrader 轨道继续 ——*
*回答研究无法回答的问题：滑点、执行时点、API 失败、状态恢复、forward performance。*
