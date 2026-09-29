看完 Phase D，我认为现在可以进入 **Final Holdout**，而且这次是一个非常清晰的下一步。

但先纠正一个重要表述：

> “regime filter 把期望放大 26 倍，所以 regime 在干活。”

这个说法**太强**。目前证据是：加入 BTC STRONG_DOWN 条件后，候选子集的条件收益显著高于去掉该条件后的大样本控制组；这支持“regime-conditioned subset 与较高收益相关”，但还不能严格证明这个 filter 本身具有因果贡献。现在不要再改它，原样带进 holdout。

### Phase D 后的实际结论

目前真正值得进入 final holdout 的研究对象是：

| Candidate         |                                        Dev |                               Validation | 当前状态              |
| ----------------- | -----------------------------------------: | ---------------------------------------: | ----------------- |
| STRONG_UP_SHORT   |     stress Dev **-0.031%**, Validation N=3 |                                 几乎没有验证样本 | **证据不足**          |
| STRONG_DOWN_SHORT | stress Dev **+0.341%**, Validation N=1,340 | +0.519% stress，PF 1.656，bootstrap CI > 0 | **有重复证据，但仍未最终验证** |

所以我建议：

**Final Holdout 两个都跑，但不允许在看到 holdout 后再决定跑哪个。**

这样最干净。否则现在把 STRONG_UP 删除，再只测 STRONG_DOWN，会留下一个“根据 validation 结果筛选后再打开 holdout”的选择行为。两个一起测，反而最容易解释。

同时，最终 holdout **不能再做任何 discovery、参数调整、阈值调整或新 control search**。

---

## 下一阶段：Phase E — Final Holdout

这一阶段结束后才知道：

```text
Development
    ↓
Phase C discovery
    ↓
Phase D frozen validation
    ↓
Phase E FINAL HOLDOUT   ← 现在
    ↓
只有确认结果后
    ↓
Phase F paper forward validation
```

而 Phase E 最重要的是：

**在打开 holdout 之前，先把“怎么看结果”写死。**

不要看到结果之后才决定什么叫成功。

我建议直接给 agent 下面这份。

# Phase E — Final Holdout Evaluation

Spec version:

`2026-09-26-v2-regime-derivatives`

## Objective

Phase D is complete.

Two candidates are frozen:

```text
H13_BTC_FILTER_1H_STRONG_UP_SHORT
H13_BTC_FILTER_1H_STRONG_DOWN_SHORT
```

Phase E is the first and only final-holdout evaluation.

The final holdout has remained sealed until this point.

Open it now ONLY for the frozen candidates.

Do NOT perform discovery, optimization, parameter search, hypothesis generation, or candidate modification.

Research only.

No live trading.
No exchange accounts.
No order execution.
No deployment.

---

# 1. Freeze before unsealing

Before reading any final-holdout rows, create:

`final_holdout_protocol.json`

Record:

```text
spec_version
candidate IDs
candidate logic hashes
data boundary
metrics
cost assumptions
funding assumptions
interpretation procedure
```

Candidate logic must exactly match the Phase D frozen implementation.

No edits after this point.

---

# 2. Final holdout boundary

Use exactly:

```text
FINAL_HOLDOUT_START
2025-11-18 23:00:00+00:00

FINAL_HOLDOUT_END
2026-08-31 23:00:00+00:00
```

The holdout ends at the latest complete price day already established by A2.

Do not extend or shorten this interval after seeing results.

Do not inspect September 2026 data if it is outside this defined holdout.

---

# 3. Candidate set

Evaluate BOTH frozen candidates:

```text
H13_BTC_FILTER_1H_STRONG_UP_SHORT
H13_BTC_FILTER_1H_STRONG_DOWN_SHORT
```

Even though STRONG_UP_SHORT produced only 3 validation observations, it remains part of the frozen candidate set.

Do not remove it after observing holdout results.

Do not add any other candidate.

---

# 4. Causal feature reconstruction

Rebuild all required features using the exact Phase D / Phase C pipeline.

Preserve:

