# GATE 0 — Statistical Power Pre-Check

**Run this BEFORE any new hypothesis is tested.** It exists because this project
spent five rounds discovering, empirically, that its data could not answer its
question — a failure that was computable in advance.

---

## Why it exists

Crypto trend-following (BTC daily, 14.6y) required **~10–20 years** of forward
data to detect its own claimed effect. Available: 14.6 years. It failed.

**Gate 0 would have flagged that before a single backtest ran.** That is the whole
point: reject an underpowered study at design time, not after months of work.

---

## The checklist

Answer all six. If **required history > available history**, stop.

| # | question | how to compute |
|---|---|---|
| 1 | Expected effect size? | from prior work or theory, in Sharpe or paired-return terms |
| 2 | Independent cycles available? | count regimes/drawdown episodes, **not** rows |
| 3 | Independent assets available? | count assets, then correct for correlation |
| 4 | Expected cross-correlation? | from the return correlation matrix |
| 5 | Minimum detectable Sharpe difference? | ≈ 2.8 × SE for 80% power |
| 6 | Required history? | see formulas below |

### Formulas

**Resolution limit (Lo 2002):**
```
SE(Sharpe) ≈ 1 / sqrt(YEARS)
```

**Required years for a PAIRED comparison (this project's actual claim type):**
```
T_required ≈ (2.8 / effect)²      for an absolute Sharpe vs zero
T_required ≈ sd(diff)² × infl / (effect/2.8)²   for a paired difference
```
where `infl` is the autocorrelation variance inflation factor
(`1 + 2·Σ(1-k/T)·ρ_k`). **Ignoring `infl` understates the requirement** — it was
1.556× here.

**Effective independent assets:**
```
N_eff = (Σλ)² / Σλ²      from eigenvalues of the correlation matrix
```

**Minimum backtest length:**
```
MinBTL ≈ 2·ln(N_trials) / SR²   years
```

---

## Worked examples from this project

| study | claim type | required | available | Gate 0 verdict |
|---|---|---|---|---|
| BTC SMA-50 trend | paired edge +0.17 | ~10–20y | 14.6y | ⚠️ borderline |
| anything after 176 trials | MinBTL 15.5y | 15.5y | 14.6y | ❌ **reject** |
| 20-major cross-section | 20 assets | ~2.6 effective | — | ❌ reject as independent test |
| 109 equities cross-section | 109 assets | ~5.7 effective | — | ⚠️ weak |
| **SPY single-asset, long history** | risk question | ~5y at SE 0.173 | **33.6y** | ✅ **passes** |
| **PG/XOM/JNJ single-asset** | risk question | ~3y at SE 0.133 | **56.7y** | ✅ **passes** |

---

## Environment power table (verified from local data)

| environment | series | years | SE(Sharpe) |
|---|---|---:|---:|
| crypto | BTC/USD daily | 14.6 | 0.257 |
| handoff equity cache | SPY | 16.7 | 0.245 |
| **US long (downloaded)** | SPY | **33.6** | **0.173** |
| **US long (downloaded)** | PG, XOM, GE, IBM, JNJ, KO | **56.7** | **0.133** |
| **US long (downloaded)** | median of 40 tickers | 27.7 | 0.190 |

Data at `user_data/data/us_long/`, verified 0 duplicates / 0 bad prices /
SPY cross-check r = 0.9986.

---

## Known data caveats (carry into any study)

1. **Yahoo `Close` is split-adjusted, not dividend-adjusted.** Use `AdjClose` for
   total return; price-only understates equity returns by ~1–3%/yr.
2. **Survivorship.** The 40 tickers are today's survivors. Bias largely cancels in
   *relative* comparisons (both legs share the universe) but inflates absolute
   numbers.
3. **Cross-sectional independence is weak**: 109 names ≈ 5.7 effective bets.
   Single-asset long histories are where the real power is.
4. **Regime count is the true n**, not row count. 33 years contains maybe 4–6
   independent major regimes — so a long history is not unlimited evidence.
5. **No order-book / intraday data** is available here, which rules out any
   microstructure-based hypothesis (including the WeChat note's patterns).

---

## Template

```
STUDY: ______________________          DATE: __________

1. Expected effect size      : ______ Sharpe / ______ paired return
2. Independent cycles        : ______
3. Independent assets       : ______  (effective N_eff = ______)
4. Expected correlation      : ______
5. Min detectable difference : ______  (2.8 × SE)
6. Required years            : ______
   Available years           : ______
   Autocorrelation inflation : ______

GATE 0 RESULT:  [ ] PASS  -> pre-register and proceed
                [ ] REJECT -> do not run; record why

If REJECT, state which input would have to change:
________________________________________________________
```

---

## Honest note on what Gate 0 is not

Gate 0 filters **underpowered** studies. It does **not** protect against
selection bias, look-ahead, or metric-mining — those need pre-registration and
the selection-adjusted placebo tests already in `LESSONS.md` (L3, L5, L9, L10).

**Both are required.** Power without pre-registration still lets you mine; 
pre-registration without power gives you a well-specified study that cannot
conclude anything.
