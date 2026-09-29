"""v4 sections 74-77: the 5x / 10x / 20x reality check, computed not typed.

v4 s74 forbids publishing "it could 10x" without stating what the world would
have to look like. This turns that into arithmetic:

    target MC x required yield = required annual token cash flow
    required growth            = required cash flow / current cash flow

and adds the check v4 does not ask for but the flow reality demands: what
fraction of DAILY TRADING VOLUME the buyback actually is. A "6% annualised
buyback yield" on a coin doing $285M/month of volume is $2,953/day of buying -
about 3 basis points of turnover. Yield and flow are different quantities, and
only the second one can move a price.

Writes out/reality_check.md.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
OUT = Path(__file__).resolve().parent / "out"

# token -> (current annual token cash flow USD, where that number comes from)
CASHFLOW = {
    "KNTQ": (3_970_000.0,
             "KIP-5 primary source: 5,391,458 KNTQ at $0.15 avg = $808,719 over "
             "5 months => 12.9M KNTQ/yr x $0.3070 = $3.97M/yr. Cross-checked by "
             "KIP-5's own '~13% APY on >33% of float staked' back-solving to "
             "12.0M/yr."),
    "AVA": (1_063_000.0,
            "369,881 AVA/month x $0.2395 = $88.6K/month = $1.063M/yr. NOTE: "
            "Travala's 2026-09-23 blog states the Foundation buys back an amount "
            "and Travala MATCHES it, so if 369,881 is the Foundation leg the "
            "true total is ~2x this. The split is UNVERIFIED; the lower number "
            "is used as the base case."),
}

YIELDS = [0.05, 0.10]
MULTIPLES = [2, 5, 10, 20]


def main() -> None:
    ev = pd.read_csv(OUT / "v4_evidence.csv").set_index("symbol")
    lines: list[str] = []

    for tok, (flow, prov) in CASHFLOW.items():
        mcap = float(ev.loc[tok, "mcap"])
        vol24 = float(ev.loc[tok, "vol24"])
        circ = float(ev.loc[tok, "circ"])
        total = float(ev.loc[tok, "total"]) if pd.notna(ev.loc[tok, "total"]) else None
        price = float(ev.loc[tok, "price"])

        lines.append(f"## {tok}  —  MC ${mcap/1e6:,.2f}M, "
                     f"current token cash flow ${flow/1e6:,.3f}M/yr "
                     f"({flow/mcap*100:.2f}% of cap)")
        lines.append(f"")
        lines.append(f"*Source of the cash-flow base:* {prov}")
        lines.append(f"")
        lines.append("| Target | Target MC | Required @5% | x current | "
                     "Required @10% | x current |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for mult in MULTIPLES:
            tgt = mcap * mult
            r5, r10 = tgt * 0.05, tgt * 0.10
            lines.append(
                f"| {mult}x | ${tgt/1e6:,.1f}M | ${r5/1e6:,.2f}M | "
                f"**{r5/flow:.2f}x** | ${r10/1e6:,.2f}M | **{r10/flow:.2f}x** |"
            )
        lines.append("")

        # ---- the flow reality check v4 does not ask for ---------------------
        daily_buy = flow / 365.0
        lines.append("**Flow reality check** (v4 does not ask for this; the "
                     "arithmetic demands it):")
        lines.append(f"")
        lines.append(f"- Current buyback = **${daily_buy:,.0f}/day**")
        lines.append(f"- 24h volume = ${vol24/1e6:,.2f}M  ->  the buyback is "
                     f"**{daily_buy/vol24*1e4:.1f} basis points of daily turnover**")
        for mult in (5, 10, 20):
            need5 = mcap * mult * 0.05 / 365.0
            # volume assumed to scale with market cap for the larger caps
            vol_scaled = vol24 * mult
            lines.append(
                f"- At {mult}x (5% yield) the buyback must reach "
                f"${need5:,.0f}/day = **{need5/vol_scaled*1e4:.1f} bps** of "
                f"volume assumed to scale pro-rata with cap"
            )
        lines.append("")

        if tok == "KNTQ":
            lines.append(
                "**Capture-rate translation (v4 s75, the 'required economic "
                "conditions' leg).** Only 50% of Elysium sequencer revenue is "
                "bought on the open market, so:")
            lines.append("")
            lines.append("| Target | Required incremental buyback | "
                         "=> required Elysium sequencer revenue | per day |")
            lines.append("|---|---:|---:|---:|")
            for mult in (2, 5, 10):
                need = mcap * mult * 0.05 - flow
                lines.append(
                    f"| {mult}x @5% | ${need/1e6:,.2f}M/yr | "
                    f"${need*2/1e6:,.2f}M/yr | **${need*2/365:,.0f}/day** |"
                )
            lines.append("")
            lines.append(
                "The 5x case therefore needs ~**$96K/day** of Elysium sequencer "
                "revenue. The confirmation bar set in the v3 round was $50K/day. "
                "So **5x requires roughly twice the threshold that would merely "
                "confirm the thesis** - on an L2 that would be about six weeks "
                "old at that point, whose parent ecosystem (Hyperliquid) already "
                "settles spot trades on its own mainnet. Verdict per v4 s76: "
                "**10x = unsupported by the fundamental route**; it would have to "
                "come from narrative and reflexivity, which is not what this "
                "score is measuring.")
            lines.append("")

        if total and circ and total > circ:
            unissued = total - circ
            lines.append("**Dilution overlay (v4 s52 / s60).**")
            lines.append("")
            lines.append(f"- Circulating {circ:,.0f} / total {total:,.0f} = "
                         f"**{total/circ:.2f}x FDV/MC**")
            lines.append(f"- {unissued:,.0f} tokens still unissued. The buyback "
                         f"retires {flow/price:,.0f}/yr = "
                         f"**{flow/price/unissued*100:.1f}% of the overhang per "
                         f"year**.")
            lines.append("")

    md = "\n".join(lines)
    (OUT / "reality_check.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
