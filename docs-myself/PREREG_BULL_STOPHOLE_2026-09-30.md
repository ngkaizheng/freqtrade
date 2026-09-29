# PREREG — B-5: THE LONG BOOK'S STOP CAN FAIL TO BE SET AT ALL

**Date:** 2026-09-30 · **Written before the fix was implemented and before any P&L was seen.**
**Subject:** `user_data/strategies/PerpLong4h.py` (`custom_stoploss`, the `exit_mode="run"` branch).
**Finding that produced it:** the new gate `tools/perp_short/bull_verify_stop.py`, on its first run.

---

## 1. The observation

Re-running the delivered long book from its own config reproduces the published number exactly —
**1,000 trades, +95.4339 %, PF 1.3654** — so the book's headline is faithful. The defect is in one
trade inside it.

| | |
|---|---:|
| stop exits | 993 |
| worst stop exit | **−30.00 %** (UNI/USDT:USDT, 2025-01-31 → 2025-02-02, open 12.6760 → 8.8732) |
| 2nd-worst stop exit | **−8.14 %** |
| 5th percentile | −5.83 % |
| median | −3.06 % |

**The gap between the worst and the second-worst is 21.9 points and nothing is in it.** A stop
distance distribution does not have a hole in it. A strategy whose stop silently stops applying
does, and the hole is where the class `-30 %` backstop is.

## 2. The mechanism, read from the code — and it is INHERITED, not long-specific

Both books guard the same way, and the two guards are the same statement:

```python
# PerpShort4h.custom_stoploss  (short side, line 341)
ratio = (stop_price / current_rate) - 1.0
if ratio <= 0:
    return None                     # stop is at or below the market -> set nothing

# PerpLong4h.custom_stoploss     (long side, line 227)
if trail >= current_rate:
    return None                     # stop is at or above the market -> set nothing
```

Returning `None` means "leave the existing stop alone", which is correct **only if a stop was
already set**. On a trade whose adverse move exceeds the stop distance *within the entry bar*, no
bar ever has a placeable stop, the custom stop is never installed, and the trade rides to the
class `-30 %` backstop instead. The position is sized for `risk / (4 x ATR%)`, so a `-30 %` exit is
up to **~7.5x the intended risk unit** on that trade.

**This is structural on both sides.** The short book is not immune; it is 0-for-1,111 in this
sample and the long book is 1-for-993. A long hits it more readily because its floor is *below*
entry, so any entry-bar dip deeper than `4 x ATR` qualifies.

## 3. Why it survived 50 rounds

`verify_stop.py` checks the SHORT book and asserts zero backstop fallthroughs. **No equivalent
gate existed for the long book** — that is the gap this round closes, and it is the same gap as
the missing `initial_state`. Two delivery-level defects, both in a book that had a published
result and no gate.

## 4. The fix, and it touches the LONG BOOK ONLY

In the `run` branch, when the computed stop is at or above the market, stop trying to place a
trailing stop and exit at the market instead:

```python
if trail >= current_rate:
    trail = current_rate * (1.0 - 1e-4)   # the trail is already violated: exit now
```

This is the pessimistic direction on purpose. The alternative — clamping down to the measured
floor `sp` — would fill at `entry - 4 x ATR`, a price the market has already passed, and would
make the backtest look **better** than reality. A project whose cost work exists to avoid
optimistic fills does not get to introduce one in a risk fix.

**`PerpShort4hDeploy` is NOT touched.** The short book is release-verified and stays byte-identical.
The same hole exists there structurally; section 2 reports it as 0-for-1,111 and it is the user's
call whether to re-open a verified artefact to close a hole that never fired.

## 5. PRE-REGISTERED PREDICTIONS — written before the run

| | prediction |
|---|---|
| **P1** | The fix changes **at most the trades whose stop was never set**. If any *other* trade's exit price changes, the mechanism in §2 is wrong and that is a finding to report, not a success. |
| **P2** | The UNI trade exits on its entry bar for materially less than −30 %. Because it stayed below its `4 x ATR` floor for 13 consecutive bars, the entry bar alone must have carried a drop larger than `4 x ATR`, so the clamped exit is a small fraction of 30 %. **The book's total return therefore IMPROVES.** No magnitude is predicted. |
| **P3** | Trade count changes by at most a few. Average concurrent positions is ~3 against a 24-slot cap, so freeing a slot 13 bars early should not admit a new trade. |
| **P4** | Max drawdown does not increase. The fix removes a −30 % tail event; it cannot add one. |

**KILL CRITERION — fixed now, before the run.** If more than 5 trades change, or the trade count
moves by more than 2 %, the mechanism is misdiagnosed: **stop, do not promote the fix, and re-open
the diagnosis.** A one-trade edit that rearranges the book is not a one-trade edit.

## 6. What is NOT being claimed

* This does not make the long book profitable — it already was, and it still is or is not.
* It does not touch the statistical position: the chandelier 8.0 was still selected on n = 2
  regimes that disagree (§49c), and the book is still a timing tool rather than alpha.
* It is a **risk-control correctness** fix. The book's edge claims are unchanged by it and its
  return changes by roughly one to two points out of ninety-five.
