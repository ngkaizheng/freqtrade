# PREREG — F-1: CAN THE FORWARD COLLECTOR ACTUALLY RECORD A TRADE?

**Written:** 2026-09-30, before the checks were run.
**Tool:** `tools/perp_short/forward_path_check.py`.

---

## 1. Why this outranks another research line

The delivered book's weakest property is not any axis — it is that **t ≈ 0.58 by timestamp
and the final holdout is burned**, so on this sample it is not provable. The only mechanism
that could ever change that is the **forward collector**, and the collector needs **6.8
years** to accumulate enough evidence (§9).

> **A 6.8-year test is worth nothing if the thing collecting cannot record a trade when one
> happens.** That is not a hypothetical. This project has already paid for it once: the
> collector "heartbeated happily and produced zero signals with no error", which is recorded
> as a status-table row — and the fix was `startup_candle_count=420`, i.e. the feed was
> present but the *first record* was unreachable.

**What exists today checks the wrong thing.** `verify_collector.py` proves the process is
alive, the DB exists, the last state change is RUNNING and the heartbeat carries state
RUNNING. **Nothing proves the signal path or the record path works.**

## 2. What the log actually shows, as read before the checks

`user_data/logs/forward_perp.log`, 1,389 lines, 2026-09-29 04:26 → 19:07 (14.7 h):

| logger | lines | what it means |
|---|---:|---|
| `freqtrade.worker` | 801 | heartbeats (two PIDs: 2868, 23240 — it restarted) |
| `freqtrade.data.history.datahandler` | 195 | OHLCV refreshes |
| `freqtrade.resolvers.strategy_resolver` | 170 | startup only |
| **any `analyze_pair` / "Found enter signal" / per-pair decision** | **0** | — |

> **Zero lines from the analysis path.** That is not proof it did not run — freqtrade logs
> signals at DEBUG, and this is an INFO log — but it is also **not proof that it did**, and
> that is the whole problem. The status of the single mechanism that could ever validate the
> deliverable rests on an absence of evidence.

**Two PIDs means it restarted at least once.** Any restart discards in-memory state, and the
strategy's circuit breaker is explicitly stateful (`bot_loop_start` with a lazy one-shot
init, trap 5). Recorded as an observation, not diagnosed here.

## 3. Pre-registered checks

**F1 — THE RECORD PATH.** Write one synthetic trade into a **throwaway copy** of the live
database through **freqtrade's own persistence models**, then read it back with the same
accessors a forward analysis would use, and confirm a `Trades.query` returns it.
> **Positive control.** A check that has never been shown to fail is decoration, so F1 is
> *proven* by first inserting a deliberately malformed row and confirming the read path does
> **not** return it. The live database is **copied, never written**.
> **If F1 fails, the forward series is VOID.**

**F2 — THE SIGNAL PATH.** Load the deployed strategy's own class, run its
`populate_indicators` and entry logic over the 4h data the collector is reading, and assert:
* no exception on live data;
* indicator columns are non-null on a stated fraction of bars (**a mask that silently
  produces zero is this project's trap #1, so a zero is a FAIL not a weak result**);
* the entry condition is evaluated and a count is returned.

**F3 — THE CADENCE, which is the number the user actually wants.** From F2, count how many
entry signals the 40 deployed symbols produce per year, and from that compute **how many are
expected between the collector's start (2026-09-29 04:26 UTC) and now**, next to the **0
actually recorded**.
> **This is the "is a test that cannot conclude" check from `AGENTS.md` 1a, applied to the
> collector.** If the expected count over elapsed time is ~0, then 0 trades is **consistent
> and uninformative** — and the report must say that rather than calling it progress.

**F4 — WHAT IS DELIVERED.** A pass is **"both paths work and the wait is quantified"**. A
failure is **"the collector is alive and silent, and here is which link is broken"**. Both are
results. **"It is running" is not a result and is not what this round may conclude.**

## 5. Kill rule

**If F1 or F2 fails, the forward test is declared VOID in the state file**, the running
collector is reported as unverified rather than as progress, and no forward number is quoted
anywhere until the broken link is fixed and this check passes.

## 6. What this does not do

* It does not shorten the 6.8 years. Nothing can.
* It does not make the edge significant. It makes the *measurement apparatus* trustworthy,
  which is a precondition for the forward test to ever mean anything.
* It does not touch the strategy, config, risk, universe or the live database.
