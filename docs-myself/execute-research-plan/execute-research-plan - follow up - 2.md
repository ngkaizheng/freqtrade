对，这份 A2 结果整体上已经把**原本的数据可用性问题基本解决了**。现在不是继续找 OI / taker / index / mark，而是先把 **A2 的审计报告本身修干净**，然后才进入 Phase C。

### 我会把当前状态判定为：Data Coverage PASS，Integrity Gate 还没完全 PASS

核心数据已经很完整：

| 数据         | BTC | ETH | XRP | SOL | BNB |
| ---------- | --: | --: | --: | --: | --: |
| Price      |   ✅ |   ✅ |   ✅ |   ✅ |   ✅ |
| Funding    |   ✅ |   ✅ |   ✅ |   ✅ |   ✅ |
| OI         |   ✅ |   ✅ |   ✅ |   ✅ |   ✅ |
| Taker flow |   ✅ |   ✅ |   ✅ |   ✅ |   ✅ |
| Index      |   ✅ |   ✅ |   ✅ |   ✅ |   ✅ |
| Mark       |   ✅ |   ✅ |   ✅ |   ✅ |   ✅ |
| Basis      |  ✅* |  ✅* |  ✅* |  ✅* |  ✅* |

而且已经延伸到 2026-08-31，正式 final holdout 也存在了。

但是我看到 **4 个需要先修的点**。

**1. Checksum accounting 有明显不一致**

例如 BTC：

> 79 files / checksum-verified 0 / unverified 0

79 个文件不可能既不是 verified，也不是 unverified。

这不一定代表数据错了，但代表 audit report 的 provenance 状态不完整。Phase C 前必须把每个文件明确归类：

`CHECKSUM_VERIFIED / NO_CHECKSUM_AVAILABLE / NOT_CHECKED / FAILED`

不能出现 79 个文件“凭空消失”。

**2. `basis = AVAILABLE`，但 coverage 全部是空的**

这是报告内部最明显的 schema inconsistency。

你现在：

```text
basis_start = blank
basis_end   = blank
basis_rows  = blank
basis_status = AVAILABLE
```

要明确 basis 到底是：

```text
basis = mark_price / index_price - 1
```

还是其他定义。

如果它是 derived feature，就应该写清楚：

```text
basis_source = derived
basis_start = ...
basis_end = ...
basis_rows = ...
```

不能只写 AVAILABLE。

**3. `Archive files fetched: 0` 需要补 provenance**

你现在明明已经有：

```text
metrics/BTCUSDT/5m
metrics/ETHUSDT/5m
...
79 files
1759 files
```

但报告却写：

```text
Archive files fetched: 0
```

这可能只是因为 coding agent 使用了已有缓存/挂载资料，而不是重新下载。

这个没问题，但必须记录：

```text
source_type
source_path
source_url/origin
first_seen
checksum_status
ingestion_timestamp
```

否则以后很难证明这次研究的数据到底来自哪里。

**4. 不要因为报告写 `92/92 testable` 就马上跑 92 个完整回测**

现在应该先做一个非常小的 **A2.5 Integrity Gate**。

尤其是 OI 是 irregular event stream，不能因为它叫 `5m` 就直接当普通完整 5-minute candle 做：

```text
forward_fill()
```

必须保持：

> signal timestamp 只能看到当时已经发生的 OI observation。

同样，funding 也必须严格按照 event timestamp 做 causal as-of join。

---

## 然后才进入 Phase C

而且这次其实比 MVP 更重要，因为现在你终于具备了真正做 derivatives regime research 的数据。

你的研究链应该变成：

```text
A2
 ↓
A2.5 Integrity / Provenance Gate
 ↓
Phase C — Regime + Derivatives Discovery
 ↓
Freeze candidate hypotheses
 ↓
Validation period
 ↓
Final Holdout
 ↓
Paper validation
```

不要碰 live trading。

你可以直接把下面这段丢给 coding agent：

# Phase A2.5 + Phase C — Integrity Gate and Derivatives Research

Spec version:
`2026-09-26-v2-regime-derivatives`

## Objective

Phase A2 has recovered the previously missing derivatives datasets.

