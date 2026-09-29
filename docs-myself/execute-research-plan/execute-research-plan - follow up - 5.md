我会把这次结果正式定性为：

> **H13_BTC_FILTER_1H_STRONG_DOWN_SHORT：development + validation 有重复，但 final holdout 没有复制。当前项目 0 survivor。**

而且有个细节必须保留：`bootstrap CI [-0.536%, +0.088%]` 跨 0，所以不能说 holdout 已经统计学上证明“反向 edge”；准确说法是 **previous positive effect failed to replicate and the holdout is compatible with no edge**。

现在不要再改 H13。

## 下一步我建议分成两步

### Phase F：Postmortem / Mechanism Audit

这个阶段**允许看已经 unblinded 的 holdout**，因为它已经不再能作为未来验证集。

目的不是找“怎样把策略救回来”，而是回答：

**这个 edge 为什么只存在于旧时期？**

重点查：

```text
H13
↓
什么时候开始失效？
↓
是 BTC regime 本身失效？
是 SHORT 条件失效？
是不同 altcoin 行为改变？
是 OI / funding / basis 关系改变？
还是 holding horizon / transaction cost interaction？
```

这里可以做非常详细的分析，但所有结果必须标成：

> `POST_HOC / EXPLORATORY / NOT_FOR_CANDIDATE_SELECTION`

否则你会不知不觉用 holdout 做第二轮挖矿。

我建议至少查：

| Diagnostic                                    | 要回答的问题                                         |
| --------------------------------------------- | ---------------------------------------------- |
| rolling expectancy                            | edge 大概什么时候开始衰减                                |
| monthly/weekly distribution                   | 是否集中在几个 regime                                 |
| per-symbol × period                           | 是否所有 altcoin 同时失效                              |
| BTC regime frequency                          | STRONG_DOWN 的市场占比有没有变化                         |
| OI / funding / basis conditional distribution | 输入环境有没有明显变化                                    |
| gross vs cost decomposition                   | 是 alpha 消失，还是成本吃掉                              |
| holding-horizon decomposition                 | 不同固定 horizon 是否表现不同                            |
| signal clustering                             | 是否某些连续 signal block 贡献绝大部分结果                   |
| feature distribution drift                    | development / validation / holdout 的特征分布是否发生变化 |

特别重要的是：

**不要在 Phase F 找到一个漂亮解释以后就直接把它变成 H16。**

---

## 然后才是 Phase G：重新开一轮实验

这才是我认为真正值得继续的路线。

当前研究的时间线已经变成：

```text
2020 → 2025-06
Development

2025-06 → 2025-11
Validation

2025-11 → 2026-08
Final Holdout
        ↑
        已经 unblinded
```

所以这整个区间以后都不能再被称为“当前实验的 untouched holdout”。

但你现在已经有一个新的时间尾部可以建立**新的 holdout**。

你目前的数据已经有 derivatives 到 2026-09-24，而 price 只到 2026-08-31。下一轮应该先把价格/index/mark 等统一延伸到一个新的、明确冻结的 cutoff，然后建立：

```text
OLD DATA
2020 → 2026-08-31
        ↓
NEW RESEARCH PERIOD

NEW HOLDOUT
2026-09-01 → new cutoff
```

然后重新开一个**全新的 experiment ID / preregistration**。

也就是说：

```text
Strategy Factory Experiment #1
H13
        ↓
FAILED REPLICATION
        ↓
POSTMORTEM
        ↓
Experiment #2
        ↓
NEW HYPOTHESES
        ↓
NEW FROZEN HOLDOUT
```

这样才不会变成：

```text
发现策略
→ holdout 失败
→ 改规则
→ 再看旧 holdout
→ 再改
→ 最后挑一个看起来好的
```

那样统计上就基本失去意义了。

---

## 我最建议你现在做的

先不要做 Phase G。

**先做 Phase F。**

因为这次失败其实非常有价值：你已经知道一个通过了 discovery、walk-forward validation，而且在 validation 上表现不错的 derivatives/regime relationship，到了较新的市场阶段就消失了。

这比单纯“没有找到策略”有信息量得多。

直接给 agent：

# Phase F — Postmortem and Mechanism Audit

Spec version:

`2026-09-26-v2-regime-derivatives`

## Objective

Phase E is complete.

Final holdout has been opened and is permanently unblinded.

Current candidates:

```text
H13_BTC_FILTER_1H_STRONG_UP_SHORT
H13_BTC_FILTER_1H_STRONG_DOWN_SHORT
```

Current conclusion:

```text
H13_STRONG_UP_SHORT   = NO_MEANINGFUL_SAMPLE
H13_STRONG_DOWN_SHORT = NEGATIVE_REPLICATION
```

The project currently has:

```text
0 research survivors
```

Phase F is a post-hoc exploratory audit.

It MUST NOT be used to rescue, optimize, replace, or re-select the failed candidates.

---

# 1. Evidence status

The following data is now permanently unblinded:

```text
2025-11-18 23:00:00+00:00
→
2026-08-31 23:00:00+00:00
```

This region may be used for diagnostics.

It MUST NOT again be described as:

```text
untouched
unseen
unblinded
validation
holdout
```

for any future candidate-selection purpose.

All Phase F outputs must be labelled:

```text
POST_HOC
EXPLORATORY
NOT_FOR_CANDIDATE_SELECTION
```

---

# 2. No strategy rescue

Do NOT:

* modify H13
* change thresholds
* change timeframe
* change holding period
* change symbols
* change costs
* remove symbols
* add filters
* optimize parameters
* create H16/H17/etc.
* create a new candidate from a post-hoc finding
* reopen the old holdout as a validation set

Phase F is diagnosis only.

---

# 3. Failure timeline

