"""One-off: record the operating-point decision (N=40) and the retreat from the
previous, unevidenced "take the middle, N=100" advice.
"""
import io
import sys

P = "docs-myself/RESEARCH_STATE.md"

ROW = (
    "| **Which rung to actually run — a minimax rule applied to the PUBLISHED "
    "two-window ladder** | **2026-09-29 — N = 40. And it RETRACTS this repo's own "
    "previous advice of 'take the middle, N=100', which was an unevidenced round "
    "number** | `PICK_THE_RUNG_2026-09-29.md`; "
    "`tools/perp_short/{pick_rung,repoint_collector}.py`; collector re-pointed to "
    "N=40, liquidity order asserted. **No new backtest was run** - the ladder and "
    "both windows were already published in `WALKFORWARD_RESULT_2026-09-28.md` and "
    "this is a decision rule applied to them. **⚠ THE RULE WAS APPLIED AFTER BOTH "
    "WINDOWS WERE SEEN**, so it is a standard robustness criterion and **not a "
    "pre-registered gate**, and must not be reported as one. **THE RULE: choose N to "
    "maximise min(t_DEV, t_OOS) - minimax regret on the two published estimates, "
    "because a rung that is beautiful in one window and mediocre in the other is "
    "exactly the failure mode of an in-sample pick.** Naive t, measured COVID "
    "costs: | N | t dev | t oos | min | regret | |25|**2.76**|1.65|1.65|1.11| "
    "|40|1.84|**2.08**|**1.84**|**0.23**| |50|2.21|1.47|1.47|0.75| |100|1.65|1.49|"
    "1.49|0.16| |200|0.65|1.07|0.65|0.42| |300|**-0.43**|1.18|-0.43|1.61| "
    "|515|-2.90|-2.63|-2.90|0.27| **N=25 - the in-sample winner - carries a regret "
    "of 1.11 and drops to 1.65 out of sample: the textbook in-sample mirage, and "
    "the rule rejects it. N=40 wins on BOTH min t (1.84) and regret (0.23, the "
    "lowest of any rung). N=515 is excluded on ECONOMICS rather than by the rule: "
    "it is the only rung with a negative OOS mean R (-0.5074 over 1,230 trades).** "
    "**THE TOP FOUR RUNGS SPAN ONLY 0.38 OF min t - a genuinely flat optimum**, so "
    "25-100 is a plateau and tuning inside it is not worth doing; what matters is "
    "NOT going past 200. **WHAT THE RULE CANNOT DO, STATED WHERE IT IS APPLIED: it "
    "supplies no out-of-sample confirmation (both windows sit inside a sample whose "
    "every bar has been seen), the strictest dependence treatment on OOS is t ~ 0 "
    "at every rung, and the market-neutralised excess is negative at every rung "
    "that clears t=2. **A better operating point is not a better strategy.** |"
)

CHANGE = (
    "| 2026-09-29 | **THE OPERATING POINT IS NOW CHOSEN BY A RULE, AND THE RULE "
    "RETRACTS THIS REPO'S OWN PREVIOUS ADVICE.** `PICK_THE_RUNG_2026-09-29.md`. "
    "The previous round recommended 'take the middle of the range, e.g. N=100' - "
    "**that was a round number with no evidence behind it, and it is wrong**: "
    "N=100's min t is 1.49 against N=40's 1.84. **The rule is minimax regret on the "
    "two ALREADY-PUBLISHED windows - choose N to maximise min(t_DEV, t_OOS) - and "
    "it is applied to numbers already seen, so it is a robustness criterion and NOT "
    "a pre-registered gate.** It picks **N=40 (min t 1.84, regret 0.23, the lowest "
    "regret of any rung)** and it rejects **N=25**, which is the in-sample winner "
    "with t_dev 2.76 and a regret of **1.11** - it falls to 1.65 out of sample, "
    "which is the in-sample mirage the two windows were split to expose. "
    "**The top four rungs span only 0.38 of min t, so 25-100 is a genuine "
    "plateau** and tuning inside it is not worth doing; what matters is not going "
    "past 200, where N=300 has a NEGATIVE development t and N=515 is the only "
    "rung with a negative OOS mean R (-0.5074 over 1,230 trades). The forward "
    "collector has been re-pointed to N=40 with its liquidity order ASSERTED, "
    "because with 24 slots the whitelist order is a decision and not formatting. "
    "**Unchanged and restated: this is a better operating point, not a better "
    "strategy** - no out-of-sample confirmation exists, the strictest dependence "
    "treatment on OOS is t ~ 0 everywhere, and the market-neutralised excess is "
    "negative at every rung that clears t=2. |"
)

A = "| **Which rung to actually run"
B = "| **⚠ THE FORWARD COLLECTOR WAS NOT RUNNING"
C = "| 2026-09-29 | **CORRECTION: THE FORWARD COLLECTOR WAS NOT RUNNING"


def main() -> int:
    with io.open(P, encoding="utf-8") as f:
        lines = f.read().split("\n")
    if any(l.startswith(A) for l in lines):
        print("already present")
        return 0
    idx = next((i for i, l in enumerate(lines) if l.startswith(B)), -1)
    if idx < 0:
        print("anchor not found")
        return 1
    lines[idx:idx] = [ROW]
    ch = next((i for i, l in enumerate(lines) if l.startswith(C)), -1)
    if ch >= 0:
        lines[ch:ch] = [CHANGE]
    with io.open(P, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("inserted the N=40 operating-point row and change-log entry")
    return 0


if __name__ == "__main__":
    sys.exit(main())
