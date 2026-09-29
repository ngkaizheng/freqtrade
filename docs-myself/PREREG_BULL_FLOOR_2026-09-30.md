# PREREG — B-6: THE LONG BOOK IGNORES ITS OWN `atr_stop`. THE FLOOR IS 1.5, NOT 4.0

**Date:** 2026-09-30 · **Written after the diagnosis and before the fix was applied or re-run.**
**Subject:** `user_data/strategies/PerpLong4h.py:179` (`_anchor_stop_price`, the long branch).
**Supersedes part of:** `PREREG_BULL_STOPHOLE_2026-09-30.md` — see §6, which corrects my own
reasoning rather than quietly replacing it.

---

## 1. The defect

```python
# PerpShort4hStop.py:36-38   -- the config is read into STOP_MULT
@property
def stop_mult(self) -> float:
    return float(self.config.get("atr_stop", self.atr_stop))

# PerpShort4hStop.py:40-47   -- the SHORT path uses stop_mult
def _anchor_stop_price(self, pair, trade):
    return trade.open_rate * lev + self.stop_mult * atr

# PerpLong4h.py:172-179      -- the LONG path uses atr_stop
def _anchor_stop_price(self, pair, trade):
    if trade.is_short:
        return super()._anchor_stop_price(pair, trade)     # -> stop_mult  (4.0)  OK
    ...
    return trade.open_rate * lev - self.atr_stop * atr     # -> atr_stop   (1.5)  WRONG
```

`atr_stop` is the frozen class constant on `PerpShort4h:122` and equals **1.5**. The config's
`atr_stop: 4.0` is consumed by the property and lands in `stop_mult`, which the long branch never
reads. **The delivered long book has been running a 1.5xATR stop floor since it was created.**

## 2. The evidence — a split brain, measured on both sides

**Stop side.** For every stop exit, `m = (entry - stop) / ATR(entry bar)`. A floor guarantees
`m <= atr_stop`, and trades where the floor binds sit exactly at it.

| | |
|---|---:|
| stop exits analysed | 993 |
| of which the stop trailed **above** entry (locked-in winners, `m < 0`) | 158 |
| remaining, analysed for the floor | 835 |
| **`m` within 0.02 of 1.5** | **797 (95.4 %)** |
| **`m` within 0.02 of 4.0** | **0 (0.0 %)** |
| median `m` | **1.5000** |
| `m > 1.52` (floor violated) | **1** — the UNI backstop fallthrough, §B-5 |

**Sizing side.** `PerpLong4h` does not override `custom_stake_amount`, so it inherits
`PerpShort4hStop`'s, which uses `self.stop_mult`. Recomputing the stake for the first 250 trades:

| assumed stop multiple in sizing | median relative error |
|---|---:|
| **4.0 (`stop_mult`)** | **6.6 %** |
| 1.5 (`atr_stop`) | 159.4 % |

**So the position is sized for a 4.0xATR stop and stopped at 1.5xATR.** The two halves of the risk
architecture disagree by a factor of 2.67.

## 3. What that means for the published number

Realised risk per trade is `1.5 / 4.0 = 37.5 %` of the intended 0.5 %, i.e. **≈ 0.1875 % of equity
per trade**, at 2.67x the intended notional per position.

**`BULL_BOOK_B4_RESULT_2026-09-30.md`'s +95.43 % / +70.6 % / Sharpe 0.96 are a 0.1875 %-risk
result. They do not describe the 0.5 %-risk book the deliverable documents.** Every number in that
document, and the whole chandelier curve it was selected from, is measured at the wrong risk. This
is not a rounding difference; it is the difference between a strategy and a different strategy.

## 4. The fix

One token: `self.atr_stop` → `self.stop_mult` in the long branch. **`PerpShort4hDeploy`,
`PerpShort4hStop` and `PerpShort4h` are not touched** — the short book already used `stop_mult`
and `verify_stop.py` verified 383/383 of its stops at 4.0xATR, so it is unaffected and stays
byte-identical.

## 5. PRE-REGISTERED — written before the run

| | prediction |
|---|---|
| **P1** | The floor moves to 4.0xATR and stays there. The gate's floor test, re-pointed at `stop_mult`, must then find 0 violations and a large population at exactly 4.0. **If the population still sits at 1.5, the fix did not take and nothing below may be believed.** |
| **P2** | **The trade count RISES.** A 4.0xATR floor is 2.67x further away, so trades survive stop-outs that used to kill them, and the no-time-stop `run` mode keeps them alive. Expect materially more than 1,000 trades. A flat trade count would mean the floor is not what binds, and the whole diagnosis would need revisiting. |
| **P3** | **The UNI backstop fallthrough disappears.** The escape window is the entry-bar dip that exceeds the floor; widening the floor 2.67x widens that window. If it survives, the `return None` guard is a second, independent defect and B-5's fix is still needed on its own. |
| **P4** | The return goes **UP**, because more capital-at-risk is actually deployed: the same signal, 2.67x the intended risk per trade. **No magnitude is predicted** — a wider stop also converts some winners into full stops, and the two effects are not obviously ordered. |
| **P5** | Max drawdown goes **UP** by roughly the same factor. If the drawdown does NOT rise, the extra risk is being wasted somewhere and that is itself a finding. |

**KILL CRITERION.** If the short book changes at all — any of the 1,111 trades, any byte of the
frozen three files — this round is void and the repository must be restored. The short book is the
release-verified artefact and this fix is not allowed to touch it.

## 6. CORRECTION to `PREREG_BULL_STOPHOLE_2026-09-30.md`

That document predicted the UNI fallthrough was an isolated `return None` hole and proposed
clamping the trail. **Its reasoning assumed the floor was 4.0xATR.** It is 1.5xATR. That makes the
fallthrough much more likely — an entry-bar dip only has to exceed 1.5xATR rather than 4xATR to
escape the stop entirely — so the fallthrough is most likely a **consequence of this defect rather
than an independent one**.

Both are still real and both are still fixed, but the order matters and the prereg order was wrong:
**fix the floor first, then re-measure whether the fallthrough still exists.** The clamp in B-5 is
therefore NOT applied yet. It stays pre-registered and waits for P3's answer.
