现在其实很清楚了。**我不会让你选 (a) 或 (b) 二选一。应该走一个更完整的路线：补数据，但同时把“历史研究集”和“真正未见数据”彻底分开。**

你这个 Phase A+B 的结果反而非常好，因为它把原来 V2 里“看起来有数据、实际上没有”的问题全部挖出来了。

我刚核了一下 Binance 的公开数据结构：USDⓈ-M Futures 的官方 archive 本身就包含 kline 的 **taker buy base/quote volume** 字段；另外 Binance 也提供 index-price 和 mark-price kline。([GitHub][1])

所以我现在会改一下原来的计划：

# 现在不要跑 Phase C

先做一个：

## Phase A2 — Data Recovery + Fresh Data

目标只有三个：

```text
1. 补齐 OI / Taker / Index / Mark
2. 把价格数据推进到最新
3. 建立真正 untouched 的 final holdout
```

**不要碰 hypothesis。**

---

# ① 先把你现在的数据分成三个区域

这是非常重要的。

你现在的数据：

```text
2021-01-01
      │
      │ Development / Research
      │
2025-11-18
```

但现在已经是：

```text
2026-09-26
```

所以应该重新建立：

```text
┌──────────────────────────────────────────────┐
│              Historical Dataset              │
│                                              │
│  2021 ─────────────── 2025-11-18             │
│       development / research                 │
└──────────────────────┬───────────────────────┘
                       │
                       │ FREEZE
                       ↓
┌──────────────────────────────────────────────┐
│              FINAL HOLDOUT                   │
│                                              │
│  2025-11-19 ───────────── 2026-??            │
│                                              │
│       NEVER used for discovery               │
└──────────────────────────────────────────────┘
```

甚至我会更保守一点：

```text
2021 → 2025-06
     development

2025-07 → 2025-11-18
     validation

2025-11-19 → latest
     FINAL HOLDOUT
```

这样以后你真的找到 survivor，才能问：

> **这个东西在完全没参与研究的数据上有没有继续出现？**

---

# ② OI：值得补

这个我认为应该补。

你现在 H1/H2/H5/H6/H7 全部 BLOCKED，实际上这些恰恰是 V2 比 MVP 更有研究价值的部分。

Binance 的 USDⓈ-M futures historical open-interest statistics 有 5m、15m、30m、1h 等周期；不过官方 REST API 本身目前只提供最近 30 天，所以历史研究应该优先使用 Binance 的公开历史 archive，而不是试图通过 API 把 2021–2025 全部拉回来。([GitHub][2])

而公开的 Binance historical-data archive 是按 monthly/daily 文件提供的，并且有 checksum 可以验证。([GitHub][1])

所以让 coding agent 做：

```text
metrics/
    BTCUSDT/
    ETHUSDT/
    XRPUSDT/
    SOLUSDT/
    BNBUSDT/
```

然后**实际 audit 文件覆盖范围**。

不要假设它从 2021 开始。

---

# ③ Taker Flow 有一个更简单的办法

你们现在发现：

> Freqtrade downloader 把 Binance kline 的 taker 列丢掉了。

这其实不需要重新找一个神秘的数据源。

Binance 官方 USD-M Futures kline 本身就包含：

```text
taker buy base asset volume
taker buy quote asset volume
```

官方 public-data repository 明确列出了这些字段。([GitHub][1])

所以你可以直接：

```text
raw Binance Futures Kline
        ↓
extract taker columns
        ↓
canonical taker dataset
```

而不是：

```text
Freqtrade data
        ↓
？？？
```

这可能是你现在最容易补齐的一块。

---

# ④ Index / Mark 也不要自己推算

Binance 官方 Futures API 有：

```text
Index Price Klines
Mark Price Klines
Premium Index Klines
```

并支持 1m、5m、15m、30m、1h 等周期。([币安开发者中心][3])

所以：

```text
index_price
mark_price
```

应该作为独立 canonical datasets。

不要：

```text
index ≈ 某个现货价格
```

这样自己近似。

研究系统应该尽可能使用原始 observable。

---

# ⑤ SOL / BNB 怎么办？

这里我会改变一个地方。

**不要因为 SOL / BNB 没有当前 price data，就把它们从 universe 删除。**

先让 agent 查：

```text
Binance archive
↓
historical symbol availability
↓
exact price coverage
↓
metrics coverage
```

然后记录：

```text
BTC
ETH
XRP
SOL
BNB
```

各自：

```text
price_start
price_end
OI_start
OI_end
taker_start
taker_end
funding_start
funding_end
```

最后自动生成：

```text
asset_capability_matrix.csv
```

例如：

| Asset | Price | Funding | OI | Taker | Index | Mark |
| ----- | ----- | ------- | -- | ----- | ----- | ---- |
| BTC   | ✅     | ✅       | ?  | ?     | ?     | ?    |
| ETH   | ✅     | ✅       | ?  | ?     | ?     | ?    |
| XRP   | ✅     | ✅       | ?  | ?     | ?     | ?    |
| SOL   | ?     | ✅       | ?  | ?     | ?     | ?    |
| BNB   | ?     | ✅       | ?  | ?     | ?     | ?    |