* 1h decision timeframe
* BTC reference regime
* causal OI as-of semantics
* causal funding semantics
* validated basis definition
* mark/index handling
* timezone handling
* exact frozen candidate predicates

No future information may enter a feature.

Every derivative observation used in the holdout must satisfy:

```text
truth_timestamp <= decision_timestamp
```

and the previously validated truth-timestamp leakage checks must remain active.

---

# 5. Execution / cost assumptions

Use exactly the frozen assumptions.

Base:

```text
5 bps fee per side
1 bps slippage per side
```

Stress:

```text
10 bps fee per side
3 bps slippage per side
```

Funding:

```text
adverse payer only
credits ignored
actual observed funding events only
```

Leverage:

```text
1x
```

Do not change any of these based on the results.

---

# 6. Primary final-holdout metrics

For every candidate calculate:

```text
trade_count
mean_return
median_return
win_rate
profit_factor
expectancy
stress_expectancy
stress_profit_factor
max_drawdown
Sharpe
Sortino
MAE
MFE
```

Also report:

```text
gross_pnl
net_pnl
```

using the already-frozen execution/cost model.

Do not use annualized metrics as the primary result if the implementation does not already define them.

---

# 7. Time decomposition

For each candidate calculate fixed calendar-period diagnostics:

```text
2025-11
2025-12
2026-01
2026-02
2026-03
2026-04
2026-05
2026-06
2026-07
2026-08
```

For every month:

```text
trade_count
PnL
mean_return
expectancy
PF
```

Do not merge or remove months because of low or negative performance.

Also report:

```text
positive_month_count
negative_month_count
zero_signal_month_count
```

---

# 8. Symbol decomposition

For each candidate and each symbol:

```text
BTCUSDT
ETHUSDT
XRPUSDT
SOLUSDT
BNBUSDT
```

report:

```text
trade_count
PnL
PnL_share
mean_return
expectancy
PF
```

Do not exclude any symbol after seeing results.

---

# 9. Regime decomposition

For the frozen candidates report the actual observed BTC reference state associated with each signal.

For each candidate:

```text
signal_count
PnL
expectancy
PF
```

This is descriptive only.

Do not create additional regime buckets.

Do not change the STRONG_UP / STRONG_DOWN definition.

---

# 10. Dependence-aware uncertainty

Signals are serially dependent.

Repeat the Phase D dependence-aware diagnostic:

```text
lag-1 autocorrelation
effective_sample_size
block-bootstrap 95% CI
P(return > 0)
```

Use block bootstrap consistent with Phase D.

Do not use naive pooled t-statistics as the only evidence.

Do not introduce a new post-hoc statistical threshold.

---

# 11. Comparison with previous evidence

For each candidate create a fixed comparison table:

```text
Development contiguous
Development fold-restricted
Validation
Final holdout
```

Columns:

```text
N
expectancy
stress expectancy
PF
stress PF
bootstrap CI
```

The purpose is to show evidence progression.

Do not select the most favorable region.

Do not average development, validation, and holdout together.

---

# 12. Predefined interpretation categories

Do not create a numerical score or ranking.

Use descriptive categories only.

For each candidate classify the final-holdout sign relative to the previous evidence:

```text
POSITIVE_REPLICATION
NEGATIVE_REPLICATION
NO_MEANINGFUL_SAMPLE
MIXED
```

Definitions:

### POSITIVE_REPLICATION

Final-holdout expectancy has the same positive sign as the development and validation evidence, with meaningful sample size.

### NEGATIVE_REPLICATION

Final-holdout expectancy has the opposite sign from the established development/validation direction, with meaningful sample size.

### NO_MEANINGFUL_SAMPLE

The candidate produces too few holdout observations to support a meaningful replication statement.

### MIXED

The directional result is not straightforward across cost models / periods / components.

These are descriptive evidence labels, not trading recommendations.

---

# 13. Do not introduce a new "pass" threshold

The original Phase C survivor thresholds were discovery gates.

Do not invent a new threshold after seeing holdout results such as:

```text
PF > X
Sharpe > X
expectancy > X
win rate > X
```