Do NOT immediately run the full hypothesis discovery yet.

First execute a strict A2.5 integrity/provenance gate. Only when A2.5 passes should Phase C begin.

This remains a research-only project.

Do not modify `freqtrade/` core.
Do not create live trading execution.
Do not connect exchange accounts.
Do not place orders.

---

# PART A — A2.5 Integrity / Provenance Gate

## A2.5.1 Fix audit accounting

The current report contains inconsistent checksum accounting.

Example:

* 79 files
* checksum_verified = 0
* unverified = 0

Every ingested file must belong to exactly one provenance state:

```text
CHECKSUM_VERIFIED
NO_CHECKSUM_AVAILABLE
NOT_CHECKED
FAILED
```

No file may remain unclassified.

For every file record:

```json
{
  "path": "...",
  "source": "...",
  "source_type": "...",
  "checksum_status": "...",
  "checksum_algorithm": "...",
  "checksum_expected": "...",
  "checksum_actual": "...",
  "file_size": ...,
  "first_seen": "...",
  "ingested_at": "..."
}
```

If a checksum sidecar does not exist, use:

`NO_CHECKSUM_AVAILABLE`

Do NOT call this `CHECKSUM_VERIFIED`.

If the file was already present locally and was not downloaded during A2, preserve that fact explicitly.

`archive_files_fetched = 0` is acceptable only if the report also explains that the files were already available locally / mounted / cached.

---

# A2.5.2 Validate dataset row continuity

For each dataset:

* duplicate timestamps
* timestamp sorting
* timezone normalization
* invalid OHLC values
* negative volumes
* zero/invalid index or mark values
* impossible timestamp spacing
* missing periods
* overlapping files
* duplicate rows across file boundaries

Produce:

`data_integrity_v2.json`

and:

`data_integrity_report.md`

For each symbol and dataset, report:

```text
rows
start
end
duplicate_rows
missing_intervals
invalid_rows
overlap_rows
timestamp_order
```

Do not assume continuous coverage merely because start/end timestamps look correct.

---

# A2.5.3 Validate basis definition

The current coverage matrix says:

```text
basis_status = AVAILABLE
```

while basis_start/end/rows are empty.

Fix this.

First inspect the implementation and determine the exact basis definition.

If basis is derived from mark/index, explicitly record something equivalent to:

```text
basis = mark_price / index_price - 1
```

Only use the actual implementation's definition.

For every symbol report:

```text
basis_source = DERIVED
basis_start
basis_end
basis_rows
basis_missing_rows
```

Make sure basis uses only causally available mark/index observations.

Do not use future index/mark values.

---

# A2.5.4 Validate OI event semantics

Open interest is documented as an irregular event stream.

Do NOT blindly forward-fill OI.

The feature join must be causal:

```text
latest OI observation with timestamp <= signal timestamp
```

For every OI-derived feature, record:

```text
source_timestamp
signal_timestamp
age_seconds
```

Use this to test for accidental future leakage.

Create a leakage test that intentionally shifts OI timestamps forward and verify that the validation rejects the resulting feature join.

---

# A2.5.5 Validate funding semantics

Funding is 8-hour event data.

Do not treat funding as a regular hourly series.

For every signal timestamp:

```text
funding observation must be causally available at signal time
```

Document whether the current funding event is considered observable before or only at settlement.

Use the conservative interpretation already defined by the research specification.

Do not silently forward-fill future funding events backward.

---

# A2.5.6 Cross-source validation

Where overlapping authoritative sources exist, compare:

* OI
* taker flow
* index price
* mark price
* funding

For each dataset pair report:

```text
overlap_rows
max_abs_diff
mean_abs_diff
median_abs_diff
exact_match_rate
```

Any discrepancy above tolerance must be reported.

Do not silently overwrite one source with another.

---

# A2.5.7 Data capability matrix

Regenerate:

`data_capability_matrix.csv`

Required fields:

