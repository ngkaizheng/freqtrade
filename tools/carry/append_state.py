"""Append the literature-review section and change-log row to RESEARCH_STATE.md.

Append-only, and idempotent: if the marker row is already present it does nothing.
Run once. Written as a script because sibling agents are editing the same file
concurrently and a read-modify-write edit tool call races with them.
"""
import pathlib

P = pathlib.Path("docs-myself/RESEARCH_STATE.md")
MARKER = "CARRY_LIT_REVIEW_2026-09-26"

SECTION = """
---

## 9. External literature + exchange-documentation review (2026-09-26)

**Full deliverable: `docs-myself/CARRY_LIT_REVIEW_2026-09-26.md`.** Seven questions: Binance USD-M
funding mechanics from primary docs; the size of the carry in the literature; whether it decays; what
the payment is *for*; implementation traps; comovement/diversification; and the bear case.

Source quality, explicitly, because this line has been burned by vendor content before. Everything
load-bearing below is either **Binance's own documentation / REST API** or **peer-reviewed or
working-paper**. The 2026 items that are *vendor-adjacent* are labelled in the review and none of them
carries a conclusion on its own. Specifically called out and **not** relied on: CoinGlass,
Glassnode, Amberdata, exchange "Academy" pages, and "we tested this strategy" blog posts.

### What the outside literature confirms

| this repo's finding | external confirmation |
|---|---|
| `fundingRate > 0` = longs pay shorts (§2) | **Binance's own FAQ, verbatim.** Upgrade the provenance from "verified against raw data" to "verified against exchange documentation" |
| ~90% decay, 2022 boundary | He, Manela, Ross & von Wachter (arXiv:2212.06888v7): "After 2022, the average deviation reduces by **almost 80%**"; "**22 percentage points a year**". Crépellière-Pelster-Zeisberger (J. Financial Markets 64, 2023): magnitude "decreased greatly from April 2018 onward… barely possible to exploit". Shynkevich (J. Economics and Finance 47(3), 2023): "declined significantly since 2018" |
| funding correlation 0.627 (§4) | re-measured independently. Plus: **PC1 = 49%** of equal-variance cross-sectional variance, funding-change correlation **0.447**, so a 20-name carry book is a **1.45x** vol reduction, not 4.5x |
| §3.14 the carry is Binance's parameter | He et al. Table B.1: 41.7–50.4% of 8h settlements pay exactly the interest component; the clamp cuts the annualised SD of the payment by **47–82%** vs a linear rule. And **BNBUSDT is the one contract with iota = 0** |
| carry is a hold, not a trade | He et al. Table 46: the perp-spot basis half-life is **1.68 h (BTC)**, 2.34 h (ETH), 9.53 h (DOGE) |
| "0 of 20 negative" is a full-sample statistic | independently reproduced: **6/20 negative from 2022**, **7/20 since 2025** |

### Corrections this review forces

1. **Retracted (in the repo's favour):** a claim in an early message of mine that the 8-hour interval
   had changed for this universe. It had not. The corpus is genuinely 8h throughout — 479 common
   timestamps vs the live Binance stream on BTCUSDT / LINKUSDT / BNBUSDT, **max abs diff
   0.00000000**, gaps 8.0h to float noise. The `3 x 365` annualiser is correct for it.
   *But the interval is administered silently*: since 2025-05-02 a cap/floor hit moves a symbol to
   1h, and since 2026-01-02 it reverts to **4h, not back to 8h**, with no announcement. Read
   `fundingIntervalHours` from `GET /fapi/v1/fundingInfo` per run; do not hard-code 3 x 365.
2. **Refined (§3.14):** the share of settlements paid at exactly the fixed parameter is **36.6%**
   pooled (25.2% post-2025-05-02), not 43%. The sharper statement is the **excess**:
   EW total **+9.40%/yr** vs EW fixed interest component **10.95%/yr** ⇒ **excess −1.55%/yr**;
   BTC **+0.20%/yr**; **negative for 9 of 20 symbols** (BNB −10.29, TRX −9.32, BCH −8.61).
   **BNB is paid at exactly 0.0001 on 0.00% of settlements** — independent confirmation that
   BNBUSDT's iota = 0, and BNB is the *worst* symbol in the panel. One administered parameter
   explains the whole ranking.
3. **New:** the funding **cap binds in the tail** — BTC's realised min and max are exactly ±0.3000%
   (its cap) and SOL's minimum is exactly −2.0000% (its cap). The exchange truncates the payment
   precisely when a funding book is most stressed.
4. **New (Binance doc, verbatim):** funding is **forfeited on early close** — "If you close your
   position prior to the funding time, you will not pay or receive any funding." There is no accrual.
5. **New (Binance doc, verbatim):** funding is **debited against position margin** when balance is
   insufficient, "which may affect your liquidation price".
6. **The strongest bear-case datum is a measured drawdown, not a theory.** He et al. Table 6 replicate
   this exact strategy on Binance: BNB return **−5.14%/yr**, SR **−0.66**, maxDD **−33.61%**,
   alpha **−7.13** (t = **−2.21**). `tools/carry/REPORT.md` reports **no drawdown for carry at all**.

### The best-documented round-trip cost for a spot+perp hedge

He et al. Table 3, from Binance's published fee schedule, one-way **maker** fees, `c = 2(c_S + c_F)`:
**4.86 bps** (large fund) / **10.44 bps** (small fund) / **16.38 bps** (retail tier). Spread cost on top,
from Binance's own trade records (§4.4): median daily **effective** perp spread **0.11 bps (BTC)**,
0.18 (ETH), 0.44 (BNB), 1.35 (DOGE), 2.12 (ADA); **5.95 bps on BTC during the 2020-03-12 crash**.
Zhivkov (2026, *Mathematics* 14(2):346) independently models **0.6%** round trip including 0.1%
slippage. The repo's 0.30% taker-based figure is defensible as a **base**; it needs a **stress**
counterpart, and price impact above ~$10k notional remains **unmeasured by anyone**.

### Negative findings (recorded, not papered over)

- **No author named "Shamshuddeen" exists** in arXiv, OpenAlex, Crossref, RePEc or general web
  search, and the "Poucet + Pauna" pairing returns nothing. Reported as-is; no near-miss substituted.
  The genuine prior art is listed in the review.
- **"The Crypto Carry Trade" (Christin, Routledge, Soska, Zetlin-Jones, 2022)** is the closest prior
  art to this strategy and is **located but not retrieved** (host timeouts). Its numbers are the most
  important missing input.
- **No published study decomposes a funding book's realised P&L into service fee vs risk premium**, and
  none estimates its ruin probability. No clean peer-reviewed spot+perp Binance study exists for
  2024–2026; the best Binance-specific evidence (He et al. Table 6) is a preprint.

### Verdict

Unchanged: **carry is off, and the multi-window monitor is right to keep it off.** The 30-day reading
of +4.75%/yr is a **spike signature**, not a regime — 90/180/365d read +2.56/+0.60/−0.58. An earlier
message of mine read the 30-day number as "the switch is near flipping"; that was too eager and the
monitor's disagreement rule is the correct call. The literature makes the off verdict *stronger*:
the carry is mostly a financing charge that averages to roughly zero in excess of Binance's own
parameter, it has been compressed ~90%, it is one common factor rather than 20 independent streams,
and the best peer-reviewed replication of it lost 33.6% on one symbol.
"""

