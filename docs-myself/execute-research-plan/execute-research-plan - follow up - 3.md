这一步我建议**不要再做任何策略优化**。Phase C 已经完成候选发现；现在应该把这两个 candidate 完全冻结，专门验证它们是不是能在**较新的、从未参与选择的 validation 区间**重新出现。

### 现在的研究状态

```text
A2        PASS
A2.5      PASS
Phase C   COMPLETE
Candidates:
  H13_BTC_FILTER_1H_STRONG_UP_SHORT
  H13_BTC_FILTER_1H_STRONG_DOWN_SHORT

Final holdout:
  untouched
```

这里最值得攻击的不是 PF 本身，而是**时间稳定性 + 归因问题**：

| 问题                      | 现在看到的现象               | Phase D 怎么查                             |
| ----------------------- | --------------------- | --------------------------------------- |
| 2021–2022 concentration | 大量利润来自早期              | 按年份/时期拆解                                |
| regime 是否真的重要           | 强 UP、强 DOWN 都做 SHORT  | 做 BTC-regime attribution diagnostic     |
| 是否 BTC/某个币贡献大部分利润       | pooled N 很大           | 按 symbol 拆                              |
| 是否只是少数时段有效              | top-3 fold share 仍较高  | 固定 calendar slices                      |
| edge 是否能离开旧市场环境         | development 到 2025-06 | 用 2025-06 → 2025-11 validation          |
| 成本敏感性                   | stress 仍为正            | validation 上原样重算                        |
| 样本独立性                   | 可能存在连续/相关信号           | autocorrelation / effective sample size |

尤其是你指出的这个：

> 一个 STRONG_UP，一个 STRONG_DOWN，但两者都 SHORT。

这个非常值得查。**它可能说明 BTC regime 只是筛选条件，真正起作用的是 SHORT 方向本身。**

但是现在不能看到这个现象以后，马上创造一个新的 SHORT 策略去优化它。可以做 **diagnostic attribution**，但不能拿它生成新的候选。

---

## 下一步：Phase D

Phase D 应该只做：

```text
Frozen candidates
        ↓
Development diagnostics
        +
Reserved validation
        ↓
Replication / non-replication evidence
        ↓
STOP
        ↓
只有之后才考虑 final holdout
```

而且 **final holdout：

```text
2025-11-18 23:00 → 2026-08-31 23:00
```

整个 Phase D 都不能碰。

下面这份可以直接给 coding agent。

# Phase D — Frozen Candidate Validation

Spec version:

`2026-09-26-v2-regime-derivatives`

## Objective

Phase C is complete.

Freeze the two research candidates exactly as discovered:

```text
H13_BTC_FILTER_1H_STRONG_UP_SHORT
H13_BTC_FILTER_1H_STRONG_DOWN_SHORT
```

Do NOT optimize them.

Do NOT add parameters.

Do NOT modify entry/exit logic.

Do NOT change thresholds.

Do NOT remove conditions.

Do NOT create a replacement strategy.

The purpose of Phase D is validation and attribution only.

This is still research-only.

No live trading.
No exchange accounts.
No order execution.
No Freqtrade live strategy generation.

---

# 1. Freeze candidate definitions

Before running anything:

Record the exact implementation hash / source hash for both candidates.

Create:

`candidate_freeze.json`

Example structure:

```json
{
  "spec_version": "2026-09-26-v2-regime-derivatives",
  "frozen_at": "...",
  "candidates": [
    {
      "id": "H13_BTC_FILTER_1H_STRONG_UP_SHORT",
      "logic_hash": "...",
      "source_hash": "..."
    },
    {
      "id": "H13_BTC_FILTER_1H_STRONG_DOWN_SHORT",
      "logic_hash": "...",
      "source_hash": "..."
    }
  ]
}
```

The candidate definitions must be byte-for-byte / logic-equivalent to the Phase C implementation.

After this point, candidate logic cannot change during Phase D.

---

# 2. Data regions

Use exactly the previously frozen research boundary.

## Development

```text
2020-02-01 00:00:00+00:00
→ 2025-06-06 22:12:00+00:00
```

## Validation

```text
2025-06-06 22:12:00+00:00
→ 2025-11-18 22:12:00+00:00
```

## Final holdout

```text
2025-11-18 23:00:00+00:00
→ 2026-08-31 23:00:00+00:00
```