```text
symbol
price_start
price_end
price_rows
price_status

funding_start
funding_end
funding_rows
funding_status

open_interest_start
open_interest_end
open_interest_rows
open_interest_status

taker_flow_start
taker_flow_end
taker_flow_rows
taker_flow_status

index_price_start
index_price_end
index_price_rows
index_price_status

mark_price_start
mark_price_end
mark_price_rows
mark_price_status

basis_start
basis_end
basis_rows
basis_status
```

Every AVAILABLE field must have actual coverage metadata.

---

# A2.5.8 Holdout verification

Do not change the already recorded research boundary after looking at the holdout.

Current boundary:

```text
development:
2020-02-01 00:00:00
through
2025-06-06 22:12:00

validation:
2025-06-06 22:12:00
through
2025-11-18 22:12:00

final_holdout:
2025-11-18 23:00:00
through
2026-08-31 23:00:00
```

Verify that:

1. development code cannot access final_holdout
2. discovery code cannot access validation unless explicitly invoked by a later validation stage
3. final_holdout remains untouched
4. holdout access is logged

Do not redefine these dates based on observed performance.

---

# A2.5.9 A2.5 PASS criteria

A2.5 passes only if:

* all files have provenance status
* no checksum failures
* all datasets have deterministic timestamp ordering
* duplicate policy is explicit
* basis metadata is complete
* OI joins are causal
* funding joins are causal
* no feature leakage test failure
* holdout isolation test passes
* capability matrix has no AVAILABLE fields with missing coverage metadata

If any condition fails:

STOP.

Do not run Phase C.

---

# PART B — Phase C: Regime + Derivatives Discovery

Run Phase C only after A2.5 PASS.

Do not modify the preregistered hypothesis list merely because a result looks weak.

Do not perform generic hyperparameter optimization.

Do not create thousands of arbitrary parameter combinations.

The purpose is economic hypothesis testing, not curve fitting.

---

# B1 Universe

Research universe:

```text
BTCUSDT
ETHUSDT
XRPUSDT
SOLUSDT
BNBUSDT
```

Do not add/remove symbols based on preliminary performance.

Only remove a symbol when the required data capability genuinely fails.

---

# B2 Timeframes

Primary research:

```text
15m
1h
```

Secondary confirmation:

```text
5m
30m
4h
```

1m remains primarily an execution-resolution dataset.

Remember the previously documented funding aliasing issue.

Do not use 5m funding-derived signals as primary discovery features.

---

# B3 Feature families

Generate causal features from:

## Price / trend

* returns
* EMA slope
* moving-average distance
* breakout state
* trend strength
* multi-timeframe alignment

## Volatility

* realized volatility
* ATR
* volatility percentile
* compression
* expansion
* volatility shock

## Open interest

* OI level
* OI change
* OI return
* OI acceleration
* price/OI divergence
* OI contraction after price expansion
* OI expansion during breakout

OI must remain an irregular observation stream before causal as-of joining.

## Funding

* funding level
* funding z-score
* funding extreme
* funding change
* funding persistence
* price/funding divergence
* funding/OI interaction

Funding remains event-based.

## Taker flow

Use the recovered Binance kline taker-buy data.

Derive:

```text
taker_sell = volume - taker_buy_volume
```

Then derive causal:

* buy ratio
* sell ratio
* net taker flow
* flow acceleration
* flow shock
* price/flow divergence

## Basis

Use the validated basis definition from A2.5.

Generate:

* basis level
* basis z-score
* basis extreme
* basis change
* price/basis divergence
* basis/OI interaction

## Index / mark

Generate:

* mark-index spread
* mark/index deviation
* spread shock
* spread persistence

---

# B4 Regime engine

Build an explicit regime classifier.

Minimum dimensions:

```text
trend
volatility
liquidity
open_interest_state
funding_state
```

Trend states:

```text
STRONG_UP
WEAK_UP
NEUTRAL
WEAK_DOWN
STRONG_DOWN
```

Volatility:

```text
LOW
NORMAL
HIGH
EXTREME
```

Avoid percentile saturation.

The previously discovered trend-classification bug must not return.

Use the validated absolute-threshold / standardized-score implementation already documented in the preregistration unless the frozen specification explicitly states otherwise.

---

# B5 Conditional return research

