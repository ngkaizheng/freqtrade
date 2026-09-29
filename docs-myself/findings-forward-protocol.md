# Findings: Forward Validation Protocol — Built, Enforced, and Verified

Run 2026-09-19. Files: `docs-myself/FORWARD-PROTOCOL.md`,
`tools/forward_recorder.py`, `tools/forward_criteria_check.py`,
`tools/forward_checker_selftest.py`.

Round 8 left the selection question **unresolved** and concluded that only a
**pre-committed forward test** can settle it. This round makes that test real:
a frozen protocol, an automated criterion checker, and a self-test proving the
checker works.

---

## Why forward data is the only clean evidence

Round 8's key finding (lesson L10): the round-2 grid searched the **entire**
15-year Bitstamp series, so for BTC **no period influenced no window choice**.
Any historical "holdout" is contaminated at the *selection* step.

Forward data is independent of every past choice **by construction**. That is
its entire value — not more data, but *uncontaminated* data.

---

## The protocol (`FORWARD-PROTOCOL.md`)

**Frozen specification** — any change invalidates the test and restarts the clock:

| item | value |
|---|---|
| asset | BTC/USD (Bitstamp) |
| rule | `Close > SMA(50)` → 100%, else 50% |
| **window** | **50, committed in advance, never searched** |
| cost assumption | 10 bps per rebalance |

### Two questions, explicitly separated

**Question A — implementation** (resolves in weeks): does the deployed strategy
behave exactly as the backtest says?

**Question B — statistical edge** (does **not** resolve on any realistic
horizon): is the edge real?

The protocol states plainly:

> To detect the **paired** edge (rule vs matched flat) at 80% power needs
> **~10–20 years** (best estimate ~18y; see `findings-power-analysis.md`).
> *(Earlier drafts said "~271 years" — that was the absolute-Sharpe formula, the
> wrong statistic for a paired comparison.)*
> A profitable forward period does **NOT** confirm the edge; a losing one does
> **NOT** refute it.

This is written into the protocol so that a few months of P&L cannot be
misread — by me or anyone else — as evidence. Over-reading short windows is the
error this project has documented six times.

### Failure criteria, fixed in advance

**Criterion 1 — implementation** (any one ⇒ invalid):

| # | condition | expected |
|---|---|---|
| 1a | signal parity mismatch | 0 |
| 1b | exposure parity outside 0.25 units | 0 |
| 1c | cancelled-order rate | ≤ 5% |
| 1d | realised cost | ≤ 20 bps |
| 1e | rebalances/year | 10–35 (expect **~19**) |
| 1f | position correct after restart | yes |
| 1g | duplicate orders | 0 |

**Criterion 2 — mechanism:** forward **VR(20) < 1.0** sustained ⇒ the mechanism
story is contradicted. This is the one Question-B-adjacent claim forward data
*can* address, because VR describes the return process, not the strategy.

**Criterion 3 — explicitly NOT failure:** a losing month/quarter/year; drawdown
worse than historical; Sharpe below 1.45; underperforming buy & hold short-term.
Crypto at ~75% vol does this routinely (2022: −84%).

### Prohibited during the period

No window changes · no threshold/confirmation changes · no added indicators ·
no stopping early because it wins (that is selection on the outcome) · no
substituting a new strategy on interim results.

---

## The checker, and the bug it exposed in my own harness

`tools/forward_criteria_check.py` evaluates Criteria 1 and 2 and prints
PASS / FAIL / INSUFFICIENT_DATA. It **refuses to report PASS** off a single
observation:

```
Criterion 1 (implementation) : INSUFFICIENT_DATA
Criterion 2 (mechanism)      : INSUFFICIENT_DATA

IN PROGRESS — not enough forward record to judge.
Reporting PASS here would be over-reading (L6/L9).

Power check: 1 forward day -> SE(Sharpe) ~ 19.10
Detecting the paired edge needs ~10–20 years (see `findings-power-analysis.md`).
```

### Self-test (and my own error)

A checker that only ever says "insufficient" is untested. So
`forward_checker_selftest.py` writes **synthetic logs with known defects** and
asserts each is flagged.

First run: **2/6** — I nearly concluded the checker was broken.

**It was not.** My *self-test's parser* was wrong: it read the **last** `-> `
line, which is Criterion 2, not Criterion 1. A diagnostic dumping raw output
showed `-> FAIL` (line 19, Criterion 1) alongside `-> PASS` (line 26,
Criterion 2) with no positional way to tell them apart.

Fixed by parsing the **labelled** summary (`Criterion 1 (implementation): FAIL`),
never by position. After the fix:

| case | expected | got |
|---|---|---|
| healthy, 200 days, ~19 reb/yr | PASS | **PASS** |
| signal mismatch | FAIL | **FAIL** |
| exposure mismatch | FAIL | **FAIL** |
| too few rebalances (~3.6/yr) | FAIL | **FAIL** |
| too many rebalances (~73/yr) | FAIL | **FAIL** |
| short record (30 days) | INSUFFICIENT_DATA | **INSUFFICIENT_DATA** |

**6/6.** Recorded as lesson **L11**: when a *harness* reports failure, suspect
the harness first; parse by label, not position. A verification tool that has
never itself been falsified is not a verification tool.

> Note the bug-detection behaviour here is the same pattern as the round-3
> `Invoke-WebRequest` episode (L2) — a tool's failure being evidence about the
> tool. This time I applied it to my own code and found the fault in a minute
> instead of misdiagnosing the machine.

---

## Current status

| item | state |
|---|---|
| protocol | ✅ written and frozen |
| recorder | ✅ 1 observation (2026-09-18), signal parity OK, exposure parity OK |
| dry-run DB | ✅ 1 trade, 2 orders, **0 cancelled**, bitstamp only |
| criterion checker | ✅ functional, verified 6/6 |
| Criterion 1 | **INSUFFICIENT_DATA** (1 day < 90-day minimum) |
| Criterion 2 | **INSUFFICIENT_DATA** (1 day < 180-day minimum) |
| 90-day checkpoint | ~2026-12-18 |

**No claim is made that the strategy works.** The deliverable this round is a
*measurement apparatus that has been shown to detect the failures it is looking
for* — which is a prerequisite for the forward result to mean anything.

---

## Trial ledger

No new strategy hypotheses were tested, so the ledger is unchanged at **~176**.
Building and self-testing a checker is verification infrastructure, not a trial —
though for honesty, the 6 synthetic self-test cases are recorded here as **6
diagnostic configurations**.

---

## Reproduce

```powershell
.\.venv\Scripts\python.exe tools\forward_recorder.py            # append daily
.\.venv\Scripts\python.exe tools\forward_recorder.py --report   # summary
.\.venv\Scripts\python.exe tools\forward_criteria_check.py      # criteria verdict
.\.venv\Scripts\python.exe tools\forward_checker_selftest.py    # 6/6 expected
```
