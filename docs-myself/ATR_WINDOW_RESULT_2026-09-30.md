# §39 — THE 1h ATR DISAGREEMENT WAS A THIRD AND FOURTH FALSE POSITIVE, AND THE "CORRECTION" OF §36b WAS ITSELF WRONG

**Date:** 2026-09-30
**Tool:** `tools/perp_short/atr_window_probe.py` (new) + `tools/perp_short/consistency_gate.py` (fixed)
**Raw:** `user_data/logs/atr_window_probe.txt`, `user_data/logs/consistency_gate.txt`
**Status:** the red gate is **CLOSED**. `consistency_gate` now **PASSES 4/4**, exit 0.
**No backtest was run and nothing was changed in the deployed book.**

---

## 1. Where this starts

§36 built `consistency_gate.py` because four rounds had produced wrong-but-plausible numbers.
On its first run it reported a 12.3 % and a 13.2 % disagreement on the load-bearing
`median ATR%` constant. §37a fixed the 4h leg — it had compared a **40-symbol** median
against a **23-symbol** median, and only 23 of the 40 deployed symbols have a 1h file.
The 4h leg then agreed to 0.00 %.

§37b recorded the 1h leg as **UNRESOLVED** and deliberately refused to name a cause:

| what §37b could rule out | how |
|---|---|
| different universe | both routes pinned to the same 23 symbols |
| dropped rows | "the merge retains 1,149,946 of 1,149,946" |
| one-directional bias | 20 of 23 symbols lower through the merged route |
| a clean per-symbol reimplementation | returned 0.0 % agreement, **conflicting** with the integrated one |

The gate printed all of it and returned FAIL. **That was correct behaviour and it is why
the cause survived to be found properly rather than guessed at.**

## 2. The candidate cause §37b did not test: the DATE WINDOW

Three causes were eliminated. The fourth was never asked:

> **Do the two routes cover the same period?**

They do not, and the arithmetic says so immediately:

* `route_direct` reads **every** bar the 1h panel has.
* `route_merged` uses `merge_asof(..., tolerance="2h")` against the 4h panel, so it can
  only return 1h bars sitting within 2 hours of a 4h bar. **It is silently restricted to
  the 4h panel's span.**

| panel | first bar | last bar |
|---|---|---|
| 1h (`user_data/data/binance/futures`) | **2019-09-08** | 2026-09-27 |
| 4h (`user_data/data/wide526/futures`) | **2023-01-01** | 2026-08-31 |

**So route A was taking a 7-year median and route B a 3.7-year median.**
§37b had noted the 1h panel "extends FURTHER" and concluded truncation was not the cause —
correct as a statement about truncation, and it missed the point: **the extra 4.3 years are
exactly what makes the two numbers differ**, because 2020 and 2021 were more volatile than
2023–2026.

**Measured, not argued:**

```
1h bars in                       1,149,946
1h bars the merge actually keeps   726,952
DROPPED                            422,994   (36.8 %)
```

> ⚠ **§37b's "1,149,946 of 1,149,946 retained, 0 dropped" was not a count of 1h rows
> surviving the join.** The number 1,149,946 is the *total* 1h bar count across the 23
> symbols, so that check compared the input against itself and could not fail — trap 13
> again, **the fifth recurrence**, and the second one in a gate written specifically to
> prevent it. The window probe re-measures the retention with its own join and it is 36.8 %.

## 3. Three things that make this a mechanism and not a coincidence

A single sign match is a coincidence. Three independent things had to line up.

**(a) The sign is predicted in advance.** 2020–2021 volatility is above the 2023–2026
sample, so a longer window must read **higher**. The measured bias is **higher** through
the direct (longer) route on 20 of 23 symbols.

**(b) Dose-response, r = +0.882.** Bias is plotted against the *fraction* of 1h bars the 4h
panel cannot see:

| out-of-span fraction | n | median bias |
|---|---:|---:|
| **< 5 %** | 3 | **−0.08 %** |
| > 30 % | 17 | **+17.66 %** |

Pearson r = **+0.882** over 23 symbols.

