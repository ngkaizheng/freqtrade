# LESSONS LEDGER

Every methodological error I made in this project, what caught it, and the rule
that prevents recurrence. **Read this before starting new research.**

This file exists because I repeated my own documented mistakes. A lesson that is
not written down is a lesson not learned.

---

## L1 — I added sampling frequency instead of calendar years

**What I did:** After round 1 failed for lack of statistical power, I recommended
downloading 4h/1h data to "increase the sample."

**Why it was wrong:** Lo (2002): SE(annualised Sharpe) ≈ 1/√**YEARS**, independent
of sampling frequency. Intraday data adds rows, not information about the
annual risk/return ratio.

**Caught by:** Working out the Lo formula while preparing round 2.

**Rule:** To buy statistical power, extend the **calendar span**. Never assume
finer granularity helps. Compute SE = 1/√years *before* acquiring data.

---

## L2 — I trusted a proxy's failure as evidence about the real thing

**What I did:** Used PowerShell `Invoke-WebRequest` to test network reachability,
got `SSL connection could not be established`, and concluded "all outbound HTTPS
is blocked from this machine — firewall/VPN layer."

**Why it was wrong:** The network was fine. Python's `ssl` handshake succeeded
immediately to the same hosts. PowerShell's TLS stack was the problem, not the
network. I reported a confident diagnosis that was simply false.

**Caught by:** Switching to Python `urllib` when a *different* tool (curl) also
failed but the failure mode looked unlike a real firewall.

**Rule:** When a diagnostic says "the environment is broken," verify with a
**second independent tool** before believing it. Prefer the tool closest to the
actual code path. A tool failing is evidence about the tool first.

---

## L3 — I compared two things that differed in two ways at once

**What I did:** Compared VWMA-50 against MA200, found VWMA better (Sharpe 1.03 vs
0.82), and began building the case that **volume** carries information. The
disagreement analysis even looked compelling: VWMA was "right" on both sides.

**Why it was wrong:** The two rules differed in **window** (50 vs 200) *and*
**weighting** (volume vs equal). A faster MA is right at turning points **by
construction**. The comparison proved nothing about volume.

**Caught by:** Asking "what else differs between these two rules?" before
accepting the result.

**Result:** Holding the window fixed and varying only the weighting gave a mean
effect of **0.017 Sharpe** — nothing. The entire apparent edge was *speed*.

**Rule:** To test mechanism M, hold everything else constant and vary only M. Any
comparison where two variables move together is uninterpretable, no matter how
good the result looks.

---

## L4 — I counted nominal trials instead of effective ones

**What I did:** Ran the frozen rule on 20 crypto majors, found 16/20 beat buy &
hold, sign test **p = 0.0059**, and called cross-asset replication passed.

**Why it was wrong:** Crypto majors are ~0.7–0.8 correlated. The eigenvalue
participation ratio showed **~2.6 effective independent bets**, not 20. Re-tested
against a correlation-preserving null, **p collapsed to 0.142**.

**Caught by:** Asking "are these 20 things actually independent?" — a question I
had not thought to ask until round 2.

**Rule:** Before any "N of M assets confirmed it" claim, compute the **effective**
number of independent bets from the return correlation matrix. Significance on
correlated panels is overstated by roughly √(N/N_eff).

---

## L5 — I selected a parameter on data that included the test period

**What I did:** Chose SMA-50, ran nine gates on the full 15-year series, reported
9/9, and wrote "candidate found and validated."

**Why it was wrong:** **SMA-50 was selected by looking at the full sample — which
includes 2025–2026.** The parameter had seen the test period even though the
evaluation had not. A clean train(2012–2024)/test(2025–2026) split:

* train-only selection picks **SMA-20, not SMA-50**
* SMA-20 test edge **+0.024** vs SMA-50 test edge **+0.282** ← the leak, quantified
* Binance majors: train edge +0.402 → test edge **−0.001**
* per-asset: +0.197 → **−0.031**; positive-edge assets 19/20 → **7/20**

**Caught by:** The user directly asking whether I had ever run a clean
train/test split with the strategy designed without seeing the test period.

**Rule:** **Freeze the split before selecting anything.** The moment a parameter
is chosen by looking at a grid over the full sample, every subsequent
"out-of-sample" claim about that parameter is void. A grid search over the full
series is *in-sample by definition*, however many gates follow.

**This is the most serious error in the project** — it is the same
selection-bias mechanism I had identified and criticized in six earlier studies,
reapplied to my own candidate.

---

## L6 — I let a passing test suite substitute for understanding

**What I did:** After 9/9 gates, wrote "candidate found and validated" and marked
the objective complete.

