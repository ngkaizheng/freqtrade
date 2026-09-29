# Round Findings: Project Freeze, Research Environment Audit, and the WeChat Note

Run 2026-09-19. Scripts: `tools/binance_stock_recheck.py`, `tools/us_equity_audit.py`,
`tools/gate0_data_feasibility.py`, `tools/download_us_long.py`,
`tools/us_long_quality_check.py`, `tools/extract_note_pdf.py`.

---

## 1. Status: this alpha-discovery round is TERMINATED

Per `TERMINAL-FINDING.md`, the crypto search has ended: **no strategy survives**
to the project's own standard. The current state is not "tune the strategy" but
"decide whether research restarts, and in what environment".

**Frozen:**
* `TERMINAL-FINDING.md` — the determination
* `LESSONS.md` — 13 errors, 17 standing rules
* `BTCSmaTrend` is **not** to be extended (no SMA-30/40/60, RSI, MACD, VIX,
  breadth, or further crypto indicator search)

**Retained:** FreqTrader as an **execution/implementation** validation
environment, not an alpha-validation one. A 90-day dry-run cannot establish a
long-horizon edge (~10–20 years needed); it *can* verify signal→order→fill→position
correctness, which is an engineering question.

---

## 2. The PDF: `Note-From-Wechat.pdf`

**Extraction succeeded.** 190 pages, ~32k characters, 122 pages with substantive
Chinese text. Extracted to `user_data/note_from_wechat.txt`.

> **Process note (lesson L7 recurring):** the console displayed the text as
> `����` and I nearly concluded the PDF had broken CMaps. Codepoint inspection
> showed U+8BFE 课, U+7A0B 程, U+5185 内, U+5BB9 容 = "课程内容". **The data was
> always fine; my Windows console was mangling it.** Reading the file with the
> file tool, not the console, resolved it immediately — the second time this
> exact trap has appeared in this project.

### What the document actually is

A **Chinese A-share short-term trading course** (量价笔记 / 打板技巧) — not US
stocks and not crypto.

Structure (from its own TOC):

| chapter | content |
|---|---|
| 第一节 | 主力吸筹判断 (accumulation detection), 洗盘 (shakeout) |
| 第二节 | 主力维护, 买入信号, "V"型维护, 左长黑右长红 |
| 第三节 | 涨停板推动原理, 主力资金检测, 盘口检测, 启动点, 连续大单 |
| 第四节 | 主力操盘成本线, 如何选股, 综合选股与步骤 |
| 第五节 | 分时相对卖点, 日线卖点, 黄金坑, 弱转强 |
| 第六节 | 如何潜伏首板, 怎么打板, 一进二条件与买点, 资金运作出货 |

Its core content is **量价关系** (price–volume relationships) — a 16-pattern
taxonomy such as 放量滞涨 (volume up, price stalls → distribution),
缩量大涨 (volume down, price accelerates → continuation), 平量大跌
(panic, no bids → acceleration down). That is exactly the volume-signal family
already tested in round 4 (`findings-volume-signals.md`), where volume carried
**0.017 Sharpe** of incremental information.

### Honest assessment of its transferability

| aspect | issue |
|---|---|
| **Market** | A-shares with **涨停板 (limit-up)** mechanics — a hard price ceiling that creates the whole 打板 edge. **US equities and crypto have no equivalent.** |
| **Mechanism** | Requires 主力 (large-player) order-flow inference from 盘口 (order book) and 分时 (intraday) data |
| **Data** | Needs tick/level-2 data and intraday snapshots. **Not in this workspace**, and not obtainable from the sources used here |
| **Sample** | Intraday pattern recognition on discretionary setups — no stated sample size or statistical test |
| **Base rates** | No win-rate, expectancy, or drawdown figures given for the patterns |

**Verdict:** it is a genuine, detailed **playbook for a different market
microstructure**. Its concepts can *inspire* hypotheses (e.g. does
volume-stall predict reversal in US large caps?), but the patterns themselves do
not transfer to US equities or crypto, and none of it is testable without
intraday/order-book data.

The one thing it does confirm: the volume–price family is a plausible place to
look, and this project already tested it in its simplest form and found nothing.

---

## 3. Binance stocks — the user was right, I was imprecise

I previously reported "spot = 0 stock instruments, futures = 199 TRADIFI
perpetuals". Re-checked thoroughly:

| finding | value |
|---|---|
| spot symbols scanned | 3,705 |
| spot stock instruments | **0** (4 "CVX" hits are **Convex Finance**, not Chevron — a false positive) |
| futures TRADIFI_PERPETUAL | **199** |
| of which stock tickers | **26** |
| `underlyingType` | **`EQUITY`** |
| `underlyingSubType` | `['TradFi']` |
| funding rate | **+0.000000** on AAPLUSDT/NVDAUSDT/SPYUSDT |
| AAPLUSDT last close | 335.41, mark 335.41 |