**(c) A natural control group that passes.** Three symbols — **SUI, ARB, TIA** — have 1h
panels that begin *inside* the 4h panel's span, so for them there is **no window
difference**. They are the experiment's control and they show a median bias of
**−0.08 %, i.e. zero.** The hypothesis predicts exactly this, and it is what it got.

Per-symbol detail (`user_data/logs/atr_window_probe.txt`):

| symbol | 1h bars | in 4h span | all-bars | in-span | bias |
|---|---:|---:|---:|---:|---:|
| BNB | 58,093 | 32,133 | 0.880 % | 0.690 % | +27.63 % |
| ETC | 58,713 | 32,133 | 1.194 % | 1.000 % | +19.39 % |
| LTC | 58,881 | 32,133 | 1.135 % | 0.932 % | +21.69 % |
| XRP | 58,953 | 32,133 | 1.084 % | 0.921 % | +17.66 % |
| DOT | 53,458 | 32,133 | 1.296 % | 1.103 % | +17.46 % |
| **TIA** | 25,467 | 24,843 | 1.713 % | 1.715 % | **−0.11 %** |
| **SUI** | 29,813 | 29,189 | 1.515 % | 1.516 % | **−0.08 %** |
| **ARB** | 30,798 | 30,174 | 1.331 % | 1.319 % | **+0.91 %** |

## 4. The aggregate reproduces both numbers to the decimal

```
direct over ALL 1h bars       : 1.371 %   <- exactly the gate's route A
direct over the 4h SPAN only  : 1.189 %   <- the gate's route B is 1.190 %
difference                    : 13.22 %   <- the gate's reported 13.2 % gap
```

**13.22 % vs the gate's 13.2 %.** The hypothesis does not merely explain the direction; it
accounts for the magnitude of a discrepancy the gate had flagged as unexplained.

## 5. The consequence nobody expected: §36b's "correction" was an ERROR

§36b concluded:

> *"The merged route reports the 4h ATR% as 2.502 % where the direct computation gives
> 2.835 %… §18a and the §4 constant row are corrected to the direct values."*

**The reasoning was backwards.** The merged route is not "biased low" — it is
**window-restricted**, and for this book that restriction is the *correct* one: the deployed
backtest runs 2023-03-22 → 2026-08-31, entirely inside the 4h panel's span, so
**1.371 % is a 7-year median over 2020–2021 volatility that this strategy never traded.**

So the sequence is:

| version | 1h ATR% | 4h ATR% | ratio | status |
|---|---:|---:|---:|---|
| §18a (original) | 1.191 % | 2.502 % | 0.478 | **was right to ~1.6 % / ~2 %** |
| §36b ("corrected") | **1.371 %** | 2.835 % | 0.483 | **a 13 % error, in the wrong direction** |
| **this round (window-pinned)** | **1.210 %** | **2.553 %** | **0.474** | verified by two routes to 0.04 % |

**§18a was essentially correct and §36b broke it.** A "correction" that keeps the number
closest to the more obvious route is not automatically a correction; here the obvious route
was measuring a different decade.

## 6. What the gate does now, and what it will never do again

1. **Both routes are pinned to one universe** (the 23 shared symbols) — §37a.
2. **Both routes are pinned to one date window**, computed as the intersection over all
   shared symbols: **2023-10-31 18:00 → 2026-08-31 20:00 UTC**.
3. **`WINDOW` is a first-class failure class.** Before comparing values the gate checks
   that route B retained ≥97 % of route A's bars. If it did not, that is reported as
   *`tf WINDOW: route B retains only X % of route A's N bars — the two routes are not
   measuring the same period, so this is NOT a disagreement`* — explicitly **not** a
   disagreement, because a value difference caused by a different sample is not evidence
   about the arithmetic.
4. **Retention is printed for every horizon** so the vacuous check of §2 cannot recur.