### Critical rule

Phase D MUST NOT read final holdout data.

The final holdout remains sealed.

Expected holdout access count:

```text
0
```

---

# 3. Recompute, do not reuse hidden results

Reconstruct candidate signals using the same feature pipeline used by Phase C.

Do not reuse Phase C performance numbers as if they were validation results.

The same:

* timeframe
* causal feature construction
* OI as-of semantics
* funding observability convention
* basis definition
* execution assumptions
* costs
* funding treatment

must be used.

No new information may be introduced.

---

# 4. Validation metrics

For each candidate, calculate on the reserved validation interval:

```text
sample_count
mean_return
median_return
std
win_rate
profit_factor
expectancy
max_drawdown
Sharpe
Sortino
MAE
MFE
base_cost_result
stress_cost_result
```

Use the exact Phase C cost model:

Base:

```text
5 bps fee / side
1 bps slippage / side
```

Stress:

```text
10 bps fee / side
3 bps slippage / side
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

Do not optimize costs.

---

# 5. Development concentration diagnostics

The concentration issue discovered in Phase C must be attacked explicitly.

This section is diagnostic only.

Do not modify candidate selection gates.

For both candidates produce:

## 5.1 Calendar-year P&L

At minimum:

```text
2021
2022
2023
2024
2025
```

Report:

```text
trade_count
gross_pnl
net_pnl
mean_return
PF
expectancy
```

Also report:

```text
2021-2022 combined contribution
2023-2025 combined contribution
```

Do not change the candidate based on these results.

---

# 6. Period concentration

Produce fixed calendar-period diagnostics.

Use calendar years rather than selecting periods after seeing the result.

For every year:

```text
trade_count
PnL
PnL_share
expectancy
PF
```

Also calculate:

```text
positive_year_count
negative_year_count
largest_positive_year_share
largest_negative_year
```

Do not introduce a new pass/fail threshold.

These are diagnostics.

---

# 7. Fold concentration

Use the exact Phase C walk-forward folds.

For each candidate:

```text
fold_id
start
end
trade_count
PnL
expectancy
PF
```

Also preserve:

```text
top1_fold_profit_share
top3_fold_profit_share
bottom_fold
median_fold_pnl
positive_fold_count
```

Do not introduce a new concentration gate.

The purpose is to understand stability, not retroactively redefine the research specification.

---

# 8. Symbol attribution

This is required.

The pooled results can hide concentration in one asset.

For each candidate and symbol:

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
PF
expectancy
win_rate
```

Also calculate:

```text
largest_symbol_profit_share
```

Do not alter the candidate if one symbol dominates.

Report it.

---

# 9. Regime attribution diagnostic

The two candidates are:

```text
STRONG_UP + SHORT
STRONG_DOWN + SHORT
```

This creates an important attribution question:

Is the BTC regime actually contributing anything, or is the dominant effect simply the SHORT direction?

Run a diagnostic comparison.

### Candidate

Use the frozen candidate exactly as defined.

### Diagnostic control

Construct a temporary analytical control representing the same underlying SHORT setup while removing ONLY the BTC regime restriction, if this can be done mechanically from the existing Phase C implementation.

This control is:

* diagnostic only
* not a new hypothesis
* not a candidate
* not eligible for promotion
* not allowed to replace either frozen candidate
* not allowed to trigger parameter changes

Report:

```text
candidate_short_return
control_short_return
candidate_trade_count
control_trade_count
candidate_PF
control_PF
candidate_expectancy
control_expectancy
```

Do not optimize the control.

If implementation would require inventing new trading logic rather than mechanically removing the existing regime filter, STOP this diagnostic and report:

`REGIME_ATTRIBUTION_CONTROL_NOT_AVAILABLE`

---

# 10. Validation-period analysis

This is the most important section.

Run both frozen candidates on:

```text
2025-06-06 22:12
→
2025-11-18 22:12
```

This region was not used during Phase C candidate discovery.

For each candidate report:

```text
N
mean
median
win_rate
PF
expectancy
stress_expectancy
stress_PF
max_drawdown
MAE
MFE
```

Also report:

```text
trade_count_by_month
PnL_by_month
expectancy_by_month
PnL_by_symbol
```

Do not select a more favorable date range.

Do not remove bad months.

Do not change the start/end dates.

---