**Both statements are true at once, and the user is right about what they see:**
Binance does **not** offer stock **spot** (you cannot buy a share), but it **does**
list ~26 stock-tracking **perpetual futures** with `underlyingType = EQUITY`,
which the app almost certainly presents under a "Stocks"/"TradFi" tab.

Practical differences from shares: derivatives with leverage/funding, USDT-settled,
24/7, 3–8 months of history, can diverge from the real equity. **My earlier
statement was right in substance but I should have said the app shows them as a
stock product.**

---

## 4. US equity data — a material discovery

### The handoff's headline claim does not reproduce

`quant-research-handoff/README.md` states the MA200 result is based on
**"SPY 1993-2026 (33.6 years)"**. The cache it ships contains
**SPY 2010-01-04 → 2026-09-16 = 16.7 years**, first row 2010-01-04.

> **16.9 years of the claimed history is not in the shipped data.** The
> 33.6-year SPY result **cannot be reproduced from local files**. Any statement
> relying on that number should be treated as unverified until the data is
> re-obtained.

### Long history IS obtainable — verified and downloaded

Yahoo's chart API (no key, no library) returned:

| ticker | bars | range | years |
|---|---:|---|---:|
| SPY | 8,467 | 1993-01-29 → 2026-09-18 | **33.6** |
| QQQ | 6,925 | 1999-03-10 → | 27.5 |
| GLD | 5,492 | 2004-11-18 → | 21.8 |

Downloaded **40 tickers** to `user_data/data/us_long/` — up to **56.7 years**
(PG, XOM, GE, IBM, JNJ, KO from 1970-01-02), median 27.7y.

**Quality verified:** 0 duplicate dates, 0 non-positive prices, 0 `high < low`,
0 infinite returns, all 40 include `AdjClose`. Independent cross-check: new SPY
vs handoff SPY on 4,201 overlapping days gives **return correlation 0.9986** —
consistent.

> The cross-check first reported **0 overlapping days**. That was a bug in my
> *checker* (the new file's Date carries a time component; a raw string merge
> silently found no matches), not bad data — **lesson L11 again**. Normalizing
> both to tz-naive midnight fixed it.

### Power comparison — the actual point

| environment | years | SE(Sharpe) |
|---|---:|---:|
| crypto BTC daily | 14.6 | 0.257 |
| handoff equity cache | 16.7 | 0.245 |
| **new long equity (SPY)** | **33.6** | **0.173** |
| **new long equity (PG/XOM/JNJ/KO)** | **56.7** | **0.133** |

That is **1.5×–1.9× better Sharpe resolution** than crypto — the first genuine
power improvement available in this project.

**Caveats carried forward:** Yahoo `Close` is split-adjusted, not
dividend-adjusted (`AdjClose` is also saved — total return needs it, and price-only
understates equity returns by ~1–3%/yr). Effective independent bets across the
109-name handoff universe is **~5.7**, so cross-sectional tests remain
underpowered; single-asset long histories are where the real gain is.

---

## 5. Gate 0 — to be applied before any new hypothesis

Adopted from the reviewer's suggestion and consistent with lesson L1:

```
BEFORE any strategy work:
  1. Expected effect size?
  2. Independent cycles available?
  3. Independent assets available?
  4. Expected cross-correlation?
  5. Minimum detectable Sharpe difference?
  6. Required history = ?

  IF required years > available years -> REJECT the study. Do not run it.
```

**Applied to crypto trend-following in hindsight:** required ~10–20 years for a
+0.17 paired edge, available 14.6 → borderline, and it failed. **Gate 0 would
have flagged this before the search started.** That is the concrete value of
having it.

---

## 6. What is decided, and what is open

**Decided:**
* Crypto trend search is **terminated**
* FreqTrader is retained for **execution** validation only
* The WeChat note is **not** transferable as written (different market
  microstructure; needs data not available here)
* Long US-equity history **is** obtainable and is now downloaded and verified

**Open — needs a decision before work starts:**
* Whether to restart research at all
* If yes: **which alpha family**. The reviewer's framing is useful —
  **Type A (risk reduction)** is largely mechanical (this project proved that
  repeatedly) and should not be called alpha; **Type B (conditional return
  prediction)** is the real target, and must beat a **selection-adjusted placebo**
* Whether the next study is **single-asset long-history** (33–57y, best power) or
  **multi-asset/period** (more independent bets, but shorter per series)

**Not started:** no new hypothesis has been pre-registered, and no US-equity
strategy has been tested.

---

## Reproduce

```powershell
.\.venv\Scripts\python.exe tools\extract_note_pdf.py        # PDF -> text
.\.venv\Scripts\python.exe tools\binance_stock_recheck.py   # Binance equities
.\.venv\Scripts\python.exe tools\us_equity_audit.py         # SPY discrepancy
.\.venv\Scripts\python.exe tools\gate0_data_feasibility.py  # source probe
.\.venv\Scripts\python.exe tools\download_us_long.py        # 40 tickers
.\.venv\Scripts\python.exe tools\us_long_quality_check.py   # verification
```