**Why it was wrong:** The gates were real and honestly computed, but they answered
"does this rule pass these historical checks?" — not "is this rule likely to make
money?" I treated a *checklist* as a *conclusion*. L5 shows the checklist itself
was contaminated.

**Caught by:** The user challenging the "9/9" framing and asking for a clean
split.

**Rule:** State what a test does **not** establish. Prefer the phrasing
"passed the predefined gates" over "validated". When a result is strong, spend
proportionally more effort trying to break it.

---

## L7 — Encoding bug masked a passing result

**What I did:** Added a `⚠️` character to a script's output; on Windows GBK
console it raised `UnicodeEncodeError` and the script exited **1** despite
printing "9/9 gates passed".

**Why it mattered:** Exit codes are the interface. A passing script that exits 1
is a broken script, and could have been misread as a failed gate.

**Caught by:** Verifying exit codes rather than only reading stdout.

**Rule:** Verify `$LASTEXITCODE` on every script, not just its printed output.
Keep console output ASCII; put non-ASCII only in markdown files.

---

## L8 — I reported turnover as a trade count

**What I did:** Repeatedly stated the strategy's expected frequency as "~9
trades/year" in the findings docs, the runbook, and in conversation.

**Why it was wrong:** 9.4/year is **turnover** — the sum of |Δexposure| in
exposure units. Each regime flip moves exposure by **0.5** (1.00 ↔ 0.50), so the
number of rebalance **events** is `turnover / 0.5` ≈ **19/year**, not 9. The
reconciliation is exact: turnover 140.5 / 0.5 = 281 = the observed flip count.

**Caught by:** An independent signal-verification script that counted flips
directly and disagreed with the figure I had been quoting.

**Why it matters:** This was not cosmetic. The forward-validation turnover check
is one of the few metrics that resolves in weeks. A **wrong benchmark would have
made a broken implementation look acceptable** — a live bot firing 9/year against
a true expectation of 19 is badly broken, but would have read as "on target".

**Rule:** Distinguish *magnitude* metrics from *event count* metrics. When two
numbers describe the same activity, reconcile them arithmetically before
publishing either. Prefer the count that can be observed directly live.

---

## L9 — I over-read a single split as a general law

**What I did:** `reconciliation_jackknife_vs_oos.py` produced Spearman ρ = **−0.810**
between in-sample window edge and out-of-sample window edge on the 20-major pool.
I stated that in-sample selection is "**actively harmful**" — i.e. that you
systematically land on a window that underperforms.

**Why it was wrong:** That was **one split, 8 windows**. Repeating across six
independent splits:

| | mean ρ | range | negative in |
|---|---:|---|---:|
| BTC/USD | **−0.151** | −1.000 … +0.810 | 3/6 |
| 20-major pool | **+0.226** | −0.762 … +0.833 | 2/6 |

ρ is **not** stably negative. The dramatic −0.810 was a coincidence of that
particular split.

**Caught by:** Deliberately re-running the same measurement across multiple
independent splits instead of accepting a striking single number.

**What survived:** a weaker but *durable* finding — on BTC, the in-sample-best
window produced a **positive out-of-sample edge in 0 of 6 splits** (mean −0.172).
That is the real result; the sign of ρ was noise.

**Rule:** A correlation or effect measured on ONE split is a single draw. Before
describing any such number as a general property, repeat it across several
independent splits and report the **range**, not just the headline. This is L3
(one comparison ≠ a conclusion) and L6 (a striking number ≠ an understanding)
appearing again in a new guise.

---

## L10 — I built a test whose design could not answer its own question

**What I did:** To disentangle "SMA-50 is genuinely a good window" from "SMA-50 was
chosen on data containing these periods," I ranked the windows by out-of-sample
edge across splits. BTC showed SMA-50 ranking **1.8/8 on average, best in 4/6**,
which appeared to refute my contamination thesis.

**Why the test was invalid:** the "out-of-sample" periods (2020, 2021, … 2025
onward) are **subsets of the full sample that SMA-50 was selected on**. A window
chosen with knowledge of the whole series will look good in subsets of it
**mechanically**. The test period was not out-of-sample with respect to the
*selection*, only with respect to the *evaluation* — the same distinction that
caused L5.

**Caught by:** writing the interpretation and realising the result was too
convenient for the opposing view, then asking what the test period was actually
independent of.

**What I did about it:** reported the result, stated explicitly that it neither
confirms nor refutes the thesis, and left the question **unresolved** rather than
using it as support. The only clean evidence remains the train-only protocol
(round 7), which favours the thesis.