Before translating every feature into a strategy, calculate conditional forward returns.

For each feature/regime condition evaluate:

```text
5m forward return
15m forward return
30m forward return
1h forward return
4h forward return
```

Also calculate:

```text
sample_count
mean
median
std
win_rate
MAE
MFE
```

All forward-return windows must be strictly future relative to the feature timestamp.

---

# B6 Hypothesis families

Use the existing 92 preregistered hypotheses.

Do not add arbitrary new hypotheses during this run.

Expected high-level families include:

1. trend + OI
2. OI divergence
3. funding extremes
4. funding + price divergence
5. funding + OI
6. price + OI + taker flow
7. OI contraction after large price move
8. volatility compression / expansion
9. volatility shock
10. basis extremes
11. basis + OI
12. cross-asset confirmation
13. BTC regime filter
14. multi-timeframe confirmation
15. regime-specific activation

The report must state which hypothesis IDs were tested.

---

# B7 Testing protocol

Use:

```text
development data ONLY
```

for the initial Phase C discovery.

Use the preregistered rolling walk-forward structure.

Required outputs for each hypothesis:

```text
sample_count
mean_return
median_return
win_rate
profit_factor
expectancy
max_drawdown
MAE
MFE
Sharpe
Sortino
DSR
Reality Check
base-cost result
stress-cost result
fold-level results
```

Base cost:

```text
5 bps fee per side
1 bps slippage per side
```

Stress cost:

```text
10 bps fee per side
3 bps slippage per side
```

Funding:

```text
conservative adverse-payer only
no funding credit
```

Leverage:

```text
1x
```

Do not optimize these costs around the results.

---

# B8 Multiple testing

Because 92 hypotheses are being tested:

* preserve hypothesis IDs
* preserve trial ledger
* apply the preregistered multiple-testing procedure
* preserve raw p-values and adjusted values
* run Reality Check across the tested universe
* calculate DSR

Do not report only the best-looking hypothesis.

Report the entire tested population.

---

# B9 Candidate survivor gates

Use the existing preregistered research gates.

A candidate can only become a research survivor if all required conditions pass:

```text
OOS expectancy > 0
stress expectancy > 0
base PF > 1.05
stress PF > 1.00
minimum 200 OOS observations/trades
positive expectancy in >= 60% of folds
DSR > 0
Reality Check p < 0.05
no single fold contributes >35% of total OOS profit
```

These are research-selection criteria only.

Do not convert them into live trading instructions.

---

# B10 Required outputs

Create:

```text
user_data/strategy_factory_runs/v2/<run_id>/
```

Required:

```text
manifest.json
trial_ledger.jsonl
hypothesis_results.csv
regime_summary.csv
conditional_returns.csv
fold_results.csv
multiple_testing.json
data_snapshot.json
report.md
report.html
```

Also preserve:

```text
data_capability_matrix.csv
data_integrity_v2.json
data_integrity_report.md
```

---

# B11 Failure behavior

The following outcomes are valid:

```text
0 survivors
1 survivor
multiple survivors
```

A zero-survivor result is a valid research result.

Do not loosen thresholds after seeing the results.

Do not silently remove weak hypotheses.

Do not introduce new parameters to rescue a failed hypothesis.

---

# B12 Final stop condition

After Phase C:

STOP.

Do not:

* run final_holdout yet
* optimize survivors further
* create a live Freqtrade strategy
* deploy a bot
* place trades
* change the preregistration

The next step after Phase C will be a separate validation stage using the frozen candidate set.

Print at the end:

```text
A2.5 STATUS: PASS / FAIL
PHASE C STATUS: COMPLETE
HYPOTHESES TESTED: X
SURVIVORS: X
FINAL HOLDOUT ACCESSED: NO
LIVE TRADING CODE CREATED: NO
```

最重要的一点是：**现在已经不是缺数据了，而是要防止“数据虽然很多，但 join/时间语义偷偷 leakage”**。这一步做好后，Phase C 才真正有研究价值。

而且这次的 2025-11-19 → 2026-08-31 数据量已经足够做一个真正独立的 **final holdout**，所以千万不要现在提前把它拿来挑策略。
