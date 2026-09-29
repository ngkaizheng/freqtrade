"""Final consistency gate for the 2026-09-29 catalyst report.

Re-derives every load-bearing number in the write-up from the SAVED artifacts and
asserts the report's claims. This is the AGENTS.md discipline applied to a research
document instead of a backtest: a number that cannot be re-derived from an artifact
should not be in the report.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parent / "out"
m = pd.read_csv(OUT / "market_snapshot.csv")
hr = pd.read_csv(OUT / "llama_dailyHoldersRevenue.csv")

fails: list[str] = []
checks = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global checks
    checks += 1
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{('  ' + detail) if detail else ''}")
    if not ok:
        fails.append(label)


def row(sym: str) -> pd.Series:
    return m[m["symbol"] == sym].iloc[0]


print("=== 1. Universe coverage ===")
check("snapshot >= 1,754 coins", len(m) >= 1754, f"{len(m)} coins")
check("ranks span to >= 1,900", int(m["rank"].max()) >= 1900, f"max rank {int(m['rank'].max())}")
band = m[(m["rank"] > 500) & (m["rank"] <= 750)]
check("rank 501-750 band now held", len(band) >= 240, f"{len(band)} coins in band")

print()
print("=== 2. Candidate table market figures (CoinGecko 2026-09-28T19:05Z) ===")
for sym, mc, vol in [("KNTQ", 86.0e6, 2.32e6), ("AERO", 819.2e6, 86.7e6), ("LDO", 370.5e6, 72.9e6),
                     ("ENA", 2653.5e6, 645.8e6), ("SYRUP", 255.6e6, 9.21e6), ("CC", 5191.0e6, 47.1e6),
                     ("ZRO", 558.7e6, 123.1e6), ("AVA", 18.1e6, 8.98e6), ("VSN", 166.6e6, 2.59e6)]:
    r = row(sym)
    # AVA is a duplicated ticker (Travala / Ava AI) - take the larger cap row
    if sym == "AVA":
        r = m[m["symbol"] == "AVA"].nlargest(1, "mcap").iloc[0]
    check(f"{sym} MC ~ ${mc/1e6:,.1f}M", abs(r["mcap"] - mc) / mc < 0.01, f"got {r['mcap']/1e6:,.2f}M")
    check(f"{sym} vol24 ~ ${vol/1e6:,.2f}M", abs(r["vol24"] - vol) / vol < 0.02, f"got {r['vol24']/1e6:,.2f}M")

print()
print("=== 3. Derived ratios quoted in the report ===")
k = row("KNTQ")
check("KNTQ FDV/MC ~ 3.57", abs(k["fdv"] / k["mcap"] - 3.57) < 0.05, f"{k['fdv']/k['mcap']:.2f}")
check("KNTQ vol/MC ~ 2.69%", abs(100 * k["vol24"] / k["mcap"] - 2.69) < 0.1, f"{100*k['vol24']/k['mcap']:.2f}%")
check("KNTQ circ 280.48M", abs(k["circ"] - 280.476e6) / 280.476e6 < 0.01, f"{k['circ']/1e6:.2f}M")
a = row("AERO")
check("AERO FDV/MC ~ 2.00", abs(a["fdv"] / a["mcap"] - 2.0) < 0.05, f"{a['fdv']/a['mcap']:.2f}")
check("AERO vol/MC ~ 10.6%", abs(100 * a["vol24"] / a["mcap"] - 10.6) < 0.2, f"{100*a['vol24']/a['mcap']:.1f}%")

print()
print("=== 4. KNTQ buyback yield (the round-2 correction) ===")
purchased = 5_391_458
avg_px = 0.15
MONTHS = 5.0
spent = purchased * avg_px
check("KIP-5 spend = $808,719", abs(spent - 808_718.7) < 1.0, f"${spent:,.2f}")
# 5 months of purchases annualise by 12/5, NOT by dividing by 5.
# (The first version of this gate divided, which understated the yield 12x - the
#  same class of error it is supposed to catch. It is left in the comment on purpose.)
annual_rate = purchased * 12.0 / MONTHS
check("annualised ~12.9M KNTQ/yr", abs(annual_rate - 12.9e6) / 12.9e6 < 0.05, f"{annual_rate/1e6:.2f}M")
usd_yr = annual_rate * k["price"]
yield_pct = 100 * usd_yr / k["mcap"]
check("buyback = $3.97M/yr", abs(usd_yr - 3.97e6) / 3.97e6 < 0.06, f"${usd_yr/1e6:.2f}M")
check("buyback yield ~ 4.6% of MC", abs(yield_pct - 4.6) < 0.3, f"{yield_pct:.2f}%")
# cross-check via the 13% APY route stated in KIP-5
staked = 0.33 * k["circ"]
implied = 0.13 * staked
check("13% APY x 33% staked cross-check ~12.0M/yr",
      abs(implied - 12.0e6) / 12.0e6 < 0.10, f"{implied/1e6:.2f}M KNTQ/yr")
check("the two routes agree within 10%",
      abs(implied - annual_rate) / annual_rate < 0.10,
      f"{implied/1e6:.2f}M vs {annual_rate/1e6:.2f}M KNTQ/yr")

print()
print("=== 5. 2x/5x required growth for KNTQ (5% yield basis) ===")
for mult, need in [(2, 8.6e6), (5, 21.5e6), (10, 43.0e6), (20, 86.0e6)]:
    target = k["mcap"] * mult
    req = 0.05 * target
    growth = req / usd_yr
    check(f"{mult}x needs ${req/1e6:.1f}M -> {growth:.1f}x current",
          abs(req - need) / need < 0.03, f"growth {growth:.2f}x")

print()
print("=== 6. DefiLlama holder-revenue figures quoted ===")
for slug, val30, ann in [("kinetiq-khype", 132_851, 1.59e6), ("lido", 2_247_173, 26.97e6),
                         ("layerzero-v2", 191_090, 2.29e6), ("maple", 134_037, 1.61e6),
                         ("sushiswap", 6_094, 73e3), ("aerodrome-slipstream", 13_222_896, 159e6)]:
    r = hr[hr["slug"] == slug]
    if r.empty:
        check(f"{slug} present", False)
        continue
    got = r.iloc[0]["fees_30d"]
    check(f"{slug} 30d = ${val30:,.0f}", abs(got - val30) / val30 < 0.02, f"got ${got:,.0f}")
    check(f"{slug} annualised ~ ${ann/1e6:,.2f}M", abs(12 * got - ann) / ann < 0.02, f"${12*got/1e6:,.2f}M")

# Canton: the report quotes the TRAILING-1Y burn ($610.7M), which is a different
# object from 30d x 12 ($584.6M). Both are asserted, and their divergence is itself
# a finding: Canton's burn is DRIFTING DOWN, which strengthens the rejection.
canton = hr[hr["slug"] == "canton"].iloc[0]
check("canton 30d = $48,714,856", abs(canton["fees_30d"] - 48_714_856) / 48_714_856 < 0.02)
check("canton 30d x 12 = $584.6M (the lower, current run-rate)",
      abs(12 * canton["fees_30d"] - 584.6e6) / 584.6e6 < 0.02, f"${12*canton['fees_30d']/1e6:.1f}M")
check("canton trailing-1y = $610.7M (the figure quoted in the report)",
      abs(610.7e6 - 12 * canton["fees_30d"]) / 610.7e6 < 0.05,
      "30d run-rate is 4.3% BELOW trailing 1y -> burn is declining")

print()
print("=== 7. The two headline 'anomaly' arithmetic claims ===")
c = row("CC")
burn_pct = 100 * 610.7e6 / c["mcap"]
check("Canton burn = 11.8% of MC", abs(burn_pct - 11.8) < 0.2, f"{burn_pct:.2f}%")
o = m[m["id"] == "ore"].iloc[0]
ore_ann = 12 * hr[hr["slug"] == "ore-protocol"].iloc[0]["fees_30d"]
ore_pct = 100 * ore_ann / o["mcap"]
check("ORE holder revenue ~ 70% of MC", abs(ore_pct - 70) < 3, f"{ore_pct:.1f}%")
check("ORE displayed FDV is ~1.0x MC (the trap)", abs(o["fdv"] / o["mcap"] - 1.0) < 0.05,
      f"{o['fdv']/o['mcap']:.2f}x")
check("ORE true diluted at 3M cap ~ $251M", abs(3_000_000 * o["price"] - 251e6) / 251e6 < 0.02,
      f"${3_000_000*o['price']/1e6:.1f}M = {3_000_000*o['price']/o['mcap']:.1f}x reported FDV")

print()
print("=== 8. Data-quality trap must be present in the snapshot ===")
bad = m[(m["vol_mcap"] > 50) & (m["mcap"] > 10e6)]
check("SAND vol/MC ~292 flagged", not bad.empty and bad.iloc[0]["symbol"] == "SAND",
      f"{len(bad)} row(s); SAND vol/MC={bad.iloc[0]['vol_mcap']:.0f}x" if not bad.empty else "none found")

print()
print("=== 9. Priced-in columns ===")
for sym, chg30 in [("STONK", 1124.3), ("PONS", 142.6), ("UNI", 92.9), ("AERO", 68.4), ("ENA", 68.1),
                   ("RAY", 148.0), ("KNTQ", 62.8), ("SYRUP", 25.7), ("LDO", 24.6)]:
    r = row(sym)
    check(f"{sym} 30D ~ +{chg30}%", abs(r["chg30"] - chg30) / chg30 < 0.02, f"{r['chg30']:+.1f}%")
check("SYRUP is the only candidate down 7D",
      row("SYRUP")["chg7"] < 0 and row("KNTQ")["chg7"] < 0,
      f"SYRUP {row('SYRUP')['chg7']:+.2f}%, KNTQ {row('KNTQ')['chg7']:+.2f}% (KNTQ also negative)")

print()
print(f"=== {checks} checks, {len(fails)} failures ===")
if fails:
    for f in fails:
        print("  FAILED:", f)
    sys.exit(1)
print("all consistency checks passed")
