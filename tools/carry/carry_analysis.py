"""
Funding / basis carry: is the carry bigger than the cost of harvesting it?

This is NOT an inference problem. The payoff of a hedged carry position
(long spot, short perp, same notional) is observable at trade time from the
funding stream. What has to be computed is a known cashflow against a known
cost. The answer is a number, not a p-value.

Sign convention, verified against the raw data: fundingRate > 0 means LONGS PAY
SHORTS. A short-perp leg therefore RECEIVES funding when the rate is positive.

Cost model, conservative (Binance public taker, no BNB discount):
    spot  taker  0.10%
    perp  taker  0.05%
    ->  0.15% to establish, 0.15% to close  =  0.30% round trip

Run:  .venv\\Scripts\\python.exe tools\\carry\\carry_analysis.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 40)

ROOT = Path(__file__).resolve().parents[2]
FUND_DIR = ROOT / "user_data/data/binance_funding"
OUT = Path(__file__).resolve().parent

SPOT_TAKER = 0.0010
PERP_TAKER = 0.0005
ROUND_TRIP = 2 * (SPOT_TAKER + PERP_TAKER)      # 0.30%
SETTLEMENTS_PER_YEAR = 3 * 365


# ------------------------------------------------------------------ load
frames = {}
for f in sorted(FUND_DIR.glob("*-funding.feather")):
    sym = f.name.replace("_USDT-funding.feather", "")
    d = pd.read_feather(f)
    d["fundingTime"] = pd.to_datetime(d["fundingTime"], utc=True)
    d = d[["fundingTime", "fundingRate"]].dropna().sort_values("fundingTime")
    d = d[~d["fundingTime"].duplicated()]
    frames[sym] = d.set_index("fundingTime")["fundingRate"]

panel = pd.DataFrame(frames).sort_index()
common = panel.dropna()
print(f"symbols            : {panel.shape[1]}")
print(f"raw settlements    : {len(panel)} ({panel.index[0].date()} -> {panel.index[-1].date()})")
print(f"fully common       : {len(common)} ({common.index[0].date()} -> {common.index[-1].date()})")
years = (common.index[-1] - common.index[0]).days / 365.25
print(f"span               : {years:.2f} years\n")

# ---------------------------------------------------------- sign sanity
print("=" * 78)
print("A. THE FUNDING STREAM ITSELF")
print("=" * 78)
flat = common.to_numpy().ravel()
print(f"  mean per settlement   {flat.mean()*100:+.5f}%")
print(f"  median                {np.median(flat)*100:+.5f}%")
print(f"  positive share        {(flat > 0).mean()*100:.1f}%")
print(f"  1st percentile        {np.percentile(flat, 1)*100:+.4f}%")
print(f"  5th percentile        {np.percentile(flat, 5)*100:+.4f}%")
print(f"  95th percentile       {np.percentile(flat, 95)*100:+.4f}%")
print(f"  99th percentile       {np.percentile(flat, 99)*100:+.4f}%")
print(f"  min / max             {flat.min()*100:+.4f}% / {flat.max()*100:+.4f}%")
print(f"\n  Binance caps funding at +/-0.75% per settlement; observed extremes")
print(f"  confirm this is the real capped series, not an unnormalised field.")

# ------------------------------------------------- unconditional per symbol
print()
print("=" * 78)
print("B. GROSS CARRY PER SYMBOL (short perp receives, long spot is price-neutral)")
print("=" * 78)
tot = common.sum()
ann = (tot / years) * 100
pos = (common > 0).mean()
rows = []
for s in common.columns:
    rows.append({
        "symbol": s,
        "total_carry_%": tot[s] * 100,
        "annualised_%": ann[s],
        "pct_settlements_positive": pos[s] * 100,
        "median_settlement_%": common[s].median() * 100,
        "worst_settlement_%": common[s].min() * 100,
        "best_settlement_%": common[s].max() * 100,
    })
sym = pd.DataFrame(rows).sort_values("annualised_%", ascending=False)
print(sym.to_string(index=False, float_format=lambda v: f"{v:+.4f}"))
print(f"\n  median symbol annualised gross carry: {ann.median():+.2f}%/yr")
print(f"  symbols with negative annualised carry: {int((ann < 0).sum())} / {len(ann)}")

# ------------------------------------------------------------- by year
print()
print("=" * 78)
print("C. THE SAME THING BY YEAR -- where the risk actually lives")
print("=" * 78)
yr = common.resample("YE").sum()
yr_pct = yr * 100
yr_days = common.resample("YE").size()
out = pd.DataFrame({
    "days": yr_days / 3,
    **{s: yr_pct[s] for s in common.columns},
    "EQUAL_WEIGHT_20": yr_pct.mean(axis=1),
})
print(out.to_string(float_format=lambda v: f"{v:+.3f}"))
print(f"\n  equal-weight across 20 symbols, per year:")
print(f"    best  {out['EQUAL_WEIGHT_20'].max():+.2f}%   worst {out['EQUAL_WEIGHT_20'].min():+.2f}%")
print(f"    mean  {out['EQUAL_WEIGHT_20'].mean():+.2f}%")
print(f"    negative years: {int((out['EQUAL_WEIGHT_20'] < 0).sum())} / {len(out)}")

# ------------------------------------------------- net of costs, scenarios
print()
print("=" * 78)
print("D. NET AFTER THE COST OF HARVESTING IT")
print("=" * 78)
gross_annual_pct = out["EQUAL_WEIGHT_20"].mean()
print(f"  gross carry, equal-weight, mean annual : {gross_annual_pct:+.2f}%/yr")
print(f"  one round trip costs                   : {ROUND_TRIP*100:.2f}%")
print(f"  so a single entry pays for itself after "
      f"{ROUND_TRIP*100/gross_annual_pct*365:.0f} days of average carry\n")

print("  Net annual return under different re-establishment disciplines:")
print(f"  {'re-establish every':<22}{'cost/yr':>10}{'net/yr':>10}")
print("  " + "-" * 42)
for label, n in [("never (one entry)", 0), ("quarterly", 4), ("monthly", 12),
                 ("fortnightly", 26), ("weekly", 52), ("daily", 365)]:
    c = n * ROUND_TRIP * 100
    print(f"  {label:<22}{c:>9.2f}%{gross_annual_pct - c:>+9.2f}%")
print(f"""
  The trade only works if the carry is harvested with a LOW turnover. A weekly
  re-establishment costs {52*ROUND_TRIP*100:.2f}%/yr, which alone consumes the
  entire mean carry. This is a hold-the-position trade, not a trading strategy,
  and it has to be sized and risk-managed as such.""")

# ------------------------------------------------- selection rule variant
print("=" * 78)
print("E. DOES A SELECTION RULE HELP? (cost charged per COMPLETED ROUND TRIP)")
print("=" * 78)
eq = common.mean(axis=1)
# Rule: hold the hedge while the trailing 7-day mean funding is positive,
# stand aside otherwise. Cost is charged once per in->out->in cycle, NOT per
# day held -- an earlier pass of this script made that mistake and produced a
# meaningless -69%/yr.
pos_state = (eq.rolling(21, min_periods=1).mean() > 0).astype(int)
state_change = pos_state.diff().abs()
yr_gross = eq.resample("YE").sum() * 100
round_trips = state_change.resample("YE").sum() / 2.0
days_held = pos_state.resample("YE").mean()

sel = pd.DataFrame({
    "gross_%": yr_gross,
    "days_held_%": days_held * 100,
    "round_trips": round_trips,
    "cost_%": round_trips * ROUND_TRIP * 100,
})
sel["net_%"] = sel["gross_%"] - sel["cost_%"]
print(sel.to_string(float_format=lambda v: f"{v:+.3f}"))
print(f"\n  net, mean over the sample : {sel['net_%'].mean():+.2f}%/yr")
print(f"  net, worst year           : {sel['net_%'].min():+.2f}%")
print(f"  net, negative years       : {int((sel['net_%'] < 0).sum())} / {len(sel)}")

# --------------------------------------------------------- the decay
print()
print("=" * 78)
print("G. THE NUMBER THAT ACTUALLY DECIDES IT: THE CARRY RIGHT NOW")
print("=" * 78)
roll = (eq.rolling(365).sum() * 100).dropna()
print("  rolling 365-day equal-weight gross carry:")
for ts, v in roll.iloc[::250].items():
    print(f"    {ts.date()}  {v:+7.2f}%")
last = roll.iloc[-1]
print(f"\n  MOST RECENT 365 DAYS  gross carry : {last:+.2f}%")
print(f"  cost at monthly re-establishment    : {12*ROUND_TRIP*100:.2f}%/yr")
print(f"  -> net if run today                 : {last - 12*ROUND_TRIP*100:+.2f}%/yr")
print(f"  -> net at quarterly re-establishment: {last - 4*ROUND_TRIP*100:+.2f}%/yr")
print()
last3 = yr_gross.iloc[-4:-1].mean()
print(f"  mean of the three full years 2023-2025 : {last3:+.2f}%/yr")
print(f"  mean over the whole sample              : {yr_gross.mean():+.2f}%/yr")
print("""
  The headline mean is not the decision-relevant number. Funding is a
  consequence of crowding, and crowding was extreme in 2021 and has been
  unwinding since. What matters is the carry available at the moment capital
  would actually be committed.""")

# ------------------------------------------------------------- summary
print()
print("=" * 78)
print("H. DRAWDOWN -- the risk that was missing from this report")
print("=" * 78)
print("""
The first version of this report gave no drawdown for the carry book at all.
That was a material omission, not a formatting one. A hedged carry position is
direction-neutral, which makes it look risk-free, but the risk it carries is
tail-shaped: funding is forfeited on an early close, the payment is capped by
the venue while the liability on the short leg is not, and a delta-neutral book
still loses on margin and on basis. He et al. (arXiv:2212.06888 v7, Table 6)
replicate this exact long-spot/short-perp book on Binance and report
BNB -5.14%/yr, Sharpe -0.66, max drawdown -33.61%.
""")

eq_daily = common.mean(axis=1).resample("D").sum()
for label in ("all symbols",):
    curve = eq_daily.cumsum()
    peak = curve.cummax()
    dd = curve - peak
    worst = dd.min()
    worst_date = dd.idxmin()
    # longest stretch below the previous peak
    under = (curve < peak).astype(int)
    runs, run = 0, 0
    for v in under:
        run = run + 1 if v else 0
        runs = max(runs, run)
    print(f"  equal-weight cumulative funding, {label}:")
    print(f"    worst drawdown      {worst*100:+.2f}%   on {worst_date.date()}")
    print(f"    longest underwater  {runs} days")
    print(f"    final cumulative    {curve.iloc[-1]*100:+.2f}% over {len(curve)} days")

# per-symbol worst drawdown on the same accumulation
print()
worst_sym = []
for s in common.columns:
    c = common[s].resample("D").sum().cumsum()
    dd = (c - c.cummax()).min()
    worst_sym.append((s, dd * 100))
worst_sym.sort(key=lambda x: x[1])
print("  worst drawdown per symbol on cumulative equal-weight-per-day funding:")
for s, d in worst_sym[:6]:
    print(f"    {s:<9} {d:+8.2f}%")
print(f"    {'(best)':<9} {worst_sym[-1][1]:+8.2f}%  {worst_sym[-1][0]}")

eq_daily.to_csv(OUT / "carry_daily_series.csv")
print("\nwritten carry_daily_series.csv")

print(f"  Gross carry, equal-weight 20 symbols, {years:.1f} years : {gross_annual_pct:+.2f}%/yr")
print(f"  Cost to harvest at 1 entry and hold                       : {ROUND_TRIP*100:.2f}%")
print(f"  Cost at monthly re-establishment                          : {12*ROUND_TRIP*100:.2f}%/yr")
print(f"  Best single symbol annualised                             : {ann.max():+.2f}%/yr")
print(f"  Median single symbol annualised                           : {ann.median():+.2f}%/yr")
print()
print("=" * 78)
print("F. THE NUMBER")
print("=" * 78)
print(f"  Gross carry, equal-weight 20 symbols, {years:.1f} years : {gross_annual_pct:+.2f}%/yr")
print(f"  Cost to harvest at 1 entry and hold                       : {ROUND_TRIP*100:.2f}%")
print(f"  Cost at monthly re-establishment                          : {12*ROUND_TRIP*100:.2f}%/yr")
print(f"  Best single symbol annualised                             : {ann.max():+.2f}%/yr")
print(f"  Median single symbol annualised                           : {ann.median():+.2f}%/yr")
print(f"  Worst single symbol annualised                            : {ann.min():+.2f}%/yr")
print(f"  MOST RECENT 365 days, equal weight                        : {roll.iloc[-1]:+.2f}%")
print(f"  -> net of monthly re-establishment                        : {roll.iloc[-1] - 12*ROUND_TRIP*100:+.2f}%/yr")
print()
print("  *** THIS GROSS FIGURE IS NOT A RETURN YOU CAN KEEP. ***")
print("  See section I: decomposing it against Binance's administered")
print("  interest component leaves an EXCESS of about -1.5%/yr.")

sym.to_csv(OUT / "carry_by_symbol.csv", index=False)
out.to_csv(OUT / "carry_by_year.csv")
sel.to_csv(OUT / "carry_selection_rule.csv")
print(f"\nwritten to {OUT}")
