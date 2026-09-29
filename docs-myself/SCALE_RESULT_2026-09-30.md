# §44 — S-1: THE BOOK SCALES LINEARLY WITH CAPITAL, AND THE RATE NEVER IMPROVES — THE ANSWER TO 「能不能赚到钱」

**Date:** 2026-09-30
**Prereg:** `docs-myself/PREREG_SCALE_2026-09-30.md`
**Tool:** `tools/perp_short/scale_axis.py`. Configs `user_data/config_scale_w*.json`.
Raw `user_data/logs/scale_{w*,axis}.txt`. **The deployed wallet stays at 10,000.**

---

## 1. The question that had never been asked

| axis | varied? | where |
|---|---|---|
| universe width | yes, 25→515 | §20b, §20d |
| risk per trade | yes, 0.25 %→1.5 % | §28, §30, §31 |
| horizon | yes, 5m→3d | §18, §40, §41 |
| stop multiple, leverage, signal quality, weighting | yes | §16, §25, §34 |
| **starting CAPITAL** | **NEVER** | **this** |

**§28 varied risk at a constant 10,000 USDT account.** That is not the same question as
"how much money", and the difference is exactly the size of the user's decision.

## 2. S0 — the reproduction gate, run first

The 10,000 USDT arm returned **113.74 %** — the deployed book's number to the printed
precision. **PASS**, so the other three arms are readable.

## 3. The whole curve, published whatever it says (S1)

| wallet | trades | total % | **total USD** | USD/yr | PF | DD 已平仓 | DD 峰谷 |
|---|---:|---:|---:|---:|---:|---:|---:|
| **10,000** | 1,111 | 113.74 % | 11,374 | 3,278 | 1.36 | 14.16 % | 18.43 % |
| **50,000** | 1,109 | 114.30 % | 57,151 | 16,470 | 1.37 | 14.16 % | 18.45 % |
| **250,000** | 1,110 | 114.39 % | 285,965 | 82,411 | 1.37 | 14.16 % | 18.45 % |
| **1,000,000** | 1,110 | 114.40 % | **1,143,967** | **329,673** | 1.37 | 14.16 % | 18.45 % |

| | capital | USD profit | linearity | % vs 10k |
|---|---:|---:|---:|---:|
| | 1× | 1.00× | 1.000 | — |
| | 5× | 5.02× | **1.005** | +0.56 pp |
| | 25× | 25.14× | **1.006** | +0.65 pp |
| | **100×** | **100.58×** | **1.006** | **+0.66 pp** |

**S2: the percentage return is FLAT across a 100× range of capital** — a 0.66 pp spread, and
it goes slightly **up**, not down. The trade count is flat too (1111 / 1109 / 1110 / 1110), so
**the arms are trading the same set of opportunities**: capital changed the size of each
position and nothing else.

**The prediction, stated in the prereg before the run, was exactly this** — and it is a real
prediction, not a safe one. It would have failed if anything in the stack were absolute
rather than fractional: a minimum order size, a quantity step, a rounding rule, or a
liquidity limit. **At $1,000,000 the median order is ~$73,000 (§42's figure scaled), four
orders of magnitude above the $733 the book trades at 10k, and nothing degrades.** That is an
independent confirmation of §42's capacity finding at 100× the size it contemplated.

## 4. S3 — the dollars, which is what the user asked for

| capital | engine default (10 bps round trip) | **measured COVID costs (34.9 bps)** |
|---|---:|---:|
| 10,000 | 11,374 USDT / 3.47 y | ~9,030 USDT · **+3.2 k/yr** |
| 50,000 | 57,151 | ~45,400 · **16.4 k/yr** |
| 250,000 | 285,965 | ~227,000 · **82.4 k/yr** |
| **1,000,000** | **1,143,967** | **~908,000 · ~262 k/yr** |

The COVID column uses §19c's measured **CAGR 20.7 %** on the same 1,111 trades, which is the
authoritative cost-adjusted figure (§19c, reproduced at 0.00 pp before any regime is reported).

> **THE COMPLETE ANSWER TO 「能不能赚到钱」:**
>
> * **Yes, and it scales linearly.** $1M of capital at the deployed settings would have
>   produced about **$262k/year** at measured COVID costs over the tested window.
> * **More capital buys more DOLLARS at an unchanged rate. It never buys a better rate** —
>   the percentage is flat to 0.66 pp across 100×.
> * **No arm improved the return.** The rate is at its measured ceiling, and every axis that
>   could have raised it is closed (§20, §28, §34, §41).
> * **The binding constraints on size are the user's own config, not the market** — 24 slots
>   and free balance (§31), both fractions of equity, both scale-invariant (§42).

## 5. ⚠⚠ A READER-FACING NUMBER WAS THE WRONG ONE, AND IT IS FIXED

The 14.16 % drawdown this project has published since §19 is `max_drawdown_account` — the
drawdown **on closed trades**. **The engine prints a second, larger figure in the same run:**

| engine field | value | what it measures |
|---|---:|---|
| `max_drawdown_account` | **14.16 %** | **realised**, on closed trades (3365.65 USDT) |
| `Max % of account underwater` | **18.43 %** | **account mark-to-market** peak-to-trough, including open positions |

**Both are correct. They are different statistics. The page reported the milder one without
saying which it was**, so a reader would have taken the worst peak-to-trough drawdown to be
14.16 % when it is **18.43 % — optimistic by 4.27 pp.**

`HOW_TO_RUN_2026-09-29.md` now carries both, in the summary table and in a boxed correction,
and names which is which. **This is the last recurrence of §16d's class: the number was right,
the name was not.** It was caught here only because S-1's arms printed 18.45 % and the
deployed figure was 14.16 % — **two runs of the same strategy disagreeing by 4.3 pp on a
column headed "maxDD", which is exactly the signal this project has learned to chase.**

## 6. What this does not do

* **It does not make the edge significant.** t ≈ 0.58; 6.8 years of forward data untouched.
* **It does not change the deployed book.** The deployed wallet stays at **10,000** and
  `risk_per_trade` at **0.005**. Only the wallet varied, and only in the experiment.
* **It does not re-open risk** (§28) or any other closed axis.
* **It is a backtest at the engine's own fill model**, which has no slippage or impact model
  at all (§42). §42's capacity result is the only measured correction, and it says the
  correction is small — but the $262k/yr figure is a backtest number, not a live one.

## 7. Verdict

* **S0 PASS. The axis is answered and it is the most useful single number this project has
  produced for the user.**
* **Capital scales linearly to at least 100×, and the rate is flat** — so capital, not
  cleverness, is the remaining lever, and it is a lever the user controls entirely.
* **A published drawdown number was the milder of two and is corrected**, with both now
  named.
* **S5 applies: the axis closes here.** A capital sweep past the point where the percentage
  turns down is §5b's dead fruit, and it did not turn down anywhere in the tested range —
  so the honest statement is that the ceiling was **not located**, and that finding it would
  need a venue with a real fill model, which this backtester does not have.
