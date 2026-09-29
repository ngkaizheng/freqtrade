# PREREG — S-1: DOES CAPITAL SCALE, AND WHAT DOES THE BOOK ACTUALLY MAKE IN DOLLARS?

**Written:** 2026-09-30, before any capital arm was run.
**Motivation:** every axis is closed, the apparatus is verified, capacity does not bind. The
one question the user actually asks — 「能不能赚到钱、赚多少」 — has never been answered in
dollars, and **capital itself has never been varied.**

---

## 1. What has and has not been varied

| axis | varied? | where |
|---|---|---|
| universe width (N) | yes, 25→515 | §20b, §20d |
| risk per trade | yes, 0.25 %→1.5 % | §28, §30, §31 |
| horizon | yes, 5m→3d | §18, §40, §41 |
| stop multiple | yes | closed |
| exchange leverage | yes, 1×→20× | §16c |
| signal quality / weighting | yes | §25, §34 |
| **starting CAPITAL** | **NEVER** | **this** |

**§28 varied risk at a constant 10,000 USDT account.** That answers "how much risk per
trade", not "how much money". The two are not the same question, and the difference is
exactly the size of the user's decision.

## 2. What every measured result implies, stated as a PREDICTION

The deployed config makes **every constraint a fraction of equity**:

* `risk_per_trade: 0.005` — position = `risk / (4 × ATR%)` of equity
* `max_stake_frac: 0.25` — a per-position cap that is **also** a fraction
* `stake_amount: "unlimited"`, `max_open_trades: 24` — a **count**, so scale-free
* §31 measured committed p90 = 99.4 % and peak concurrency 25 at 0.5 % risk

> **PREDICTION (stated before running): the PERCENTAGE return is invariant to capital, and
> the absolute profit scales linearly.** Every term in the P&L is a fraction of equity, so
> there is no mechanism by which a different starting balance could change the return rate.
>
> **This is a falsifiable prediction, not a safe one.** It fails if anything in the stack is
> absolute rather than fractional — a minimum order size, a rounding rule, an exchange
> quantity step, or a liquidity limit. **And §42 measured that at 1M USDT the median order
> is ~$73,000, which is four orders of magnitude above the $733 the book trades at 10k, so a
> liquidity effect is not implausible a priori.**

## 3. Pre-registered decisions

**S0 — REPRODUCTION GATE.** The **10,000 USDT arm must reproduce the deployed book to within
0.05 pp (113.74 %)**. If it does not, no other arm may be read.

**S1 — the arms.** 10k / 50k / 250k / 1,000,000 USDT. Four arms, fixed in advance, **all
published whatever they say** (the §41 H4 rule). Everything else identical: N=40,
`risk_per_trade 0.005`, `atr_stop 4.0`, 4h, `perp_leverage 1.0`, same date range, same
strategy class, no parameter touched.

**S2 — what decides the axis.**
* **percentage return flat** ⇒ capital is the only lever left, and the honest answer to
  「能不能赚钱」 is *yes, linearly, and the rate never improves*.
* **percentage return falls with capital** ⇒ something binds that is not a fraction, and
  **naming it is the result** — a real capacity ceiling that §42's aggregate-volume
  extrapolation would have missed.

**S3 — report absolute USD, not just percent.** The user asked in dollars. Each arm's
`profit_total_abs` is the number, and the per-year figure too.

**S4 — the scaling law is tested, not assumed.** If the absolute profit is *proportional* to
capital across all four arms, say so with the fit. If it is sub-linear, the shortfall is the
finding and the smallest capital at which it starts is reported.

**S5 — KILL.** Four arms. If the percentage is flat at every rung, **this axis closes and is
not revisited**: a capital sweep past the point where the percentage turns down is §5b's dead
fruit.

## 4. What this does NOT do

* **It does not make the edge significant.** t ≈ 0.58 and 6.8 years of forward data are
  untouched by anything here.
* **It does not change the deployed book.** The deployed wallet stays at 10,000. This measures
  what the *same* configuration would do at other sizes, which is an input to the user's
  decision, not a configuration change.
* **It does not re-open risk.** `risk_per_trade` is held at 0.005 in every arm; only the
  wallet changes.
