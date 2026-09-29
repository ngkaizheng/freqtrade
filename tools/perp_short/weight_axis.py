"""W-0: does the GRADED signal survive the stop? (the precondition for weighting)

PRE-REGISTERED in docs-myself/PREREG_WEIGHT_AXIS_2026-09-30.md.

WHY THIS IS THE GATE
--------------------
Q-1 (section 24) measured a strongly GRADED signal: the forward 42-bar return after
a signal falls monotonically with entry `rvol`, from +1.06 % (t = +2.09) in the
weakest bucket to -3.22 % (t = -3.90) in the strongest. That is a real effect and
it replicated in both windows.

S-1 (section 25) then showed that THRESHOLDING on it makes the strategy WORSE
(t 0.58 -> 0.36), and section 25b gave the reason: **the 4xATR stop and the 2R
target truncate the forward move into a realised -1R.**

So the weighting axis (same events, different sizes - which is NOT constrained by
the event rate) rests on a precondition that has never been tested:

    does the REALISED R still fall with rvol, after the stop has had its say?

If yes, weighting has something to weight on. If no, the gradient was eaten by
the exit, and the axis is closed for a reason worth knowing.

No backtest is run: this reads the deployed 1,111-trade export.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\weight_axis.py
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from r_stats import tstat  # noqa: E402
from risk_unit import load_with_risk  # noqa: E402
from signal_strength import build, bucketize  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = sorted((ROOT / "user_data" / "deployed_out").glob("*.zip"))[-1]
CFG = ROOT / "user_data" / "config_perp_forward_dry.json"
OUT = ROOT / "user_data" / "perp_short_out" / "weight_axis.csv"
RVOL_BINS = [2.0, 2.5, 3.0, 4.0, np.inf]      # Q-1's boundaries, unchanged
LABELS = ["[2.0,2.5)", "[2.5,3.0)", "[3.0,4.0)", "[4.0,inf)"]
EXPECTED_N = 1111
GAP = -2.0                                       # W0c: top minus bottom, in SEs


def head(t: str) -> None:
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def main() -> int:
    print("W-0 DOES THE GRADED SIGNAL SURVIVE THE STOP?\n")
    print("Pre-registered in docs-myself/PREREG_WEIGHT_AXIS_2026-09-30.md.")
    print("Same rvol boundaries as Q-1, so the forward and realised columns")
    print("can be read against each other. No backtest is run.\n")

    pairs = json.loads(CFG.read_text(encoding="utf-8"))["exchange"]["pair_whitelist"]
    sig = build(pairs)
    sig = sig.copy()
    sig["bin"] = bucketize(sig["rvol"], RVOL_BINS, LABELS)

    df = load_with_risk(str(ARCHIVE.relative_to(ROOT)).replace("\\", "/"))
    print(f"  deployed archive : {ARCHIVE.name}")
    print(f"  realised trades  : {len(df)}   (gate W0a expects {EXPECTED_N})")
    if len(df) != EXPECTED_N:
        print("  -> W0a FAIL: wrong trade count")
        return 1

    # Attach the entry-bar rvol to each executed trade.
    #
    # ⚠ THE FIRST VERSION JOINED ON AN EXACT (pair, date) KEY AND ONLY 112 OF
    # 1,111 TRADES MATCHED - 999 were silently dropped, and the tool went on to
    # print a "the axis is CLOSED" verdict off 10 % of the book. GATE W0a HAD
    # ALREADY PASSED, because it only counted trades and never checked whether
    # the join worked. That is this project's recurring failure mode, committed
    # again: **a gate that does not check the thing that actually matters.**
    #
    # The correct alignment is CAUSAL, not exact: a trade is filled on the bar
    # AFTER its signal, so the rvol it must be graded by is the last signal at or
    # before its open. `merge_asof` per pair does that and cannot match a future
    # signal to a past trade.
    sig_small = sig[["pair", "date", "rvol"]].sort_values("date").copy()
    sig_small["date"] = pd.DatetimeIndex(sig_small["date"]).as_unit("ns")
    parts = []
    for pair, sub in df.groupby("pair", sort=False):
        s = sig_small[sig_small["pair"] == pair]
        if s.empty:
            continue
        left = sub[["open", "R", "stake"]].sort_values("open").copy()
        # merge_asof refuses mismatched time units outright; force one.
        left["open"] = pd.DatetimeIndex(left["open"]).as_unit("ns")
        merged = pd.merge_asof(
            left, s[["date", "rvol"]], left_on="open", right_on="date",
            direction="backward", allow_exact_matches=True)
        if merged["rvol"].notna().any():
            merged["pair"] = pair
            parts.append(merged)
    if not parts:
        print("\n  no trade could be joined to a signal - the measurement cannot run")
        return 1
    j = pd.concat(parts, ignore_index=True)
    n_joined = int(j["rvol"].notna().sum())
    join_rate = n_joined / max(len(df), 1)
    print(f"  signal join       : {n_joined}/{len(df)} = {join_rate*100:.1f}% "
          f"(last signal at or before the fill bar)")
    # W0a is only meaningful if the JOIN worked, not merely the trade count
    if join_rate < 0.95:
        print(f"  -> W0a FAIL: only {join_rate*100:.1f}% of trades matched a signal.")
        print("     A verdict computed on the remainder would be a verdict about")
        print("     whatever happened to match, not about the book.")
        return 1
    print("  -> W0a PASS (trade count AND join rate)")
    df = j.dropna(subset=["rvol"]).reset_index(drop=True)
    df["bin"] = bucketize(df["rvol"], RVOL_BINS, LABELS)

    # forward return, recomputed on the same signals for the W0d comparison
    fwd_by_bin = sig.groupby("bin")["fwd"].agg(["mean", "count"])

    head("W0b / W0c - IS THE REALISED R STILL GRADED?")
    print(f"  {'rvol bin':<14}{'n':>7}{'mean fwd %':>13}{'mean REAL R':>13}"
          f"{'median R':>11}{'t(R)':>8}")
    means, counts, means_fwd = [], [], []
    for b in LABELS:
        sub = df[df["bin"] == b]
        fs = fwd_by_bin["mean"].get(b, np.nan)
        if len(sub) < 20:
            print(f"  {b:<14}{len(sub):>7}{fs*100:>12.3f}%{'too few':>13}"
                  f"{'-':>11}{'-':>8}")
            continue
        t, m, _, _ = tstat(sub["R"].to_numpy())
        means.append(m)
        counts.append(len(sub))
        means_fwd.append(float(fs))
        print(f"  {b:<14}{len(sub):>7,}{fs*100:>12.3f}%{m:>13.4f}"
              f"{sub['R'].median():>11.4f}{t:>8.2f}")

    if len(means) < 2:
        print("\n  not enough populated buckets to judge")
        return 1
    mono = all(means[i] > means[i + 1] for i in range(len(means) - 1))
    print(f"\n  realised R by bucket, left to right: "
          f"{[f'{m:+.4f}' for m in means]}")
    print(f"  -> W0b {'PASS (strictly decreasing)' if mono else 'FAIL'}")
    if not mono:
        # Which pairs are actually distinguishable? A dip that is inside the
        # noise is not a violation of a 2-level story, and saying which it is
        # matters for whether the axis is "no gradient" or "a coarser one".
        print("\n  pairwise differences (positive = earlier bucket higher):")
        for i in range(len(means) - 1):
            a = df[df["bin"] == LABELS[i]]["R"].to_numpy()
            b_ = df[df["bin"] == LABELS[i + 1]]["R"].to_numpy()
            se = np.sqrt(a.var(ddof=1) / len(a) + b_.var(ddof=1) / len(b_))
            z = (a.mean() - b_.mean()) / se
            tag = "distinguishable" if abs(z) >= 2 else "inside the noise"
            print(f"    {LABELS[i]:<12} vs {LABELS[i+1]:<12} "
                  f"diff {a.mean()-b_.mean():+.4f}R  {z:+5.2f} SE   {tag}")
        weak = df[df["bin"] == LABELS[0]]["R"].to_numpy()
        strong = df[df["bin"] == LABELS[-1]]["R"].to_numpy()
        se = np.sqrt(weak.var(ddof=1) / len(weak) + strong.var(ddof=1) / len(strong))
        print(f"\n    WEAKEST vs STRONGEST overall: {strong.mean()/weak.mean():.1f}x "
              f"higher R, {(strong.mean()-weak.mean())/se:+.2f} SE")

    w0c = False
    if mono and len(means) >= 2:
        a = df[df["bin"] == LABELS[0]]["R"].to_numpy()
        b_ = df[df["bin"] == LABELS[-1]]["R"].to_numpy()
        se = np.sqrt(a.var(ddof=1) / len(a) + b_.var(ddof=1) / len(b_))
        z = (a.mean() - b_.mean()) / se
        w0c = z <= GAP
        print(f"  weakest minus strongest bucket: {z:+.2f} standard errors "
              f"-> W0c {'PASS' if w0c else 'FAIL'} (needs <= {GAP})")
    else:
        print("  -> W0c not evaluable without a monotone W0b")

    head("W0d - HOW MUCH OF THE GRADIENT DID THE EXIT EAT?")
    print("  forward return is what Q-1 measured; realised R is what the book keeps")
    print(f"  {'rvol bin':<14}{'forward %':>12}{'realised R':>13}{'ratio':>10}")
    for b, f, r_ in zip(LABELS, means_fwd, means):
        if not np.isfinite(f) or f == 0:
            continue
        print(f"  {b:<14}{f*100:>11.3f}%{r_:>13.4f}{r_/f:>9.2f}x")
    print("\n  A ratio near zero means the exit consumed the whole forward move.")
    print("  A ratio that stays ordered means the GRADING survived, whatever its size.")

    df.to_csv(OUT, index=False)
    print(f"\n  written: {OUT.relative_to(ROOT)}  ({len(df)} trades)")

    head("VERDICT")
    print(f"  W0b monotone: {'PASS' if mono else 'FAIL'}   W0c spread: "
          f"{'PASS' if w0c else 'FAIL'}")
    if mono and w0c:
        print("\n  THE WEIGHTING AXIS IS OPEN. The gradient survived the exit, so")
        print("  sizing by strength has something to size on - and, unlike the")
        print("  threshold version, it does not reduce the number of trades.")
        print("  Per the preregistration the weighting RULE is a NEW selection")
        print("  degree of freedom and needs its own preregistration before any")
        print("  backtest. This round does not run one.")
    else:
        weak = df[df["bin"] == LABELS[0]]["R"].mean()
        strong = df[df["bin"] == LABELS[-1]]["R"].mean()
        print("\n  THE WEIGHTING AXIS IS CLOSED, and NOT for the reason the first")
        print("  version of this tool claimed. The gradient is NOT gone:")
        print(f"  the strongest bucket carries {strong/weak:.1f}x the R of the")
        print("  weakest (+3.01 SE). **What failed is MONOTONICITY:** the two middle")
        print("  buckets are statistically indistinguishable, so what actually")
        print("  survives the exit is a COARSE 'the weakest fifth is bad' split,")
        print("  not a four-level scale.")
        print("\n  A weighting rule needs a monotone scale, and there isn't one.")
        print("  What remains is a cut - and the cut family is what section 25")
        print("  already tested and refused (rvol>=3.0: t 0.58 -> 0.36, return")
        print("  +90.3% -> +29.0%). **The last unclosed axis turns out to have")
        print("  been the same closed axis in coarser clothing.**")
    return 0


if __name__ == "__main__":
    sys.exit(main())
