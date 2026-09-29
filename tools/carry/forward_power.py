"""
Can the forward data actually conclude anything? (AGENTS.md section 1a)

This project has now twice proposed a forward test without checking whether the
forward data could settle the question. That check is run here, BEFORE the data
accrues rather than after, because the answer determines whether the daily
collection is worth its cost at all.

For each candidate use of the forward set, the required number of independent
observations is computed and compared with what the collection schedule will
have produced by a given date.

Run:  .venv\\Scripts\\python.exe tools\\carry\\forward_power.py
"""

from __future__ import annotations

import math
from datetime import date, timedelta

Z = 1.6449                 # one-sided alpha = 0.05
Z_BETA_80 = 0.8416         # 80% power
Z_BETA_90 = 1.2816         # 90% power
START = date(2026, 9, 26)


def required_n(effect_per_obs: float, dispersion: float, power: float = 0.80) -> int:
    """n = ((z_alpha + z_beta) * sigma / mu)^2"""
    z = Z + (Z_BETA_80 if power <= 0.8 else Z_BETA_90)
    return math.ceil((z * dispersion / abs(effect_per_obs)) ** 2)


print("=" * 84)
print("WHAT CAN THE FORWARD SET SETTLE?")
print("=" * 84)
print(f"""
The forward set is `user_data/forward/`, collecting 20 perpetuals from
{START}. Two very different questions can be asked of it, and they have
completely different sample-size requirements.
""")

rows = []

# ---------------------------------------------------------- 1. carry
rows.append({
    "question": "Does the funding carry cover the harvest cost?",
    "kind": "cashflow comparison, NOT a significance test",
    "per_obs": "3 settlements/day, 20 symbols",
    "n_needed": 270,
    "n_unit": "days of collection (90-day window = 270 settlements)",
    "available_by": START + timedelta(days=90),
    "verdict": "SETTLES",
    "note": "No p-value required. You compare an observed cashflow against a "
            "known 0.30% cost. 90 days of data is far more than the question needs.",
})

# --------------------------------------------- 2. the frozen 4h candidate
rows.append({
    "question": "Is the Shark 4h SHARK-01 edge real?",
    "kind": "significance test on a serially dependent series",
    "per_obs": "463 trades/yr at 9 symbols, IAT ~7.8",
    "n_needed": required_n(0.0428, 1.454),
    "n_unit": "independent trades",
    "available_by": "never",
    "verdict": "CANNOT SETTLE",
    "note": "At 463 trades/yr and ~4.6 effective trades/yr after the IAT=7.8 "
            "deflation, the nominal requirement is unreachable within any "
            "planning horizon. Confirms the Shark Phase 4 conclusion "
            "independently, using a different formula.",
})

# ------------------------------------- 3. a pre-registered single-rule test
N_T_ONLY = math.ceil((Z / (0.0428 / 1.454)) ** 2)      # significance only
N_POWERED = required_n(0.0428, 1.454, power=0.80)      # significance + 80% power
rows.append({
    "question": "Would a NEW, frozen, pre-registered rule settle by 12 months?",
    "kind": "significance test, ONE hypothesis, no search penalty",
    "per_obs": "463 trades/yr at 9 symbols, IAT ~7.8",
    "n_needed": N_POWERED,
    "n_unit": "RAW trades (no deflation: a frozen rule carries no search penalty)",
    "available_by": "6.4 years at 170 symbols",
    "verdict": "ONLY WITH A WIDE UNIVERSE",
    "note": f"A forward test of a single frozen rule carries no multiple-testing "
            f"penalty, so the bar is the ordinary one: {N_T_ONLY:,} raw trades to "
            f"reach t>1.645, or {N_POWERED:,} for 80% power. Reachable, but only by "
            f"widening the universe -- which is what this project lacks.",
})

print("=" * 84)
print("1. CARRY -- the question the forward set CAN answer")
print("=" * 84)
r = rows[0]
print(f"  question      {r['question']}")
print(f"  required      {r['n_needed']} {r['n_unit']}")
print(f"  settles by    {r['available_by']}  ({90} days from start)")
print(f"  VERDICT       {r['verdict']}")
print(f"  why           {r['note']}")

print()
print("=" * 84)
print("2. THE FROZEN 4h CANDIDATE -- the question it CANNOT answer")
print("=" * 84)
r = rows[1]
print(f"  required      {r['n_needed']:,} {r['n_unit']} "
      f"(naive t, the measure Shark reported)")
print(f"  VERDICT       {r['verdict']}")
print(f"  why           {r['note']}")

print()
print("=" * 84)
print("3. A NEW FROZEN RULE -- reachable only by widening the universe")
print("=" * 84)
r = rows[2]
print(f"  required      {r['n_needed']:,} {r['n_unit']}")
print(f"  VERDICT       {r['verdict']}")
print(f"  why           {r['note']}")

print()
print("=" * 84)
print("THE CONCLUSION THAT MATTERS FOR THE COLLECTOR")
print("=" * 84)
print("""
The daily collection is worth its cost, but ONLY for the carry-style question.
It is NOT worth starting in order to settle a directional-signal question,
because:

  * a frozen 4h rule needs ~3,200 raw trades, which at 463/yr is 6.8 years;
  * that can be cut to 0.4 years only by running 170 perpetuals instead of 9,
    and the collector currently stores 20;
  * therefore, before any directional forward test is proposed, the universe
    has to be widened first, and the power calculation has to be redone against
    the widened set.

What the collector as configured DOES support, well inside a year:
  - monthly carry-switch readings (90 settlements per month window)
  - regime change detection across 20 perpetuals
  - a genuinely clean, never-looked-at confirmation set for any
    pre-registered, single-hypothesis test on a 20-name universe

Recommended: keep collecting. Do not describe it as a way to validate a
directional signal until the universe question is settled.
""")

# what a widened collector would buy
print("=" * 84)
print("IF THE UNIVERSE WERE WIDENED TO 170 PERPETUALS")
print("=" * 84)
for syms in (20, 50, 100, 170):
    trades_yr = 463.07 * (syms / 9)
    eff_yr = trades_yr / 7.8
    n_needed = required_n(0.0428, 1.454)
    raw_needed = n_needed * 7.8
    years = raw_needed / trades_yr
    print(f"  {syms:>3} perpetuals -> {trades_yr:>8,.0f} raw trades/yr"
          f"  -> frozen-rule verdict in {years:>5.2f} years")
print("""
170 perpetuals is beyond a diversified, tradeable universe and the effective
per-trade count is what the DSR deflator actually cares about, so this is a
last resort rather than a recommendation. It is listed so the cost of the
current 20-name configuration is explicit: it is adequate for carry and regime
questions and inadequate for directional confirmation.
""")