**Rule:** Before trusting any "out-of-sample" or "holdout" result, ask **what the
data is independent of**. If the selection saw it, it is not out-of-sample for
that question, no matter what the code calls it. Verify independence at the
*selection* step, not just the evaluation step.

---

## L11 — My test harness reported failure, and the fault was in the harness

**What I did:** Built `forward_checker_selftest.py` to prove the forward criteria
checker can detect defects. It reported **2/6**, and I nearly concluded the
checker was broken.

**What was actually wrong:** the checker was fine. My **self-test's parser** was
wrong — it took the *last* `-> ` line in the output, which is Criterion 2, not
Criterion 1. So every synthetic signal-mismatch case read back Criterion 2's
`INSUFFICIENT_DATA`/`PASS` instead of Criterion 1's `FAIL`.

**Caught by:** not accepting 2/6 — writing a diagnostic that dumped the full
checker output and showed `-> FAIL` on line 19 (Criterion 1) and `-> PASS` on
line 26 (Criterion 2), with no `->` separator semantics to distinguish them.

**Fix:** parse the **labelled** overall summary lines
(`Criterion 1 (implementation): FAIL`), not positional `->` markers. After the
fix: **6/6**.

**Why it matters:** had I trusted the harness, I would have "fixed" a working
checker and possibly broken it — then run a 90-day forward test under a
mis-verified gate. A verification tool that has never itself been falsified is
not a verification tool.

**Rule:** when a *test or harness* reports failure, suspect the **harness first**
before the thing under test. Show the raw output. Parse by label, never by
position. (This is L2 — "a tool failing is evidence about the tool first" —
applied to my own harness.)

---

## L12 — I quoted the wrong statistic's power requirement for nine rounds

**What I did:** Repeatedly stated, in seven documents and in conversation, that
detecting the edge "needs **~271 years**."

**Why it was wrong:** that figure comes from `n ≈ (2.8/SR)²`, which tests an
**absolute Sharpe against zero**. The actual claim is a **paired** comparison —
the rule versus a matched flat control on the *same* underlying returns. The
paired difference is far less noisy than either level.

| statistic | requirement |
|---|---:|
| absolute formula (what I quoted) | 225–271 years |
| paired, before autocorrelation | 11.7 years |
| **paired, autocorrelation-adjusted** | **~18 years** |

**Caught by:** finally asking what number the formula I kept repeating was
actually derived from, rather than re-quoting it.

**Rule:** Before quoting a power/required-n sample size, state **which statistic**
it applies to and confirm that is the statistic you are testing. Absolute-Sharpe
formulas do not apply to paired differences. Then check autocorrelation — the
inflation here was 1.556× (Ljung-Box Q=77.3, significant), so ignoring it
understates the requirement.

---

## L13 — I spent four scripts on a quantity that changed no decision

**What I did:** After discovering the 271-year error, I built four scripts
(analytic, autocorrelation, block cross-check, Ljung-Box) to pin down whether the
answer was ~5, ~12, or ~18 years.

**Why it was wasted effort:** every candidate value was already far beyond a
usable forward window. Once **all** estimates exceeded ~5 years, the decision —
"the forward test cannot settle the edge" — was **already fixed**. The additional
precision bought nothing.

**Caught by:** noticing, while writing the fourth script, that the conclusion
paragraph was identical to the previous three.

**Rule:** Establish the **order of magnitude** and check whether it changes the
decision. If it does not, **stop and record the range**. Precision on a quantity
that cannot alter any action is not progress — it is a way to feel productive
while avoiding harder questions.

---

## Standing rules (derived)

1. **Compute power first.** SE ≈ 1/√years. If the effect you seek is smaller than
   ~2×SE, the test cannot decide — do not run it and call the result evidence.
2. **Freeze the split before selecting anything.** Grid search on the full sample
   voids all later OOS claims (L5).
3. **Vary one thing at a time** (L3).
4. **Count effective, not nominal, trials** (L4).
5. **Verify diagnostics with a second tool** (L2).
6. **Extend calendar time, not frequency** (L1).
7. **State the limits of every test**; prefer conservative phrasing (L6).
8. **Check exit codes, not just stdout** (L7).
9. **Log the trial count.** MinBTL = 2·ln(N)/SR². If the sample is shorter, the
   search itself manufactures the result.
10. **A rejected hypothesis is a result.** Six of seven studies here were
    rejections; that is the work, not a failure to find something.
11. **Reconcile related metrics arithmetically** before publishing either (L8).
12. **Verify a "passing" check with an independent implementation** (L2, and the
    signal-verification script). If two components share a wrong assumption,
    parity reads OK and the bug is invisible.
