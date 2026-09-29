# §43 — THE FORWARD COLLECTOR: BOTH PATHS VERIFIED, AND ONE NUMBER REPRODUCED TO THE DIGIT

**Date:** 2026-09-30
**Prereg:** `docs-myself/PREREG_FORWARD_PATH_2026-09-30.md`
**Tool:** `tools/perp_short/forward_path_check.py` (new, now the 12th gate)
**Raw:** `user_data/logs/forward_path_check.txt`
**The live database was COPIED, never written** — verified before and after (94,208 bytes,
mtime 17:56:24, unchanged).

---

## 1. Why this outranked another research line

Every research axis is closed. The delivered book's remaining weakness is not an axis — it is
that **t ≈ 0.58 by timestamp and the final holdout is burned, so on this sample it is not
provable.** The only mechanism that could ever change that is the forward collector, and it
needs **6.8 years**.

> **A 6.8-year test is worth nothing if the collector cannot record a trade when one happens.**

And what existed checked the wrong thing. `verify_collector.py` proves the process is alive,
the DB exists, and the heartbeat carries state RUNNING. **Nothing proved the signal path or
the record path worked.** This project has already paid for exactly that failure once: a
collector that "heartbeated happily and produced zero signals with no error", fixed by
discovering `startup_candle_count=420` made the first record unreachable.

## 2. What the log showed before the checks — and the observation it forced

`user_data/logs/forward_perp.log`, 1,389 lines, 2026-09-29 04:26 → 19:07 (14.7 h):

| logger | lines |
|---|---:|
| `freqtrade.worker` (heartbeats) | 801 |
| `freqtrade.data.history.datahandler` | 195 |
| `freqtrade.resolvers.strategy_resolver` | 170 |
| **any analysis-path / per-pair decision** | **0** |

Zero analysis lines is **not** proof it did not run — freqtrade logs signals at DEBUG and
this is INFO — but it is **also not proof that it did**, and that was the problem: the status
of the one mechanism that could validate the deliverable rested on an absence of evidence.

**⚠ Recorded observation, not diagnosed here: the log carries TWO PIDs (2868 and 23240), so
the collector restarted at least once.** Any restart discards in-memory state, and the
strategy's circuit breaker is explicitly stateful (`bot_loop_start` with a lazy one-shot init,
trap 5). The breaker is an in-sample parameter (§39's own note) so a restart resetting it is
not dangerous, but it is unexplained and is left open rather than waved at.

## 3. F1 — THE RECORD PATH: **PASS**, with a positive control

A synthetic trade was written into a **copy** of the live database through **freqtrade's own
persistence models** and read back with the accessors a forward analysis would use.

```
PASS  the COPY opened with 0 trades; a synthetic trade written through freqtrade's own
      models was read back exactly once with its strategy and timeframe intact, and a
      pair that was never written returned 0 rows (positive control passed).
      The live DB was copied, never written.
```

> **The positive control is the point.** A check that has never been shown to fail is
> decoration, so a deliberately non-existent pair must return 0 rows — and it does. Without
> that, "read back 1 row" could just mean the read is not filtering.

> ⚠ **The first version of this check was dangerous and said nothing about being dangerous.**
> It read `Trade.query` (which does not exist in 2026.8), and — worse — it built the
> `Configuration` from the **original** config, so the engine pointed at the **LIVE**
> database while the test believed it held a copy. **A safety control that is written but not
> actually pointing where it claims is worse than no control.** The config is now rewritten to
> the copy's path *before* the engine is created, and the live file's size and mtime are
> checked before and after.

## 4. F2 — THE SIGNAL PATH: **PASS**, and it reproduced §23a to the digit

The deployed strategy's **own class** was loaded and its `populate_indicators` and
`populate_entry_trend` run over the 4h data the collector is reading.

```
PASS  40 pairs analysed with no exception; indicators non-null on 99.71% of 272,557 bars;
      2169 entry signals across the full 4h panel
```

> **⚠ 2,169 is exactly the number §23a measured, by a completely different route.** §23a
> counted the frozen signal across 40 symbols × 3.67 years from the frozen specification;
> this counts `enter_short` from the deployed class's own live code path. **Two independent
> implementations agreeing to the digit** is the strongest check in this project's toolkit,
> and it validates both §23a and this path at once.

**The 99.71 % indicator coverage matters on its own.** A mask built with `&=` from an
all-False array stays all-False forever and produces exactly zero entries — indistinguishable
from "no signal" (trap #1). The pre-registered rule was that **a zero is a FAIL, not a weak
result**; the measurement is a coverage fraction with a floor, and it clears it by 9.7
percentage points.

## 5. F3 — THE CADENCE: 0 trades is **consistent and uninformative**

| | |
|---|---:|
| collector started | 2026-09-29 04:26:38 UTC |
| elapsed at the time of the check | **0.28 days (6.7 h)** |
| measured signal rate (§23a) | 14.8 per symbol-year |
| **EXPECTED signals since start** | **0.46** |
| **ACTUALLY recorded** | **0** |

> **0 recorded against 0.46 expected is consistent with the rate and carries no information.**
> It is **not progress and must not be reported as progress** — which is exactly what
> `release_check` had been printing as a benign note.

**The number the user actually wants: the expected inter-arrival time of a signal across 40
symbols is 365 / (14.8 × 40) ≈ 0.62 days, i.e. roughly one every 15 hours.** So the first
expected forward trade is due within about a day of the collector having started, and after
6.7 hours it simply has not come yet.

**And the number that matters most: 6.8 years.** At 14.8 signals per symbol-year across 40
symbols, the forward test needs **6.8 years** to accumulate the independent timestamps the
project's own by-timestamp t requires. **Nothing this project can do shortens that**, and the
honest position is that the delivered book cannot be statistically validated within a
human's trading horizon on this sample.

## 6. Verdict, and what it is not

**VERDICT: BOTH PATHS WORK.** The collector would record a trade if one occurred, and the
strategy's signal logic reaches its entry condition on live data. **What remains unproven is
the EDGE, not the apparatus.**

* **This does not make the edge significant.** It makes the *measurement apparatus*
  trustworthy, which is a precondition for the forward test to ever mean anything.
* **It does not shorten the 6.8 years.**
* **It does not touch** the strategy, config, risk level, universe, or the live database.

**Three harness errors of my own, all of which first appeared as a VERDICT about the
deliverable** — which is the project's recurring shape:

1. `Trade.query` does not exist in 2026.8; and the config was not rewritten to the copy, so
   the engine pointed at the **live** DB while the test believed otherwise.
2. `populate_indicators` returns the **DataFrame itself**, not a `(frame, populated)` tuple.
   Unpacking a tuple produced **"no pair could be analysed at all"** — a harness error
   reported as a statement about the strategy.
3. The sqlite handle was still open when the temp directory was removed, so **a passing check
   aborted as a crash** on Windows (`WinError 32`). The engine is now disposed before
   teardown.

> **A harness that reports its own bugs as failures of the thing under test is worse than no
> harness, because it manufactures reasons to distrust a deliverable that is fine.** Every one
> of the three above was caught by reading the traceback against the API, not by any gate.

## 7. The new gate

`tools/perp_short/forward_path_check.py` is now the **12th gate** in `release_check.py`, and
it is the first one that asks **"would this work?"** rather than **"did it work?"** — every
other gate in this project inspects an artifact that already exists. This one writes a
synthetic trade and counts entry signals, because **the property that matters about a forward
test is not that it is running.**