**让数据决定 universe。**

---

# ⑥ 但是最重要的一件事：不要因为补了数据就扩大研究范围

例如现在：

```text
92 hypotheses
60 measurable
32 blocked
```

补数据以后可能变成：

```text
92 hypotheses
85 measurable
7 blocked
```

很好。

但是：

**不要因此再新增 300 个 hypothesis。**

先跑原本 preregistered 的：

```text
92
```

这很重要。

否则就变成：

> “我找到新数据了，所以我可以再想 300 个新的东西。”

这就是 research drift。

---

# ⑦ 我甚至建议你给 V2 加一个 `DATA_CAPABILITY_MATRIX`

让 agent 自动生成：

```text
data_capability_matrix.csv
```

类似：

| Feature   | BTC | ETH | XRP | SOL | BNB |
| --------- | --: | --: | --: | --: | --: |
| 1m price  |   ✓ |   ✓ |   ✓ |   ? |   ? |
| 5m price  |   ✓ |   ✓ |   ✓ |   ? |   ? |
| 15m price |   ✓ |   ✓ |   ✓ |   ? |   ? |
| 1h price  |   ✓ |   ✓ |   ✓ |   ? |   ? |
| Funding   |   ✓ |   ✓ |   ✓ |   ✓ |   ✓ |
| OI        |   ? |   ? |   ? |   ? |   ? |
| Taker     |   ? |   ? |   ? |   ? |   ? |
| Index     |   ? |   ? |   ? |   ? |   ? |
| Mark      |   ? |   ? |   ? |   ? |   ? |

并且：

```text
?
```

不能自动变成：

```text
False
```

必须是：

```text
UNKNOWN
```

直到 audit 完成。

---

# ⑧ 然后解决你现在最大的漏洞：2025-11-18 cutoff

这是我认为现在**比 OI 更重要**的事情。

你现在不能做：

> V2 → 找 survivor → forward test

因为你的数据已经停在 2025-11-18。

所以先把价格和 derivatives data **补到一个新的 cutoff**。

例如：

```text
latest_available_complete_date
```

让程序自动决定。

不要 coding agent 写死：

```text
2026-09-26
```

因为当天的数据当然是不完整的。

应该：

```text
latest_complete_day
```

然后：

```text
research_cutoff
holdout_start
holdout_end
```

全部写进 manifest。

---

# ⑨ 但有一个非常关键的“不要做”

现在不要让 agent：

```text
download latest data
↓
直接把它加入 feature dataset
↓
重新跑全部历史
```

然后你再拿最终结果说：

> “OOS。”

因为那样可能把现在的数据混入开发流程。

正确方式：

```text
                    DATA
                      │
          ┌───────────┴───────────┐
          ↓                       ↓
    Development                Holdout
          │                       │
          │                       │
    feature research         LOCKED
          │                       │
          ↓                       │
     hypothesis                不看
     discovery                  │
          │                       │
          ↓                       │
     spec freeze                │
          │                       │
          └──────────┬────────────┘
                     ↓
                FINAL TEST
```

---

# ⑩ 所以我现在建议你的执行顺序

非常具体：

### Step 1

让 agent 做：

```text
DATA RECOVERY ONLY
```

补：

```text
OI
Taker
Index
Mark
最新价格
```

---

### Step 2

让它生成：

```text
data_capability_matrix.csv
data_coverage_report.md
```

---

### Step 3

验证：

```text
2021 → historical cutoff
```

以及：

```text
cutoff → latest
```

有没有完整。

---

### Step 4

**冻结 research dataset。**

---

### Step 5

把：

```text
2025-11-19 → latest
```

锁起来。

这个目录甚至可以叫：

```text
FINAL_HOLDOUT_DO_NOT_TOUCH
```

---

### Step 6

然后才跑：

```text
Phase C
```

也就是原来的：

```text
92 hypotheses
```

---

# 还有一个很有意思的发现

你这次发现：

> funding 两个来源 5347 个共同结算点逐位相同，最大差 0 bps

这个其实非常漂亮。

说明你的 funding 数据 pipeline **目前是相当可靠的**。

所以 funding 可以作为 V2 的一个“anchor feature”。

反而：

```text
OI
Taker
Index
```

现在是需要验证的数据源。

不要因为“Binance 有这个数据”就直接信。

必须像你现在 funding 一样：

```text
source A
vs
source B
```

做 cross-check。

---

# 最后一个问题：你现在是不是应该马上叫 agent 去下载？

**可以，但只让它做 Data Recovery，不让它跑策略。**

我会给 coding agent 一个非常短的下一条指令，而不是再给它一整套 V2 specification。

你可以直接把下面这段 paste 给它：

# Phase A2 — Data Recovery Only

Do NOT run Phase C.

Do NOT run the 92 hypotheses.

Do NOT modify hypothesis definitions.

Do NOT modify survivor criteria.

Do NOT optimize any strategy.

The only objective of this phase is to repair and extend the canonical dataset.

