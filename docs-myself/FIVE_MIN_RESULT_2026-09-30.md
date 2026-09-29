# §40 — THE 5m COST LAW IS NOW MEASURED, AND THE LAST EXTRAPOLATION IN THE MACHINERY IS GONE

**Date:** 2026-09-30
**Prereg:** `docs-myself/PREREG_FIVE_MIN_2026-09-30.md` (written before any 5m bar was downloaded)
**Tools:** `tools/perp_short/probe_5m_feed.py` (Gate 0), `tools/perp_short/five_min_horizon.py`
**Raw:** `user_data/logs/{probe_5m_feed,five_min_download,five_min_horizon,five_min_crash,five_min_download}.txt`
**Result:** `user_data/perp_short_out/five_min.json`, `user_data/perp_short_out/five_min_rows.csv`
**Data:** 568 monthly archives, **94 MB**, `user_data/data/five_min/`
**No backtest was run. The deployed book is untouched.**

---

## 1. What was actually unmeasured

§35 built the pre-screen that closes a mechanism family from arithmetic before any research
is spent. Thirteen families came out refused. §38d named the one input that was still an
**extrapolation wearing a measurement's label**: the 5m ATR, obtained by taking a square
root of time from the 1h anchor. **That is now measured**, and it is the last such number
in the closed-list machinery.

## 2. The measurement

40 of 40 deployed symbols, 13 months (2025-01 → 2026-01), 505 of 520 archives, 114,048 5m
bars per full-coverage symbol.

> **The one rule this tool exists to obey:** each symbol's 4h ATR% is computed over
> **exactly that symbol's own 5m date range**. A symbol listed in 2025-06 has 5m data from
> 2025-06 and 4h data from 2023; averaging them over different windows is the §39 mistake
> at a new horizon. Symbols with short histories (HYPE 2025-05-30, ASTER 2025-09-19) have
> correspondingly short 4h windows, and the tool prints the window per symbol so the
> pinning is visible rather than promised.

| | value |
|---|---:|
| median ATR% **5m** | **0.372 %** |
| median ATR% **4h** (same symbols, same windows) | **2.953 %** |
| **r = atr5m / atr4h**, route 1 (ratio of medians) | **0.1260** |
| **r**, route 2 (median of per-symbol ratios) | **0.1256** |
| r on the **top-decile volatility days** (D2) | **0.1645** |
| √t prediction, 1/√48 (D3) | 0.1443 |

**The two independent routes agree to 0.3 %.** Per-symbol r spans 0.116 (PUMP) to 0.157
(CRV), and 38 of 40 sit inside 0.118–0.134.

## 3. The result

With `cost_R = bps / (stop_mult × atr% × 1e4)` at the **deployed** stop multiple of 4.0:

| | 5m measured | 5m pre-screen extrapolated | ratio |
|---|---:|---:|---:|
| **calm, 12.0 bps** | **0.0806** | 0.155 | 1.92× |
| **stress, 34.9 bps** | **0.2451** | 0.452 | 1.84× |

> **⚠ THE EXTRAPOLATION WAS ~1.85× TOO PESSIMISTIC IN BOTH REGIMES. It was closing this
> family partly on a cost that was too high** — in the family's own disfavour.
>
> **And the family is still closed.** That is the strong form of a closure: it survives a
> correction that ran *against* it.

**D1 gate (pre-registered before the data existed):** the family is open at the stress bar
iff `r ≥ 0.0308 / 0.15 = 0.2053`.
**Measured r = 0.1256. It is short by 1.63×.**

**D3:** measured / √t = **0.87×**, inside the pre-registered 1.5× band, so §38d's claim that
"the conclusion survives any plausible ATR" is **confirmed on a measured number** rather
than on a range.

**VERDICT: the 5m liquidation-cascade family is CLOSED.** Calm passes (0.0806 < 0.15),
stress fails (0.2451 > 0.15) — **and stress is the only regime in which a liquidation
cascade exists.**

## 4. ⚠ The part that nearly made this a near-miss, and why it isn't

The first complete run produced a result I did not trust, and the reason is worth more
than the number.

**The top-decile volatility days gave r = 0.1645, not 0.1256** — the ratio *rises* with
volatility, and it was rising *toward* the 0.2053 gate. My own reasoning at that point was:
a genuine COVID-magnitude crash might plausibly reach the gate, and the margin (1.25× on the
stress proxy) was **smaller than the correction the measurement had just applied (1.84×)**.
That is not a closure, that is an unresolved.

**So I measured a real crash.** 63 more archives, 2020-01 → 2020-07, the 10 deployed
symbols that existed then, 4h **aggregated upward** from the 5m bars (the 4h panel starts
2023-01-01, so there is no 4h feed for 2020).

**Positive control first, because every "aggregated" row depends on it.** Aggregating 5m to
4h and computing the ATR must reproduce the real 4h feed:

```
POSITIVE CONTROL, 4h aggregated from 5m vs the real 4h feed (40 symbols)
  median relative gap: 0.000%   max 5.874%   PASS - the aggregated route is valid
```