```
  common window : 2023-10-31 18:00:00+00:00  ->  2026-08-31 20:00:00+00:00
  horizon    route A (direct)  route B (merged)   relative gap      bars A    bars B  verdict
  4h                   2.554%            2.552%          0.06%     142,853   142,841  PASS
  1h                   1.209%            1.210%          0.04%     571,389   571,340  PASS
  per-trade R : 1111 trades, max relative gap between routes 0.0000%  PASS
  total ret: recomputed 113.7378%   engine 113.7378%   gap 0.0000 pp  PASS
  VERDICT: PASS
```

## 7. The constants, restated with the window attached

**A distribution statistic without a window and a universe is not a constant.** Three
quantities were being used interchangeably; they are now named separately.

| quantity | value | universe | window | used for |
|---|---:|---|---|---|
| **deployed-universe 4h ATR%** | **2.835 %** | 40 symbols | full 4h panel 2023-01→2026-08 | the cost law for the deployed book |
| **verified 4h ATR%** | **2.553 %** | 23 shared | 2023-10-31→2026-08-31 | the two-route check |
| **verified 1h ATR%** | **1.210 %** | 23 shared | 2023-10-31→2026-08-31 | the two-route check |
| **1h/4h ATR ratio** | **0.474** | 23 shared | 2023-10-31→2026-08-31 | **this is what transfers** |

**Only the ratio transfers to the deployed 40-symbol book**, because a ratio is a property
of the horizon, not of the universe. Substituting into `cost_R = bps / (4 × atr% × 1e4)`
with the deployed 4h level of 2.835 %:

| cost | cost_R at 4h | cost_R at 1h | ratio |
|---|---:|---:|---:|
| calm 12.0 bps | **0.0106** | **0.0223** | **2.11×** |
| COVID 34.9 bps | **0.0308** | **0.0650** | **2.11×** |

## 8. The conclusion survives all three attempts, and that is the point

| version | 1h/4h cost penalty |
|---|---:|
| §18a | 2.10× |
| §36b | 2.07× |
| this round | **2.11×** |

**A conclusion that survives a 13 % level error, arrived at from two opposite directions,
was never resting on the level.** "A 1h round trip buys about half the risk unit, so any
intraday edge must roughly double to break even" holds at 2.07×, 2.10× and 2.11×. What
changed is only that the number can now be quoted with a window attached.

## 9. Two new traps

**23. A join that silently restricts the sample looks exactly like a join that does not.**
`merge_asof(..., tolerance=...)` is a *filter*, and a filter that removes 36.8 % of rows
produces a result with a completely normal shape. There is no way to see it except by
counting what came out against what went in — **and §37b's count was the input against
itself.** *Any* transformation applied to a panel must print retained/total, and the
denominator must be the count **before** the transformation.

**24. The 4h/1h disagreement and the universe disagreement were the SAME BUG at two
levels.** §37a fixed "two different symbol sets"; this round found "two different date
ranges" in the same function, in the same gate, one round apart. **The general form: a
consistency check must assert that its two routes consumed the same population — of rows,
of symbols, and of time — before it is allowed to compare their values.** A gate that
compares outputs without first comparing inputs is a gate that manufactures findings.

**And the meta-lesson, which is the fifth row of this pattern:** §36b produced a
confident correction ("use the direct route's values") while the gate it had just built was
still printing *"THE CAUSE IS NOT ESTABLISHED."* **The tool said "I don't know" and the
document answered anyway.** The gate was right and the prose was not, and the only reason
this was caught within one round rather than several is that the gate refused to resolve.

## 10. Two more gates repaired, found by looking at the gate I had just fixed

Fixing `consistency_gate` meant reading the neighbouring gates, and one of them had the
identical disease.

**10a. `state_gate.py` kept a second copy of the exclusion policy, and it had drifted.**
`tools/state_index.py` (the builder) excludes `INFRA` files and any `_`-prefixed file.
`tools/perp_short/state_gate.py` (the checker) carried **its own list**, which included
`LESSONS.md` — a file the builder *does* index. So the check that printed

```
documents : 138 indexed, 137 on disk, 0 dead links
VERDICT: PASS - ... every document is indexed
```

**was not asking about `LESSONS.md` at all.** The 138-vs-137 was visible in the output and
read as a rounding artefact. It is the same class as trap 22 — *a policy kept in two places
drifts, and a gate that consults its own copy stops checking the real thing.*

