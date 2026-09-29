# START HERE — new session

**Read this, then `docs-myself/RESEARCH_STATE.md` (the canonical record) and [`docs-myself/RESEARCH_GOAL.md`](RESEARCH_GOAL.md), then decide.** The user re-armed the project-level search for new hypotheses on 2026-09-28; the detailed goal is active, but closed individual research lines remain closed.

---

## 1. Where the project stands

> **Historical snapshot:** the summary and table below were written on 2026-09-26.
> For current status, use `docs-myself/RESEARCH_STATE.md` §1/§7 and its latest
> change-log rows; this table is not the complete or current research inventory.

Five research lines were run to completion on 2026-09-26. **All five closed, and
none closed for lack of effort — each closed on a mechanism.**

| line | verdict | why |
|---|---|---|
| 5m volume breakout | no edge | costs consume 0.75R per trade; a 1-ATR stop on a 5m bar is thinner than the commission |
| 4h volume breakout | real but unmonetisable | **gross +0.131R, t=3.71, positive in all 4 splits**; friction 0.088R leaves net t=1.21, indistinguishable from zero |
| liquidation cascade (SHARK-07) | testable, null so far | best conditional excess +4.4 bps vs a 12–18 bps cost. Only 3 months of data exist anywhere |
| funding / basis carry | no risk premium | **excess over Binance's administered rate is −0.88 %/yr**; the median settlement *is* the administered parameter |
| cross-sectional momentum | pre-registered, executed, FAILED | OOS Sharpe −0.31; independently matches a published null (Ammann et al., t=0.13) |

The cross-sectional line was the last design with a structural answer to the
sample-size problem that killed the others (a cross-sectional portfolio has
lag-1 autocorrelation ≈0 and effective N ≈ nominal). Its failure closed the
then-current project search under the kill criterion written into
`docs-myself/PREREG_CROSS_SECTION_2026-09-26.md` **before** the data was seen.
**Correction, 2026-09-28:** the user has since re-authorized project-level
scouting for *new, independent hypotheses* (see `RESEARCH_GOAL.md`). This does
not reverse the old result or reopen any closed line; new work still needs its
own preregistration and a feasible power/cost design.

**The single most important fact about this project:** it is built to be
trustworthy rather than to produce a winner. Every line was reported at its
true strength, several conclusions were retracted mid-run, and the nulls are
better evidenced than the positives.

---

## 2. Settled — do NOT reopen (state file §7)

- The 92-hypothesis registry is closed; `H13` is not rescued.
- `2025-11 → 2026-08` is permanently out of candidate selection.
- The **final holdout is burned** — `binance_v2/FINAL_HOLDOUT_DO_NOT_TOUCH.json`
  records `unblinded: 2026-09-26T01:42:43`. It can never be called untouched again.
- Funding carry is analysed and **off**. A re-armed monitoring switch does not
  change the conclusion: the part that is a return rather than a financing
  charge is negative.
- The cross-sectional design is closed per its own pre-registered kill criterion.
- **Do not re-run any closed line with different parameters, timeframes or
  symbols hoping for a better number.** That is the specific error this whole
  apparatus exists to detect, and it has now detected it — including in my own
  reporting, twice.

---

## 3. What a new session can actually do

> **Historical action suggestions (2026-09-26), not the current priority queue.**
> Re-check `RESEARCH_STATE.md` and `RESEARCH_GOAL.md` before acting; current
> status and user-authorized project goal take precedence over the list below.

Ranked by expected value in the original 2026-09-26 handoff. The first was
considered the only action producing genuinely new information at that time.

### 3.1 Start and keep the forward collectors running  *(highest value, zero risk)*

Nothing in the literature measures the **current** level of crypto funding —
the most recent published sample ends 2024-03, and the only cost-adjusted null
covers eight days. Only this project's own data knows, and it changes daily.
Data that is not collected today cannot be collected at all.

```bash
# funding + daily klines (scheduled: task freqtrade-forward-collect, daily 07:15)
.venv\Scripts\python.exe user_data\forward\collect_forward.py

# Bybit liquidation events (NOT scheduled — must be started deliberately)
.venv\Scripts\python.exe -m shark_hunter.collect_liquidations

# monthly Coinalyze snapshot (free tier = ~3 months retention, verified)
.venv\Scripts\python.exe -m shark_hunter.coinalyze fetch --years 0.30
```

**The liquidation collector is the only route to SHARK-07.** No free source has
per-print data before 2026-07-08, so the dataset simply does not exist yet.
Event frequency is ~12,600 independent 3×-spikes/year across 9 symbols, which
clears the collection stop condition by ~30×. A collector started today is the
only thing that makes that hypothesis testable in 12 months' time.

### 3.2 Stress-test the cost premise  *(cheap, strengthens the foundation)*

The entire project rests on a 12–18 bps round trip. I measured it at **12.4 bps
median** on a calm day (Roll effective spread on aggTrades, top-10 perps) — so
the assumption is **accurate, not conservative**, and the word "conservative"
should not be used about it again.

But that was one calm day, and the state file records a realised BTC perp spread
of **5.95 bps in the 2020-03-12 crash** — roughly 30× the calm median.

```bash
.venv\Scripts\python.exe -m tools.cross_section.measure_cost \
    --symbols 12 --days 3 --date 2020-03-12
```