**And the crash answer:**

| cohort | symbols | 4h source | r (route 1) | r (route 2) | stress-proxy r |
|---|---:|---|---:|---:|---:|
| 2025-01 → 2026-01 (deployed universe) | **40/40** | real feed | 0.1260 | 0.1256 | 0.1645 |
| **2020-01 → 2020-07 (COVID crash)** | 10 | aggregated | 0.1228 | 0.1213 | **0.1641** |

> **r is the same in a COVID crash as in a calm year — 2.6 % apart overall, 0.2 % apart on
> the stress proxy.** The hypothesis that the ratio would rise into the gate is **refuted by
> the crash itself.** The ratio is a stable property of the horizon, which is why the 1.63×
> margin is a real margin and not an artefact of the calm sample.

**D4, handled honestly.** The crash run **returned `VERDICT: BLOCKED (D4)`** — fewer than 25
symbols — and that is the correct output for *the deployed universe's ATR%*, which is what
D4 was written about. **The crash cohort was not in the preregistration.** It is reported
because the quantity it measures is a **ratio**, and §39 established that a ratio is a
property of the horizon rather than of the universe (the 1h/4h ratio held across a 23- and
a 40-symbol panel). **That is an argument made after seeing a result, and it is labelled as
one rather than smuggled into the preregistration.** It does not change the verdict: the
40/40 cohort alone already closes the family.

## 5. Four bugs, one signature

Every one of these produced the same output: **a confident, well-formatted "0 of N".**

| # | what was wrong | how it looked |
|---|---|---|
| 1 | `archive_symbol` did `split("_")[0]` on `BTC_USDT_USDT` → **`BTC`**; Binance Vision needs `BTCUSDT` | Gate 0: **0 of 40 reachable in every month** |
| 2 | the monthly CSV **has a header row**; reading it `header=None` shifts every column | download: **0 of 520 available** |
| 3 | `pd.read_csv` on a re-wrapped `BytesIO` raised UnicodeDecodeError on a pure-ASCII file | same |
| 4 | the 4h panel is `BTC_USDT_USDT-…feather`; the code looked for `BTCUSDT-4h-…` | "**no symbol has both 5m and 4h data**" — printed *after a completely successful download* |

> **A 0 % or 100 % success rate is a BUG SIGNATURE, not a data result.** Real feeds fail
> partially; they do not fail perfectly. Both tools now refuse to report a data verdict on
> an all-or-nothing outcome and say the probe is broken instead (exit code 3). **Bug 4 is
> the one to generalise from: a single failure message must never be reported for several
> different failures** — it sent the diagnosis at the download, which had worked.

**And one honest note about the round's own process.** The pre-registration was written
*after* Gate 0 and *before* any data, which is the right order; but the crash cohort in §4
was designed *after* seeing the calm result. It is labelled as an argument, not folded into
the preregistration, because a preregistration edited to fit what you found is not one.

## 6. What this closes, and what it does not

**CLOSED, now on a measurement:** the 5m liquidation-cascade family, and with it the last
extrapolated input in the pre-screen. `family_prescreen.py` now reads
`user_data/perp_short_out/five_min.json` for the 5m row instead of extrapolating, so the
screen has **one** source for the number and the `*`-flag ("ASSUMED") is gone from it.

**NOT closed by this round, and stated so:**

* **Nothing about 5m in general.** This closes one family. §18c's measured 1h gross edges of
  0.32–1.50 bps still apply, and the cost law now says a 5m round trip costs **0.081 R calm
  / 0.245 R stress** — a new intraday hypothesis must clear that, not a guessed one.
* **D5 was not invoked.** An OPEN verdict would not have authorised a 5m backtest; the next
  gate would be §15c-5 (PC1 loading + a net long-short leg, by regression) on price data
  alone. The verdict is CLOSED, so none of that starts.
* **The deployed book.** No config, strategy, risk level, universe or position changed. The
  4h cost law is untouched by this round; F-1 measures a horizon this book does not trade.

## 7. The two constants this adds to §4

| quantity | value | universe | window | source |
|---|---:|---|---|---|
| **5m ATR%, deployed universe** | **0.372 %** | 40 symbols | 2025-01 → 2026-01 | `five_min_horizon.py`, 4h pinned per symbol |
| **5m/4h ATR ratio** | **0.126** (0.165 on the top-decile volatility days) | 40 / 10 | 2025-26 / 2020 crash | same; crash cohort independent of the verdict |
| **5m cost_R** | **0.0806 calm / 0.2451 stress** | — | — | `cost_R = bps/(4·atr%·1e4)` |

**Together with §39 these are the full measured horizon ladder for this universe:**

| horizon | median ATR% | ratio to 4h | cost_R calm | cost_R stress |
|---|---:|---:|---:|---:|
| **4h** | 2.953 % | 1.000 | 0.0106 | 0.0308 |
| **1h** | 1.210 % | 0.474 | 0.0223 | 0.0650 |
| **5m** | 0.372 % | 0.126 | 0.0806 | 0.2451 |

**Every row is measured, and the 5m row was the last one that was not.**
