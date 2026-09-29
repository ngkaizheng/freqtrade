# Exit-family study — RESULT

**Protocol:** `docs-myself/PREREG_EXIT_FAMILY_2026-09-27.md` (frozen before any arm ran)
**Strategy:** `user_data/strategies/RegimeBreakoutExitStudy.py`
**Gate:** `tools/verify_exit_study.py` (must pass before any number is believed)
**Report:** `tools/report_exit_study.py`
**Test window (FRESH):** 2025-11-19 → 2026-09-27, 312 days, 8 Binance USDⓈ-M perps
**Verified:** 2026-09-27 on freqtrade 2026.8, Python 3.11.9, pandas 3.0.5

---

## 0. 结论摘要（中文）

**判定：6 个 arm 全部为 NULL。这条线关闭。**

但这次实验最重要的产出，恰恰是它**证实了你的诊断、又否定了你的救援**：

| | gross R | gross t | 需要跨过的成本门槛 | 差距 |
|---|---:|---:|---:|---:|
| X0 对照（原始 3×ATR 移动止损 + ema 退出） | **−0.0780** | −1.70 | 0.2425R | 7.0 SE |
| X4（2.5×ATR 冻结止损 + 2R + 去掉 ema 退出） | **−0.0128** | **−0.20** | 0.2847R | **4.7 SE** |

1. **你的判断是对的，而且幅度比预期大。** 把 exit 换成"宽冻结止损 + 去掉 ema 退出"，把 gross 从 **−0.0780R 改善到 −0.0120R，6.1 倍**。原来的 3×ATR 每根 bar 重锚的移动止损 + `close<ema_21` 退出规则，**确实在系统性地摧毁 gross edge**。这个机制被隔离出来了。
2. **但救援不成立。** 改善后的 gross **t = −0.20，是一个统计零，不是正的**。6 个 arm 的 gross_t 绝对值全部 ≤ 1.70，冻结止损的 arm 全部 ≤ 0.49。
3. **5m 的成本门槛是 0.28R–0.49R/笔。** 要打平 12 bps 往返，entry 必须每笔产出 **+0.285R 到 +0.485R** 的 gross。实测是 **−0.013R**。**差距 3.5–7.3 个标准误。**
4. **6 个 arm 全部 0/3 子区间为正。** 没有任何一个时间子段是赚的。
5. **所以 H_a（entry 本身没有 edge）成立，H_b（exit 是约束）作为诊断成立、作为救援被否定。** 6 个 arm 是 6 次试验，不是一条连续谱——按预注册的 §6.3，null 即关闭，不再做更多 exit 搜索。

**一句话**：exit 确实是个真问题，把它修好值 0.065R 的 gross；但 5m 的成本要 0.285R 以上才回本，所以修好之后离回本还差 4.7 个标准误。**这不是一个 edge 不够大的策略，这是一个 edge 不存在的策略被放在了一个成本结构里。**

---

## 1. The full frontier — FRESH window, all 6 arms

R scale = each arm's own realised median stop distance. Nothing is hidden behind
the best cell.

| arm | stop | target | time | ema exit | trades | R_scale | **gross R** | gross t | cost R | **net R** | net t | Holm p | passes |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| **X0** control | 3×ATR trail + 0.9% | +1.8% | 90m | on | 2,662 | 0.494% | −0.0780 | −1.70 | 0.2425 | −0.3205 | −6.98 | 0.000000 | ✗ |
| **X1** | 1.5×ATR frozen | 3R | 90m | on | 3,286 | 0.247% | −0.0154 | −0.22 | 0.4850 | −0.5005 | −7.27 | 0.000000 | ✗ |
| **X2** | 1.5×ATR frozen | 3R | 180m | on | 3,252 | 0.247% | −0.0173 | −0.24 | 0.4856 | −0.5028 | −6.99 | 0.000000 | ✗ |
| **X3** | 2.5×ATR frozen | 2R | 180m | on | 2,781 | 0.421% | −0.0269 | −0.49 | 0.2844 | −0.3112 | −5.64 | 0.000000 | ✗ |
| **X4** | 2.5×ATR frozen | 2R | 180m | **off** | 2,716 | 0.421% | **−0.0128** | **−0.20** | 0.2847 | −0.2975 | −4.72 | 0.000005 | ✗ |
| **X5** | none | none | 18 bars | off | 2,349 | 0.247% | −0.0395 | −0.26 | 0.4851 | −0.5247 | −3.51 | 0.000452 | ✗ |