For:

```text
H13_BTC_FILTER_1H_STRONG_DOWN_SHORT
```

construct a fixed chronological analysis from:

```text
development
validation
final_holdout
```

Use fixed time buckets.

Do not search for a favorable breakpoint.

Report:

```text
trade_count
expectancy
stress_expectancy
PF
stress_PF
```

for each calendar month and year where sufficient data exists.

Then calculate rolling diagnostics using fixed windows only.

Do not choose window size after inspecting the result.

---

# 4. Distribution drift

Compare development, validation and holdout distributions for the inputs used by H13.

Required variables include:

```text
BTC trend regime
price return
realized volatility
OI level/change
funding
basis
mark-index spread
```

For each period report:

```text
mean
median
std
p10
p25
p50
p75
p90
```

Where appropriate calculate a distribution-distance diagnostic.

This is exploratory only.

Do not infer causality.

---

# 5. Regime frequency drift

For each major BTC regime:

```text
STRONG_UP
WEAK_UP
NEUTRAL
WEAK_DOWN
STRONG_DOWN
```

report frequency by period.

Question:

Did the frequency or duration of the STRONG_DOWN state change substantially between development, validation and holdout?

Do not modify the regime thresholds.

---

# 6. Signal-frequency drift

For H13_STRONG_DOWN_SHORT report:

```text
signals per month
signals per week
average consecutive signal length
median consecutive signal length
maximum consecutive signal length
```

by:

```text
development
validation
holdout
```

Determine whether the deterioration is associated with:

```text
signal frequency change
signal clustering change
return-per-signal change
```

Do not change the signal rule.

---

# 7. Symbol-period decomposition

Create a fixed matrix:

```text
symbol × period
```

for:

```text
BTCUSDT
ETHUSDT
XRPUSDT
SOLUSDT
BNBUSDT
```

and:

```text
development
validation
holdout
```

Report:

```text
N
expectancy
PF
stress expectancy
stress PF
```

Do not select or exclude symbols.

---

# 8. Gross vs cost decomposition

Determine whether the holdout deterioration was caused primarily by:

```text
gross return deterioration
fees
slippage
funding
```

Report:

```text
gross expectancy
fee impact
slippage impact
funding impact
net expectancy
```

Use only the frozen cost model.

Do not test alternative costs.

Do not reduce costs to make the result look better.

---

# 9. Holding-horizon diagnostic

Use ONLY the fixed horizons already present in the research code.

Do NOT introduce arbitrary new horizons.

For each existing horizon calculate:

```text
development expectancy
validation expectancy
holdout expectancy
```

This is descriptive only.

Do not turn the best-looking horizon into a new candidate.

---

# 10. Dependence structure

Compare:

```text
lag-1 autocorrelation
effective sample size
signal-block lengths
```

across:

```text
development
validation
holdout
```

Question:

Did dependence structure change materially?

Use the same dependence-aware methodology already implemented.

---

# 11. Regime-conditioned attribution

Compare:

```text
H13_STRONG_DOWN_SHORT
```

against the already-defined diagnostic unfiltered control.

Report for each period:

```text
candidate expectancy
control expectancy
difference
```

This remains associative evidence only.

Do NOT describe the regime filter as causal.

Do not optimize the control.

---

# 12. Hypothesis drift assessment

Produce a descriptive table:

```text
Diagnostic
Development
Validation
Holdout
Interpretation
```

Possible interpretations:

```text
STABLE
DRIFTED
DISAPPEARED
INSUFFICIENT_DATA
AMBIGUOUS
```

These labels are descriptive.

Do not use them to automatically generate new hypotheses.

---

# 13. Candidate conclusion

The report must preserve the current result:

```text
H13_STRONG_DOWN_SHORT:
positive in development
positive in validation
negative in final holdout
```

Do not average the three periods.

Do not hide the negative holdout.

Do not present the aggregate full-period result as though it were a single test.

---

# 14. Required outputs

Create:

```text
user_data/strategy_factory_runs/v2/phase-f-postmortem-<run_id>/
```

Required:

```text
postmortem_report.md
postmortem_report.html

period_metrics.csv
rolling_metrics.csv
feature_distribution_drift.csv
regime_frequency.csv
signal_frequency.csv
symbol_period_matrix.csv
cost_decomposition.csv
holding_horizon_diagnostics.csv
dependence_diagnostics.csv
regime_attribution_posthoc.csv

manifest.json
```

Every output must contain:

```text
analysis_status = POST_HOC_EXPLORATORY
candidate_selection_allowed = false
```

---

# 15. Final stop condition

After Phase F:

STOP.

Do not:

* generate a new strategy
* generate a new hypothesis
* alter H13
* reopen holdout
* perform optimization
* deploy
* trade

Final printout:

```text
PHASE F STATUS: COMPLETE
POST_HOC ONLY: YES
NEW HYPOTHESES: 0
CANDIDATE MODIFICATIONS: 0
OPTIMIZATION: NO
```

The next experiment, if any, must have a new experiment ID, new preregistration, and a newly frozen untouched holdout.

### 最后一句

这次其实不是“白跑”。

你已经验证了一个很重要的事实：

**单纯增加 OI、funding、basis、BTC regime 等 derivatives features，并不会自动把一个历史上看起来很强的 pattern 变成稳定 edge。**

而且你的 pipeline 已经抓到了好几个真实 bug、做了 causal join 检查、multiple testing、dependence correction、validation、最后还真的让 holdout 有权否决 candidate。

这说明 **Strategy Factory 本身已经开始像一个研究系统，而不只是一个 backtester**。下一步最值得做的就是把这次失败拆明白，再决定第二轮到底应该换“假设”，还是换“数据/市场机制”。
