"""S-1: the SAME delivered book, with ONE number changed: rvol 2.0 -> 3.0.

THIS IS A RESEARCH ARM. IT IS NOT THE DEPLOYED STRATEGY.

`PerpShort4hDeploy` is untouched and is what the dry-run collector runs.
This class exists so that `PREREG_STRENGTH_THRESHOLD_2026-09-30.md` can be
executed as a single-variable change and nothing else.

WHAT IS INHERITED UNCHANGED (this is the whole point)
----------------------------------------------------
Everything except one class attribute: the universe (N=40, liquidity-ordered),
0.5 % risk per trade, `atr_stop` 4.0 (read from config), the 2R target, the
42-bar time stop, the low-volatility filter, the 20-bar Donchian, and the
drawdown circuit breaker. If any of those moved, the comparison to the
deployed book would be measuring two things at once.

WHY 3.0 AND NOT 4.0
--------------------
Q-1 (`SIGNAL_STRENGTH_RESULT_2026-09-30.md`) measured the forward returns of
the 2,167 frozen signals binned by rvol, and found them strictly monotone:

    [2.0,2.5)  n=968   +1.063%   <- shorting these LOSES money
    [2.5,3.0)  n=577   -0.169%
    [3.0,4.0)  n=451   -1.621%
    [4.0,inf)  n=171   -3.223%

rvol >= 3.0 keeps 622 signals (169/year). rvol >= 4.0 keeps 171 (47/year),
and E-1 (`EVENT_RATE_RESULT_2026-09-30.md`) already closed the COUNT axis:
fewer events is the wrong direction. **3.0 is where count and quality meet.**

⚠ THE SELECTION BIAS IS DECLARED, NOT AVOIDED
----------------------------------------------
3.0 was chosen by looking at the FULL-sample bin table, which includes
2025-01 -> 2026-08. This project's final holdout was burned on 2026-09-26 and
can never be replaced. **So the backtest this class feeds is a measurement of a
selected rule on a seen sample, not a validation of a hypothesis.** That sentence
belongs in any report of the result, and gate S1f of the preregistration
requires it be there.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join("user_data", "strategies"))
sys.path.insert(0, os.path.join("user_data", "strategies_frontier"))

from PerpShort4hDeploy import PerpShort4hDeploy  # noqa: E402


class PerpShort4hStrength(PerpShort4hDeploy):
    """Frozen delivered book + one change: only the STRONGEST quartile-and-a-half
    of signals is taken. Everything else is inherited byte-for-byte."""

    # The ONLY changed value. The frozen class uses 2.0.
    rvol_threshold = 3.0