IAT is 2.27–2.44 on every arm (measured on the entry-time-sorted series), so
n_eff is 976–1,425. **0 of 6 arms has a positive mean net R, and 0 of 6 clears
the Holm-adjusted bar.**

### 3-way chronological sub-split (prereg §6.2) — 0/3 positive, every arm

| arm | 2025-11 → 2026-03 | 2026-03 → 2026-06 | 2026-06 → 2026-09 | positive |
|---|---:|---:|---:|---:|
| X0 | −0.1509% | −0.1979% | −0.1270% | 0/3 |
| X1 | −0.1211% | −0.1402% | −0.1107% | 0/3 |
| X2 | −0.1166% | −0.1511% | −0.1062% | 0/3 |
| X3 | −0.1212% | −0.1557% | −0.1179% | 0/3 |
| X4 | −0.1011% | −0.1613% | −0.1143% | 0/3 |
| X5 | −0.0876% | −0.1945% | −0.1055% | 0/3 |

No regime in the window rewards any arm. The null is not a sign flip.

---

## 2. What the study actually settled

### The exit diagnosis is CORRECT, and it was worth 6.1×

`X0 → X4` changes only the exit. Gross goes **−0.0780R → −0.0128R**.

The mechanism is now isolated, and it is two separate things:

1. **The 3×ATR re-anchored trail was the wrong shape.** It re-anchors to the
   latest price every candle, so on a 5m bar it sits ~0.5% away and fires on
   **53% of trades at a 44-minute average hold**. X0's exit mix is
   `trailing_stop_loss:1423 · exit_signal:613 · time_stop:411 · tp:183` — the
   1.8% target is reached on only **6.9%** of trades.
2. **The ema exit is close to pure noise.** `close < ema_21 OR close < ema_50_1h`
   on X2 fires on 489 of 3,252. In the OLD-window baseline it won **28 of 2,182
   (1.3%)**. It truncates the average hold to 47 minutes against a 90-minute
   time stop, so it removes the exact trades that need room to work.

So the user's reading of the baseline was right, and quantifying it was worth
running the study.

### The exit is NOT the binding constraint — and now that is a number, not a shrug

| arm | gross R | gross t | se R | hurdle (cost) R | shortfall |
|---|---:|---:|---:|---:|---:|
| X0 | −0.0780 | −1.70 | 0.0459 | 0.2425 | 7.0 SE |
| X1 | −0.0154 | −0.22 | 0.0688 | 0.4850 | 7.3 SE |
| X2 | −0.0173 | −0.24 | 0.0719 | 0.4856 | 7.0 SE |
| X3 | −0.0269 | −0.49 | 0.0552 | 0.2844 | 5.6 SE |
| **X4** | **−0.0128** | **−0.20** | 0.0630 | 0.2847 | **4.7 SE** |
| X5 | −0.0395 | −0.26 | 0.1495 | 0.4851 | 3.5 SE |

`gross t` is the t-statistic of the **gross** series. **|t| ≤ 0.49 for every
frozen-stop arm: the entry's gross edge is a statistical zero, not a measured
negative.** That distinction is the whole answer to the question the user posed.

The best arm, X4, needs a gross edge of **+0.285R/trade** to pay a 12 bps round
trip, and produces **−0.013R ± 0.063R**. Its 95% CI is roughly
**[−0.14R, +0.11R]**, which excludes +0.285R. **No fee level rescues it** —
including a hypothetical zero-fee world, where it is still gross-negative.

### The cost_R law, now measured on 6 independent arms

`cost_R = round_trip_bps / (stop_atr × atr_pct × 1e4)`

| arm | measured cost_R | predicted |
|---|---:|---:|
| X0 | 0.2425 | 0.2429 |
| X1 | 0.4850 | 0.4858 |
| X2 | 0.4856 | 0.4864 |
| X3 | 0.2844 | 0.2848 |
| X4 | 0.2847 | 0.2851 |
| X5 | 0.4851 | 0.4857 |