The gate now **imports `INFRA` from the builder** and applies the builder's own rule, so
the two cannot diverge again. It reports `138 indexed, 138 on disk`.

**And because a gate that cannot fail is decoration, it was proved violable rather than
assumed so.** A canary document was dropped into `docs-myself/`:

```
  documents     : 138 indexed, 139 on disk, 0 dead links
  FAIL  1 documents on disk are NOT indexed: ZZ_TEMP_CANARY_2026-09-30.md
  VERDICT: the state file cannot be trusted as an index.        exit 1
```

Removed → back to `138 / 138`, exit 0. **This is the first time any gate in this project has
been shown to fail on purpose rather than argued to be capable of it.**

**10b. `consistency_gate` was not in `release_check.py`'s gate list.**
`release_check.py` is the file whose entire claim is *"one command that answers: is the
deliverable still intact?"* — and the only structural defence this project has against a
wrong-but-plausible constant was not part of it. It is now, and it had to pass to be added:

```
  [PASS] consistency_gate       the load-bearing constants recompute by a second route
```

**11 gates, all PASS, exit 0, RELEASE-READY.** If the constants the cost law and the
intraday conclusion rest on stop recomputing by a second route, the deliverable is not
intact and this command now says so.

**10c. The deployed strategy only started from the repo root — and the proof of it nearly
was a false positive.**

`PerpShort4hDeploy.py` located its own inheritance chain with two *relative* `sys.path`
inserts:

```python
sys.path.insert(0, os.path.join("user_data", "strategies_frontier"))
sys.path.insert(0, os.path.join("user_data", "strategies"))
from PerpShort4hStop import PerpShort4hStop
```

Relative to the **process working directory**. Everything else in the deliverable is
directory-independent, so this was the single thing that made "run the bot" depend on
remembering to `cd` first. It now resolves from `__file__`.

Demonstrated, not asserted — and the demonstration had to be fixed first:

| form | launched from repo root | launched from `C:\Windows` |
|---|---|---|
| **old (relative)** | imports OK | **`ModuleNotFoundError: No module named 'PerpShort4hStop'`** |
| **new (from `__file__`)** | imports OK | **imports OK** |

**⚠ The first attempt to produce that table was itself a false positive, and it is worth
recording for exactly that reason.** The test re-created the old two lines and then loaded
the strategy file *from disk* — but the file on disk had already been fixed, so the "old"
test was silently re-running the new code and reporting "imported OK" from both
directories. It looked like the defect did not exist. The tell was that `find_spec` for
`PerpShort4hStop` returned `None` in the same process where the import then succeeded.
**The only way to test a reverted version is to revert it in a COPY** — a test that loads
the live file cannot test the code that used to be there.

**The running forward collector does not need a restart:** the change is in the import
preamble, which has already executed in that process, and no strategy logic was touched.
Restarting would interrupt the series the 6.8-year forward test needs for no benefit.

## 11. Verdict

* **The red gate is closed.** `consistency_gate.py` exits 0, 4/4.
* **§4 and §18a carry the corrected ratio 0.474 and the corrected cost_R 0.0106→0.0223
  and 0.0308→0.0650**, and no longer quote 1.371 % as the 1h level.
* **§18a's original levels (1.191 / 2.502) were right to ~2 %**; the 13 % excursion was
  introduced by this project three rounds ago and is now reverted.
* **The deployed book is untouched** in its *trading logic* — no config, risk level,
  universe, position sizing or signal changed, and every number in `HOW_TO_RUN` §4 and
  `DELIVERABLE_SPEC` is unaffected because none of them derives from the 1h leg. The one
  deployed file that changed is `PerpShort4hDeploy.py`'s **import preamble**, which no
  longer depends on the working directory (§10c); all 11 gates re-run green afterwards.

* **Three gates were touched, all now passing and one now proved violable.**
* **Next:** the family pre-screen's **5 m cascade** family remains the one OPEN line, and
  §38d established that its cost is an *extrapolation* rather than a measurement. That is
  the only measurement in the closed-list machinery whose input is still unmeasured.