13. **Repeat any striking single-split statistic across several splits** and
    report the range, not the headline (L9).
14. **Ask what a "holdout" is independent of** — at the *selection* step, not
    just the evaluation step (L10). If the parameter choice saw it, it is not a
    holdout for that question.
15. **When a test/harness reports failure, suspect the harness first**; show raw
    output and parse by label, not position (L11). A verification tool that has
    never itself been falsified is not a verification tool.
16. **State which statistic a power calculation applies to** before quoting it;
    absolute-Sharpe formulas do not apply to paired differences, and
    autocorrelation inflates the requirement (L12).
17. **Establish order of magnitude, then check whether it changes the decision**
    — if not, stop and record the range (L13).

---

## Trial ledger (cumulative configurations tested)

| round | what | trials |
|---|---|---:|
| 1 | MA200 exposure, momentum variants + grid, drawdown rules, volume families, VWMA grid, funding families + sign test | 70 |
| 2 | SMA window grids, cross-asset walk-forward | 28 |
| 3 | SMA 15y grid, equal-weight pool | 12 |
| 4 | out-of-domain equities, crypto majors replication, exposure bands | 30 |
| 5 | train/test split, decay tests | 10 |
| 6 | H-D pre-registered (VR predictive) | 4 |
| 7 | fragility, jackknife/OOS reconciliation, ρ stability | 10 |
| 8 | H-E ensemble + H-F expanding mean (pre-registered) | 12 |
| **total** | | **~176** |

**MinBTL at N=176 for SR=0.84 ≈ 15.7 years.** The longest clean series available
is 15.1 years (BTC Bitstamp) — i.e. **below the boundary**, which is a warning,
not a pass.

---

## Terminal status (2026-09-19)

**No strategy in this project's search survives to the standard the project set
for itself.** See `TERMINAL-FINDING.md`. The candidate SMA-50 failed the
selection-aware tests: DSR 0.9435 (needs 0.95), MinBTL 15.5y vs 14.6y available,
and a max-statistic reality check at p = 0.040–0.086 across four
dataset×metric combinations.

The measured cost of searching: ignoring selection p ≈ 0.012–0.020; pricing
selection p ≈ 0.040–0.086 — a **4–6× inflation**.

This is a finding, not a failure. The rejection list and this ledger are the
deliverable.

---

## Live hypotheses / open questions

* **H-A (active):** Does the SMA-50 exposure rule's *implementation* behave
  identically live vs backtest? → shadow backtest, weeks not decades.
  Infrastructure built: `tools/forward_recorder.py` (daily parity log),
  `tools/verify_signal_independent.py` (cross-checks the signal against two
  independent SMA implementations and the strategy's own indicator).
* **H-B (backlog):** Does crypto's positive variance ratio (VR(20)≈1.19) support
  *other* trend-family mechanisms? Mechanism-first, must pre-register.
* **H-C (backlog):** Would a portfolio of several trend rules across many majors
  beat the single-asset version, given ~2.6 effective bets?
* **Closed by evidence:** MA200 exposure, cross-sectional momentum, vol/trend
  drawdown control, volume/OBV/VWMA, funding rate, SMA-50 as a *statistically
  confirmed* edge.
* **H-D (closed 2026-09-19, NOT SUPPORTED):** is in-sample VR(20) predictive of
  out-of-sample trend edge? P1 ✅ P2 ✅ **P3 ❌** P4 ✅. Directionally as the
  mechanism predicts and the equity control is clean, but the strict statistical
  prediction failed → **not a usable tool**. Not re-tuned.
  See `findings-hD-vr-predictive.md`.

---

## Pre-registration protocol (adopted round 6)

For any new hypothesis, before looking at results:

1. Write the mechanism, the falsifiable predictions, the exact parameters, and
   the **falsification criteria** into the script header.
2. Count each prediction as a separate trial in the ledger.
3. On failure, report the failure. **Do not** try alternative windows, thresholds,
   sub-periods, or asset sets to find a passing configuration — that is the exact
   metric-mining this project has identified and rejected six times.
4. State explicitly in the write-up what was *not* tried.

---

## What would change my mind

I am not looking for a strategy that looks good. I am looking for one that
survives attempts to break it. Specifically:

* a **mechanism** that predicts where the edge should and should not appear, and
  is then **confirmed out-of-domain** (the VR finding is the one example so far —
  it correctly predicted the equity failure)
* **pre-registered** predictions before seeing results
* out-of-sample point estimates that are **not uniformly worse** than in-sample
  (SMA-50 failed exactly here)

If nothing survives, "no strategy survives on this data" is the finding, and I
will report it as such rather than relaxing the gates until something passes.