Repeat across known dislocations (2020-03-12, 2022-11 FTX, 2024-08, 2025-10).
**If the stress cost is materially above 18 bps, every cost-based verdict in
the project hardens; if it is not, the 5m and 4h conclusions get a small
reprieve that is still far short of their bars.** Either way the number becomes
known instead of assumed, and it is currently the single least-examined
load-bearing input.

### 3.3 Decide whether to continue at all  *(legitimate)*

The original pre-registered kill criterion closed the then-current search; the
user re-armed the *project-level* goal on 2026-09-28 (see `RESEARCH_GOAL.md`).
Stopping a particular line remains valid and costs nothing. If no genuinely new
hypothesis has a feasible power/cost design, report that rather than reviving a
closed line. If the goal is *a deliverable*, `RESEARCH_STATE.md` plus the
reports remain the record.

The previously listed possibilities — a longer horizon, non-price liquidity or
order-book information, or a venue/structural change — are **only possible new
hypotheses**, not recommendations or established edges. Any one must be checked
against the current state, researched broadly, and preregistered before testing;
changing parameters or timeframes on a closed line is not a new hypothesis.

### 3.4 Rigorous replication of Arefev (2026)  *(only if 3.1/3.2 are already running)*

Arefev, SSRN 7404139, ran exactly this test on Binance perps 2020–2026 with
pre-committed parameters and got a null. It is **0 citations and unreviewed**,
so it cannot close the question — which means a careful replication would be a
contribution in its own right. This is *new pre-registered work*, not a
reopening: the pre-registered line here failed on its own terms, and a stronger
replication of someone else's null is a different project.

---

## 4. Traps already paid for — the expensive ones

State file §3 has the full list (~31 entries). The ones that cost the most time
or produced the most wrong answers:

- **A boolean mask built with `&=` from an all-False array stays all-False
  forever** → every strategy produced exactly zero entries, which is
  indistinguishable from "no edge". Now fails the build.
- **A cross-sectional intersection is a selection, not a coverage step.** It
  silently deleted 18,522 of 141,889 funding rows, including SOL's entire
  November-2022 FTX episode (−21.5% of notional in one month).
- **Missing rows are not the same as bad rows.** 5m klines contained 199 frozen
  zero-volume bars that passed every integrity check. Found only by
  cross-checking native 1h bars against the 5m aggregation.
- **Comparing a per-observation Sharpe against a return-frequency benchmark**
  inflated the Deflated Sharpe bar ~41× and made a finite sample requirement
  look "undefined".
- **A mean funding rate is the wrong statistic.** Median +1.00 bps, mean
  −1.91 bps. Check the median against a documented default before treating a
  spread as a premium.
- **A hand-written test runner is not a regression gate** — it silently skips
  fixture-bearing tests and reports a smaller green number. The real gate is
  `.venv\Scripts\python.exe -m pytest tests/tools/ -q --no-header -p no:cacheprovider`
  (**243 tests**). The Shark Hunter suite is a *separate* 40-test runner.
- **Compounding a holding period over one bar** understates an edge by the
  length of the hold and makes every cross-section look unprofitable for the
  wrong reason.
- **pandas 3.0 returns `datetime64[us]` on some joins**; a hard-coded
  nanosecond assumption is then wrong by 1000×.

---

## 5. Environment

- **Always use `.venv\Scripts\python.exe`.** The system Python on `PATH` cannot
  read feather (no pyarrow) and will silently fail.
- Python 3.11, pandas 3.0, numpy 2.4, pyarrow 25.0.1, pytest 9.1.1 (+xdist,
  pytest-mock). No matplotlib, no statsmodels.
- `shark_hunter/.env` holds the Coinalyze API key. It is gitignored, as are
  `shark_data/` and `shark_results/`. **Never move a key into source or a result
  file.**
- PowerShell `Invoke-WebRequest` fails TLS against these hosts; Python
  `requests` works.

---

## 6. Useful entry points

```bash
# regression gates — run before believing any number
.venv\Scripts\python.exe -m pytest tests/tools/ -q --no-header -p no:cacheprovider
.venv\Scripts\python.exe -m shark_hunter.tests.test_regressions

# measurement (reusable)
.venv\Scripts\python.exe -m tools.cross_section.measure_cost --symbols 12 --days 3
.venv\Scripts\python.exe -m shark_hunter.coinalyze probe

# collectors
.venv\Scripts\python.exe -m shark_hunter.collect_liquidations
.venv\Scripts\python.exe user_data\forward\collect_forward.py
```

Reports, in the order they should be read:
`shark_results/REPORT_FINAL.md` (phase 1 + the retraction) →
`REPORT_PHASE2/3/4.md` →
`docs-myself/PREREG_CROSS_SECTION_2026-09-26.md` (the last closed line) →
`docs-myself/CARRY_LIT_REVIEW_2026-09-26.md` and `XSECT_REVIEW_2026-09-26.md`.

---

## 7. One thing worth saying plainly

A previous version of this project spent significant effort trying to make a
losing strategy look promising, and the documentation shows it being caught.
The apparatus that caught it — a frozen frontier instead of a chosen cell, a
deflated Sharpe, a placebo baseline, a pre-registration, an adversarial
subagent — is the most valuable output here, and it outlives any particular
result. **If a future session is offered a positive number, the first question
is which of those five mechanisms would have had to fail for it to exist.**