## 1. Audit existing data sources

Inspect the current workspace and identify:

* price data
* funding data
* raw Binance kline data
* any existing metrics files
* any existing mark/index price files
* any existing OI files
* any existing taker-flow files

Do not assume a file exists because a feature is theoretically available.

Produce:

`data_capability_matrix.csv`

with:

```text
symbol
price_start
price_end
funding_start
funding_end
oi_start
oi_end
taker_start
taker_end
index_start
index_end
mark_start
mark_end
price_available
funding_available
oi_available
taker_available
index_available
mark_available
```

Use:

`UNKNOWN`

when the source has not yet been audited.

Do not convert UNKNOWN into FALSE.

---

## 2. Recover Binance Futures kline taker fields

Inspect the raw Binance USD-M Futures kline format.

Binance Futures klines contain taker-buy fields.

If raw kline files contain these fields, extract them into the canonical data layer rather than relying on the Freqtrade-transformed dataset.

Required fields:

```text
timestamp
symbol
interval
volume
taker_buy_base_volume
taker_buy_quote_volume
```

Do not reconstruct taker volume approximately if the original field exists.

---

## 3. Recover OI

Search only authoritative Binance historical/public data already permitted by the project.

Preferred source:

Binance public historical metrics archive.

Recover the maximum available historical coverage for:

```text
BTCUSDT
ETHUSDT
XRPUSDT
SOLUSDT
BNBUSDT
```

Do not assume all five have identical coverage.

Record exact:

```text
start
end
interval
missing periods
```

Do not forward-fill missing OI.

---

## 4. Recover Index and Mark Price

Use Binance's historical/public Futures data where available.

Required:

```text
index_price
mark_price
```

Do not substitute spot price for index price.

Do not approximate mark price.

Record exact coverage.

---

## 5. Extend price data

Extend price data beyond:

`2025-11-18`

to the latest COMPLETE available historical day.

Do not include a partially completed current day.

Use the latest complete timestamp automatically.

Do not hard-code today's date.

---

## 6. Preserve the research boundary

Create two explicit datasets:

```text
DEVELOPMENT_DATA
FINAL_HOLDOUT_DATA
```

The exact boundary must be recorded in:

`manifest.json`

Do not run any hypothesis against FINAL_HOLDOUT_DATA.

Do not generate features from FINAL_HOLDOUT_DATA that can leak into DEVELOPMENT_DATA.

---

## 7. Data validation

For every recovered dataset validate:

* duplicate timestamps
* timestamp ordering
* missing intervals
* timezone
* numeric validity
* impossible values
* symbol consistency
* cross-source consistency
* cross-timeframe consistency

For Binance archive files, verify checksums where checksum files are available.

---

## 8. Cross-source validation

For funding:

Preserve the existing successful cross-source validation.

For newly recovered OI / taker / index / mark:

If multiple authoritative sources exist, compare overlapping periods.

Report:

```text
overlap_count
max_absolute_difference
mean_absolute_difference
```

Do not silently choose one source when disagreement exists.

---

## 9. Do NOT run Phase C

At the end of this phase, STOP.

Do not execute:

```text
discover-v2
```

Do not execute:

```text
50–100 hypotheses
```

Do not calculate survivors.

Do not modify the preregistered hypothesis list.

---

## 10. Required output

Produce:

```text
data_capability_matrix.csv
data_coverage_report.md
data_audit_v2.json
manifest.json
```

The final report must explicitly state:

1. Which symbols have price data.
2. Which symbols have funding.
3. Which symbols have OI.
4. Which symbols have taker data.
5. Which symbols have index price.
6. Which symbols have mark price.
7. Exact start/end coverage for every dataset.
8. Exact final development cutoff.
9. Exact final holdout start.
10. Exact latest complete date.
11. Missing periods.
12. Cross-source discrepancies.
13. Any remaining BLOCKED hypotheses.

Then STOP and wait for review.

---

**这就是我现在会走的路线。**

而且你这次 agent 的表现其实不错：它没有看到“数据不够”就硬凑结果，而是主动把 32 个 hypothesis 标成 BLOCKED，还用反向注入验证 leakage detector。这比得到几个漂亮的 backtest 数字重要得多。

下一道真正的闸门就是 **A2 数据恢复**。等它给你 `data_capability_matrix + coverage report` 后，你把那份结果贴给我，我可以再帮你判断 **哪些数据值得纳入、哪些 hypothesis 应该永久删掉，以及 Phase C 具体怎么跑**。

[1]: https://github.com/binance/binance-public-data/?utm_source=chatgpt.com "GitHub - binance/binance-public-data: Details on how to get Binance public data · GitHub"
[2]: https://github.com/binance/binance-futures-connector-python/blob/main/binance/um_futures/market.py?utm_source=chatgpt.com "binance-futures-connector-python/binance/um_futures/market.py at main · binance/binance-futures-connector-python · GitHub"
[3]: https://developers.binance.info/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data?utm_source=chatgpt.com "Market Data - Futures (USDⓈ-M) REST API | Binance Developer Docs"