unless that exact threshold was already frozen before the holdout was opened.

The final holdout should primarily answer:

> Does the frozen candidate reproduce its previously observed behavior in completely untouched data?

It is not another optimization round.

---

# 14. No new controls

Do NOT create:

* new hypotheses
* new regime definitions
* new threshold variants
* new holding periods
* new stop values
* new take-profit values
* new timeframes
* new symbols
* new feature combinations
* new "better" controls discovered from holdout

The existing H13 candidates are frozen.

The Phase D regime-attribution control is not a new candidate and must not be optimized using holdout data.

---

# 15. Holdout access accounting

The report must record:

```text
holdout_access_started
holdout_access_completed
rows_read
symbols_read
feature_sets_read
```

After Phase E:

```text
holdout_access_count > 0
```

is expected.

Before this phase it was zero.

After this phase the holdout is considered permanently unblinded.

Record this transition explicitly.

---

# 16. Required outputs

Create:

```text
user_data/strategy_factory_runs/v2/phase-e-final-holdout-<run_id>/
```

Required:

```text
final_holdout_protocol.json
final_holdout_results.csv
final_holdout_by_month.csv
final_holdout_by_symbol.csv
final_holdout_by_regime.csv
final_holdout_uncertainty.csv
development_validation_holdout_comparison.csv
holdout_access_log.json
manifest.json
report.md
report.html
```

---

# 17. Report structure

Start with:

```text
# Phase E — Final Holdout Evaluation
```

Then immediately show:

```text
Candidates frozen: 2
New hypotheses: 0
Optimization: NO
Final holdout accessed: YES
```

Then the primary table:

```text
Candidate
Holdout N
Holdout expectancy
Holdout stress expectancy
Holdout PF
Holdout stress PF
Bootstrap 95% CI
Interpretation
```

Then show:

1. monthly decomposition
2. symbol decomposition
3. regime decomposition
4. dependence diagnostics
5. development → validation → holdout comparison
6. interpretation limits

---

# 18. Critical interpretation rules

Do not say:

* "this proves the strategy works"
* "this guarantees profitability"
* "this is ready for live trading"
* "this will make money"
* "this is a winning strategy"

A positive final holdout is evidence of replication, not proof of future profitability.

A negative final holdout is evidence against replication over this historical period, not proof that the underlying relationship can never occur again.

---

# 19. Final stop condition

After the report is generated:

STOP.

Do not:

* optimize
* retune
* add hypotheses
* modify candidate logic
* create Freqtrade strategy
* deploy
* trade

Final printout:

```text
PHASE E STATUS: COMPLETE
CANDIDATES EVALUATED: 2
FINAL HOLDOUT ACCESSED: YES
NEW HYPOTHESES: 0
OPTIMIZATION: NO
CANDIDATE LOGIC CHANGED: NO
```

The next phase, if warranted, must be decided only after reviewing the complete Phase E report.

### 我现在对结果的判断

目前其实已经出现了一个很有意思的研究链：

```text
Phase C
STRONG_DOWN_SHORT
    ↓
Phase D contiguous development
+0.401%
    ↓
Phase D validation
+0.579%
    ↓
stress
+0.519%
    ↓
block bootstrap CI
[+0.277%, +0.870%]
```

这是比单纯看到 `PF 1.754` 更值得关注的证据链。

但还差最后一块：

```text
2025-11-18 → 2026-08-31
```

如果它在这里仍然保持相同方向，而且不是某一个月、某一个币、某几笔交易撑起来的，那么研究证据会明显比现在完整。

相反，**如果 final holdout 崩掉，也不要救它**。那同样是 Strategy Factory 非常有价值的结果：说明这个关系在 development + validation 中看起来有重复性，但没有跨到更后的市场环境。

还有一个重要提醒：**STRONG_UP_SHORT 的 validation 只有 3 笔，所以它实际上已经不值得被当成“有验证证据”的候选来解读。** 保留它进入 holdout 是为了实验完整性，不代表它和 STRONG_DOWN_SHORT 的证据等级相同。