ROW = (
    "| 2026-09-26 | **External literature + exchange-documentation review "
    "(`docs-myself/CARRY_LIT_REVIEW_2026-09-26.md`).** Confirms the mechanism, the §3.14 diagnosis and "
    "the §4 funding correlation from outside the repo; corrects two things. **Confirms:** the sign "
    "convention is the *documented* Binance rule; the ~90% decay reproduces He et al.'s \"almost 80%\" "
    "and is corroborated by Crépellière-Pelster-Zeisberger (JFM 2023) and Shynkevich (JEF 2023); "
    "funding correlation 0.447 (changes) / 0.627 (levels) re-measured, **PC1 = 49%**, so 20 names buy a "
    "**1.45x** vol reduction not 4.5x; He et al. Table B.1 independently gives 41.7–50.4% of settlements "
    "at exactly the interest component and a 47–82% SD reduction from the clamp. **Corrects in the "
    "repo's favour:** my early claim that the 8h interval had changed for this universe is **retracted** "
    "— corpus is 8h throughout (479 common timestamps vs live stream, max abs diff 0.00000000); the "
    "interval is still administered silently (2025-05-02 1h trigger, 2026-01-02 revert to **4h not 8h**, "
    "no announcement), so read `fundingIntervalHours` per run. **Corrects in the repo's disfavour:** "
    "§3.14's share is **36.6%** not 43%; the sharper result is EW total +9.40%/yr vs EW fixed component "
    "10.95%/yr ⇒ **excess −1.55%/yr**, BTC +0.20%, **negative for 9 of 20**, and **BNB is at exactly "
    "0.0001 on 0.00% of settlements** (confirming BNBUSDT's iota = 0) while being the *worst* symbol. "
    "Also new: the funding **cap binds in the tail** (BTC ±0.3000% exactly, SOL −2.0000% exactly); "
    "funding is **forfeited on early close** (no accrual) and **debited against position margin** "
    "(moves the liquidation price). **Strongest bear-case datum is measured, not theoretical:** He et "
    "al. Table 6 replicate this exact strategy on Binance — BNB −5.14%/yr, SR −0.66, **maxDD "
    "−33.61%**, alpha −7.13 (t = −2.21) — and `tools/carry/REPORT.md` reports no drawdown for carry at "
    "all. **Negative findings recorded:** no author \"Shamshuddeen\" exists in any index; the Christin et "
    "al. carry-trade numbers could not be retrieved; no published service-vs-risk-premium decomposition "
    "or ruin-probability estimate exists. Verdict unchanged: **off** — and the multi-window monitor is "
    "right to keep it off, since +4.75% at 30d against −0.58% at 365d is a spike, not a regime. |\n"
)


def main():
    txt = P.read_text(encoding="utf-8")
    if MARKER in txt:
        print("already appended; nothing to do")
        return
    before = len(txt)
    with P.open("a", encoding="utf-8") as f:
        f.write(SECTION)
        f.write("\n| date | change |\n|---|---|\n")
        f.write(ROW)
    print(f"appended {len(P.read_text(encoding='utf-8')) - before} chars to {P}")


if __name__ == "__main__":
    main()
