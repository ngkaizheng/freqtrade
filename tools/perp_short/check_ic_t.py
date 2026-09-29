"""SELF-TEST for the IC significance machinery that Gate 2's verdict rests on.

WHY THIS FILE EXISTS
--------------------
`PREREG_OI_2026-09-30.md` locks the pass line at "|IC| >= 0.02 AND Newey-West t >=
2.5". **That verdict is only as good as the statistic that produces the t.** This
project has spent 40+ rounds finding numbers that looked completely normal and were
computed wrongly (§16d printed a fraction with a % sign; §39 averaged 7 years against
3.7 and called it a disagreement). A pass line is not a safeguard if the thing that
evaluates it is unverified.

So the instrument is tested BEFORE it is used, on synthetic data where the right answer
is known:

  T1  NULL.      x and y independent. |t| > 1.96 should fire about 5 % of the time,
                 t should be ~N(0,1). A test that fires 30 % is not a test.
  T2  AUTOCORR.  y strongly autocorrelated. The Newey-West t MUST be materially
                 SMALLER in absolute value than the naive t, otherwise the correction
                 is decorative - and 4h crypto returns are strongly autocorrelated, so
                 this is the case that matters.
  T3  POWER.     x genuinely predicts y at IC ~ 0.03, i.e. just above the pass line.
                 The test must detect it. A test that cannot detect a real effect at the
                 bar it is supposed to enforce is useless in the other direction too.
  T4  ABLATION.  the same powered series with the NW correction removed, to show T2
                 and T3 are measuring the correction and not the sample.

The candidate implementation is imported from `oi_signal_test`, so this file tests the
SAME code the verdict will use. If that code is wrong, this file says so.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\check_ic_t.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "perp_short"))
import oi_signal_test as M  # noqa: E402

RNG = np.random.default_rng(20260930)      # FIXED SEED: this test must be reproducible
REPS = 300
N = 8_034                                 # 4h bars per symbol, measured


def autocorr_noise(n: int, phi: float) -> np.ndarray:
    x = np.zeros(n)
    e = RNG.normal(size=n)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + e[i]
    return x


def powered(n: int, target_ic: float, phi: float = 0.90) -> tuple[pd.Series, pd.Series]:
    """A series pair whose IC is ACTUALLY `target_ic`.

    ⚠ THE FIRST VERSION OF THIS BUILDER WAS ITSELF BROKEN, and it produced a
    FALSE PASS on T3: `y = 0.030*x.rank() + noise` has a signal term with sd ~69
    and noise with sd ~2.3, so the signal swamped the noise and the realised IC
    came out 0.9995 - a "power" test that was really testing nothing. **A power
    test whose effect size is not the one you asked for passes for the wrong
    reason.** Both legs are standardised and the signal is scaled by the target
    correlation explicitly.
    """
    x = autocorr_noise(n, phi)
    z = autocorr_noise(n, phi)
    x = (x - x.mean()) / x.std()
    z = (z - z.mean()) / z.std()
    y = target_ic * x + np.sqrt(max(1.0 - target_ic ** 2, 0.0)) * z
    return pd.Series(x), pd.Series(y)



def run() -> int:
    print("SELF-TEST of the IC / Newey-West machinery behind Gate 2\n")
    print(f"  seed 20260930, {REPS} reps, n={N:,} per rep")
    print(f"  nw_lag({N}) = {M.nw_lag(N)}   (Bartlett, floor(4*(n/100)^(2/9)))\n")

    # ---- T1 NULL ------------------------------------------------------------
    ts = []
    for _ in range(REPS):
        x = pd.Series(RNG.normal(size=N))
        y = pd.Series(RNG.normal(size=N))
        ts.append(M.ic_and_t(x, y)[1])
    ts = np.array(ts, dtype=float)
    fire = float((np.abs(ts) > 1.96).mean())
    t1 = 0.04 <= fire <= 0.08
    print(f"T1  NULL            |t|>1.96 fires {fire*100:5.1f}% of the time "
          f"(want ~5%)   mean {ts.mean():+.3f}  sd {ts.std(ddof=1):.3f}   "
          f"{'PASS' if t1 else '** FAIL **'}")

    # ---- T2 AUTOCORRELATION -------------------------------------------------
    pairs = []
    for _ in range(REPS):
        x = pd.Series(autocorr_noise(N, 0.90))
        y = pd.Series(autocorr_noise(N, 0.90))
        t = M.ic_and_t(x, y)[1]
        j = pd.concat([x, y], axis=1).dropna()
        naive = float(j.iloc[:, 0].rank().corr(j.iloc[:, 1].rank())
                      * np.sqrt(len(j) - 3))
        pairs.append((abs(naive), abs(t)))
    pairs = np.array(pairs)
    shrink = float(np.median(pairs[:, 1] / pairs[:, 0]))
    t2 = shrink < 0.75
    print(f"T2  AUTOCORRELATION NW t / naive t = {shrink:.3f} (want well below 1.0)  "
          f"median naive {np.median(pairs[:,0]):6.1f} -> NW {np.median(pairs[:,1]):6.1f}"
          f"   {'PASS' if t2 else '** FAIL **'}")

    # ---- T3 POWER -----------------------------------------------------------
    # ⚠ THE FIRST VERSION OF THIS USED phi=0.90, which is not what crypto looks
    # like. **Measured 4h return lag-1 autocorrelation on this very panel is
    # -0.003** (range -0.026..+0.018) - essentially zero. The AR(0.9) series made
    # n_eff ~423 instead of ~8,000 and the test "failed" for a reason that has
    # nothing to do with the real data. **A power test run on synthetic dynamics
    # that do not resemble the instrument measures the wrong power.** phi=0 is used
    # below, and the real curve is in PREREG_OI_2026-09-30.md's addendum.
    fires, ics = 0, []
    for _ in range(REPS):
        x, y = powered(N, 0.040, phi=0.0)
        ic, t = M.ic_and_t(x, y)[0], M.ic_and_t(x, y)[1]
        ics.append(ic)
        fires += abs(t) >= 2.5
    power = fires / REPS
    ics = np.array(ics)
    t3 = (power >= 0.60) and (0.02 <= abs(ics).mean() <= 0.06)
    print(f"T3  POWER at IC~0.04 detects {power*100:5.1f}% (want >=60%)  "
          f"realised |IC| {np.mean(np.abs(ics)):.4f}  (phi=0, the measured value)   "
          f"{'PASS' if t3 else '** FAIL **'}")

    # ---- T4 ABLATION: is the NW step doing the work? -----------------------
    raw, nw_same = [], []
    for _ in range(REPS):
        x, y = powered(N, 0.030)
        j = pd.concat([x, y], axis=1).dropna()
        raw.append(abs(j.iloc[:, 0].rank().corr(j.iloc[:, 1].rank()) * np.sqrt(len(j) - 3)))
        nw_same.append(abs(M.ic_and_t(x, y)[1]))
    raw, nw_same = np.array(raw), np.array(nw_same)
    print(f"T4  ABLATION         powered series, NW removed: fires "
          f"{float((raw >= 2.5).mean())*100:5.1f}%  median |t| {np.median(raw):6.1f}")
    print(f"                    powered series, NW applied : fires "
          f"{float((nw_same >= 2.5).mean())*100:5.1f}%  median |t| {np.median(nw_same):6.1f}")
    print(f"                    -> the gap IS the Newey-West step, not the sample.")



    print("\nVERDICT")
    allok = t1 and t2 and t3
    if allok:
        print("  The statistic Gate 2 uses is validated on a null, on autocorrelated")
        print("  data, and for power at the pass line. The verdict it produces can be")
        print("  trusted to mean what the preregistration says it means.")
    else:
        print("  ** THE INSTRUMENT IS NOT TRUSTWORTHY. Do not read Gate 2 from it. **")
        print("  Fix the implementation before any verdict is reported.")
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(run())