**Agreement to 3 significant figures on all six**, from a completely independent
estimation route (the realised stop distance in the trade export). The law in
`RESEARCH_STATE.md` §1c is now verified, not assumed, and it carries the verdict:
at 5m, ATR ≈ 0.165% of price, so a 1.5×ATR stop puts a 12 bps round trip at
**0.485R**. The entry would have to be more than twice as good as the 4h
signal's 0.2171R gross — at 1/48 the timeframe, in the direction the repo has
already measured as monotonically worse (1h 0.0445R, 5m ≈ 0, 4h 0.2171R).

---

## 3. The two bugs — the most transferable part of this session

Both produced a **confident, plausible, wrong table**, and both are now pinned.

### 3.1 `use_exit_signal` also gates `custom_exit`

`IStrategy._get_exit_trade_type` (`interface.py:1469`):

```python
if self.use_exit_signal:
    if exit_ and not enter:
        exit_signal = ExitType.EXIT_SIGNAL
    else:
        reason_cust = strategy_safe_wrapper(self.custom_exit, ...)(...)
```

So setting `use_exit_signal = False` to disable the `populate_exit_trend` rule
**also disables the take-profit and the time stop**, leaving the stoploss as the
only exit. The first X4 run produced **8 trades in 312 days, +0.98%, PF 4.24** —
which would have read as the best arm in the study. Fixed by keeping
`use_exit_signal = True` on every arm and emitting zeros from
`populate_exit_trend` instead.

### 3.2 `pd.Timestamp.floor("5m")` raises on pandas 3

`'m' is no longer supported` (ambiguous: minutes vs milliseconds); only `"5min"`
parses. `ShortBreakout4h` floors on `"4h"` and never hit this, so the pattern
was copied into a 5m strategy without the hazard being visible.

Consequence chain: `entry_atr` raised → caught by a local `except` → returned
`None` → `frozen_stop_price` returned `None` → `custom_stoploss` returned `None`
→ freqtrade's `strategy_safe_wrapper(..., supress_error=True)` covered the rest
→ **every frozen stop silently fell back to the class `−10%` backstop, and the
R target was silently disabled too** because `r_unit()` calls the same function.

**Three layers of silence around one bug, and X2 and X3 still printed a clean,
identical, entirely fictional row.** Fixed with
`freqtrade.exchange.timeframe_to_prev_date` (canonical, parses `"5m"`), by
re-raising rather than swallowing frequency errors, and by
`tools/verify_exit_study.py`, which **asserts the realised stop distance is not
the backstop**. An arm that runs without its stop now fails the build.

**The tell that was available for free:** X2 and X3 were byte-identical (2,294
trades, −3.34%, PF 0.64). Two arms with different stops and different targets
cannot produce the same 2,294 trades unless neither stop nor target is
reachable. **Identical rows across arms are a bug signal, not a robustness
result.**

---

## 4. What is now closed, and what is owed

**Closed:** `RegimeVolBreakout5m` and its exit family. Per prereg §6.3, a null
across all arms ends the line, and the arms are 6 trials, not a continuum. **Do
not add a 7th exit, and do not parameter-sweep the entry** — the entry is frozen
and its gross edge is a measured zero in all six configurations.

**Not owed, because no arm passed:** a forward test. There is nothing to forward.

**What would have to be true to reopen this:** the entry must produce
≥ +0.285R gross per trade at 5m. That is not a tuning question — it is 4.7
standard errors away, and the same family has now returned a gross zero on two
independent engines (`PerpTrendBreakout`, and this one) across two disjoint
windows.

**The one direction this study does *not* close** is the repo's own
best-supported finding: the **low-volatility** filter (Kurth et al.,
arXiv preprint — +38–43% gross on 51% of trades in the wide panel). Every arm
here *requires* volatility expansion. `RESEARCH_STATE.md` §1d records that the
one filter with an empirical result behind it is the opposite of this strategy's
premise. That is a genuinely different hypothesis and remains open — but it is
a **new pre-registration**, not an amendment to this one.