# 11. Validation uncertainty

Because trade outcomes may not be independent, do not rely only on the pooled one-sided t-test used during Phase C.

For validation report:

```text
autocorrelation
lag-1 autocorrelation
effective_sample_size
bootstrap_confidence_interval
```

Use a block bootstrap when observations are serially dependent.

Do not turn this into a new selection gate unless such a rule already exists in the frozen preregistration.

The purpose is to show uncertainty honestly.

---

# 12. Replication classification

Do NOT invent a new numeric winner score.

Instead classify each candidate descriptively:

```text
REPLICATED_SIGN
OPPOSITE_SIGN
NO_MEANINGFUL_SAMPLE
```

based on the sign of validation expectancy relative to the development result.

Also report:

```text
development_expectancy
validation_expectancy
development_stress_expectancy
validation_stress_expectancy
```

This is descriptive evidence, not a new optimized gate.

---

# 13. Important interpretation rule

Do not claim that a candidate is validated merely because validation expectancy is positive.

Also do not claim failure merely because validation expectancy is negative.

The report must distinguish:

```text
development evidence
validation evidence
final holdout evidence
```

At the end of Phase D:

* development evidence exists
* validation evidence may exist
* final holdout evidence must still be absent

---

# 14. Multiple testing

No new hypothesis search is permitted.

Do NOT:

* add H16/H17/etc.
* add parameter variants
* scan thresholds
* scan holding periods
* scan stop-loss values
* scan take-profit values
* optimize regime thresholds
* optimize timeframes
* optimize symbols

Phase D evaluates only the two frozen candidates.

No new Reality Check family is required for new hypotheses because no new hypotheses are being introduced.

Preserve the original Phase C multiple-testing record.

---

# 15. Final holdout guard

The final holdout must remain completely inaccessible.

Add an explicit assertion:

```text
assert final_holdout_access_count == 0
```

Also verify that:

```text
candidate generation never receives rows >= 2025-11-18 23:00:00
```

The Phase D run must fail closed if holdout access is attempted.

---

# 16. Required output files

Create:

```text
user_data/strategy_factory_runs/v2/phase-d-validation-<run_id>/
```

Required:

```text
candidate_freeze.json

validation_results.csv
validation_by_month.csv
validation_by_symbol.csv

development_year_diagnostics.csv
development_fold_diagnostics.csv
development_symbol_diagnostics.csv

regime_attribution.csv
uncertainty_diagnostics.csv

holdout_access_log.json
manifest.json

report.md
report.html
```

---

# 17. Report headline

The report must begin with:

```text
# Phase D — Frozen Candidate Validation
```

Then show:

```text
Candidates frozen: 2
Development data accessed: YES
Validation data accessed: YES
Final holdout accessed: NO
New hypotheses introduced: NO
Candidate optimization performed: NO
```

Then show a table:

```text
Candidate
Development N
Development expectancy
Development stress expectancy
Validation N
Validation expectancy
Validation stress expectancy
Validation PF
Validation stress PF
Validation sign
```

---

# 18. Stop condition

After Phase D:

STOP.

Do not:

* open final holdout
* modify candidates
* optimize candidates
* create trading strategies
* deploy anything
* connect exchange accounts

The next phase, if warranted, will be a separately controlled final-holdout evaluation using the exact frozen candidates.

Final printout:

```text
PHASE D STATUS: COMPLETE
CANDIDATES FROZEN: 2
VALIDATION ACCESSED: YES
FINAL HOLDOUT ACCESSED: NO
NEW HYPOTHESES: 0
OPTIMIZATION: NO
```

### 我特别建议你让它保留 `regime_attribution.csv`

因为这次 Phase C 最有意思的地方其实不是：

> “出现了两个候选。”

而是：

> **两个互相相反的 BTC regime，却都只做 SHORT，而且都留下了正的 development edge。**

这很可能告诉我们某个更底层的东西，也可能只是 pooled / era-specific artifact。现在不要猜，Phase D 把它拆开。

还有一个很关键的时间点：**Phase D 的 validation 只有约 5 个月，而 development 有数年。** 所以即使 validation 没出现信号，也不能直接证明 development 的结果一定是假；它只能告诉你这个 frozen candidate 在那段完全没参与选择的时间里有没有得到复制。因此下一步仍然必须把 **final holdout 留到最后**。
