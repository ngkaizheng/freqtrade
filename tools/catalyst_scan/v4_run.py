"""v4 candidate set + ranking run.

The seven dimension scores and the evidence class are the authored judgments;
every derived number (raw, final, normalized, status, gate outcome) is computed
by `v4_score.py` and re-checked by `verify_v4.py`. Each candidate carries the
written justification v4 section 82 requires, so a score is never just a number.

Dimension reference (v4 s55-s61), abbreviated in the notes below as
  G = Information Gap   F = Fundamental/Token Capture   C = Catalyst
  A = Attention         L = Liquidity                   S = Supply
  R = Reflexivity

ATTENTION CAP: v4 s58 score 4 requires several attention metrics rising in
sync (mentions / engagement / search / volume / holders). With free data sources
only the VOLUME leg is verifiable - X mentions, Google Trends and holder counts
are all behind paid or blocked APIs. So Score A is capped at
`v4_evidence.ATTENTION_SCORE_CAP` unless a coin is independently corroborated
as a CoinGecko-trending or dated-media name. The cap is asserted below, not left
to judgement.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from v4_evidence import ATTENTION_SCORE_CAP  # noqa: E402
from v4_score import Candidate, score_table  # noqa: E402

# Market regime factor (v4 s65, range 0.90-1.10).
#
# MEASURED, not assumed (CoinGecko /global + local universe snapshot,
# 2026-09-28T19:30-20:0xZ; out/regime.md):
#   total market cap $2.875T, 24h volume $155.5B, 24h change -3.31%
#   BTC dominance 58.27%, ETH dominance 11.37%
#   BTC $83,869  7D -2.17%  30D +7.59%  -33.5% from ATH
#   ETH $2,693   7D -1.61%  30D +10.13% -45.6% from ATH ; ETH/BTC 0.03211 (+2.4% 30D)
#   top 200: median 30D +16.8%, 78% up, median -73.9% from ATH, 25.5% within 25%
#   top 1000: median 30D +9.0%, 69.7% up, median -84.6% from ATH
#
# Reading: a broad alt bounce INSIDE a deep bear market that is currently
# rolling over - four of five majors are negative on 7D and total market cap
# fell 3.31% in the last 24h. Two forces pull opposite ways, and they roughly
# cancel: risk-off compresses alt multiples, but the v3 round's own finding is
# that this tape pays for CASH FLOW and not for narrative, which is exactly
# what every surviving candidate here is selling. Hence NEUTRAL rather than a
# punitive 0.95.
#
# HONEST CAVEAT, and it is load-bearing: at regime 0.95 the entire surviving
# result disappears - AVA falls 56.10 -> 53.30 and the field is empty. The
# headline therefore depends on a judgement call that the data does not settle.
# See sensitivity.py axis 5.
REGIME_FACTOR = 1.00
REGIME_LABEL = ("MIXED, downside tilt: broad alt bounce inside a deep bear market, "
                "rolling over (24h mcap -3.31%, BTC dominance 58.27%, 4/5 majors "
                "negative on 7D); pays for cash flow, not narrative")

# Corroborated attention names: on CoinGecko trending at 2026-09-28T20:0xZ
# (out/trending.txt). Only these may exceed the attention cap.
# NOTE: this is not decorative. The cap assertion in main() fired on PONS when
# it was first omitted, which is the check doing its job.
ATTENTION_CORROBORATED: set[str] = {"PONS"}

CANDIDATES: list[Candidate] = [
    # ---------------------------------------------------- KNTQ (v3's only Deep DD)
    Candidate(
        token="KNTQ", archetype="F",
        scores={"G": 4, "F": 4, "C": 3, "A": 2, "L": 3, "S": 2, "R": 3},
        evidence="C",
        notes=(
            "G4 - the unpriced variable is Elysium sequencer revenue $/day, which "
            "is quantifiable, testable at T+0 and material (50% of it is bought on "
            "the open market). Not 5: no consensus expectation number exists to "
            "compare against, and +62.1% 30D means the announcement leg IS priced. | "
            "F4 - capture is verified on-chain (KIP-5: 5,391,458 KNTQ at $0.15 avg "
            "= $808,719 over 5 months => 12.9M/yr = $3.97M/yr = 4.6% of cap), with "
            "KIP-2 adding 70% of protocol revenue + 100% of validator commission. "
            "Not 5: not large, and the buyback retires only 1.8% of the 719M still "
            "to be issued. | "
            "C3 - testnet live 2026-09-22, mainnet verbally confirmed for end-Oct, "
            "but the project has NEVER published a mainnet date (verified by "
            "primary-source absence of any such post). Official event, window not "
            "a hard date => 3, not 4. | "
            "A2 - 30D +62.1% but 7D -3.7%; the narrative is known and currently "
            "decelerating. Social velocity unverifiable => capped. | "
            "L3 - $2.37M/24h on $86.1M cap (2.75%) is ample for $500; DEX liquidity "
            "only ~$1.2M, so not 4. | "
            "S2 - FDV/MC 3.57, 719M unissued, plus the 2026-10-01 kPoints airdrop "
            "landing immediately before the catalyst. | "
            "R3 - genuine Hyperliquid-ecosystem reflexivity, but $86M cap on thin "
            "DEX depth. | "
            "EV C - the running buyback is L1 on-chain, but the catalyst date is L4 "
            "and the sequencer revenue is a future unknown."
        ),
    ),
    # ---------------------------------------------------------------- AVA
    Candidate(
        token="AVA", archetype="A",
        scores={"G": 4, "F": 4, "C": 3, "A": 2, "L": 3, "S": 3, "R": 2},
        evidence="C",
        notes=(
            "G4 - at -96.3% from ATH with 7D flat (-0.1%) and 30D +19.9%, the "
            "market is not pricing a permanent buyback at all. The unknown is "
            "quantifiable (monthly settlement size) and material as a yield "
            "(6-12% of cap). | "
            "F4 - PRIMARY SOURCE: Travala's own blog 2026-09-23 announces a "
            "PERMANENT Strategic Reserve: the Foundation buys back AVA equal to the "
            "prior month's member givebacks and Travala INDEPENDENTLY MATCHES it, "
            "with a commitment never to sell or transfer. Direct + recurring + "
            "scalable. Not 5: ~$89-177K/month is small in absolute terms. | "
            "C3 - recurring monthly from 2026-09-23; no discrete hard date, but a "
            "settled, dated, ongoing program. | "
            "A2 - 30D +19.9% but 7D -0.1%; flat, not accelerating. | "
            "L3 - $9.50M/24h on a $17.8M cap is 53% turnover, ample for $500, but "
            "turnover is not depth. | "
            "S3 - 74.37M/74.37M circulating, FDV/MC 1.00, no unlock. Better than "
            "most, because the reserve is permanent rather than re-deployable. | "
            "R2 - travel-booking adoption, not a reflexive narrative. | "
            "EV C - official announcement plus a reported first settlement; no "
            "on-chain transaction hash verified."
        ),
    ),
    # ------------------------------------------------------------- SYRUP
    Candidate(
        token="SYRUP", archetype="A",
        scores={"G": 4, "F": 3, "C": 2, "A": 1, "L": 3, "S": 3, "R": 2},
        evidence="B",
        notes=(
            "G4 - the tier is a step function on monthly net revenue (>$2.0M/mo "
            "jumps the buyback from 20% to 30%), so a small revenue move causes a "
            "disproportionate capture change. Quantifiable, testable, material "
            "(8.5x on the measured run-rate). 7D -5.4% while the sector rallied "
            "25-70% => genuinely un-owned. | "
            "F3 - MIP-021 passed 99.97% and buybacks began August 2026; measured "
            "$147K/month. Real but currently immaterial. | "
            "C2 - revenue-triggered, not date-triggered; the six-month term that "
            "would expire ~2027-01 is OUTSIDE the 30-90d window and is itself "
            "UNVERIFIED. | "
            "A1 - lowest attention in the set; 7D -5.4% against a rising tape. | "
            "L3 - $10.90M/24h on $253.8M = 4.3%; fine for $500, thin above. | "
            "S3 - 1.167B/1.245B, FDV/MC 1.07, no cliff; but purchased SYRUP goes "
            "to a strategic fund, NOT burned, so it is treasury capital. | "
            "R2 - credit book, not a reflexive loop. | "
            "EV B - governance result is on-chain and the buyback is measured."
        ),
    ),
    # ---------------------------------------------------------------- LDO
    Candidate(
        token="LDO", archetype="A",
        scores={"G": 3, "F": 3, "C": 2, "A": 2, "L": 4, "S": 4, "R": 2},
        evidence="C",
        notes=(
            "G3 - a clear testable unknown (does the Aragon execution happen, and "
            "does the cash flow persist) but the increment is small: the triggered "
            "buyback is ~$7.9M/yr = 2.13% of cap. Not 4/5 because the gap does not "
            "change the valuation arithmetic. | "
            "F3 - NEST is live but has executed ZERO buybacks to date (revenue ran "
            "below the old $40M trigger). Capture is designed and approved, not "
            "yet demonstrated. | "
            "C2 - Snapshot passed 2026-09-24, but the Aragon on-chain execution "
            "date is unconfirmed. | "
            "A2 - 30D +21.4%, 7D +1.9%; mild. | "
            "L4 - $73.82M/24h on $365.5M = 20.2%, deep. | "
            "S4 - 829.6M/1.0B, FDV/MC 1.21, no cliff unlock; the least supply risk "
            "in the set. | "
            "R2 - mature governance token. | "
            "EV C - the vote is on-chain; the execution date and the durability of "
            "the $27M/yr holders-revenue line are not independently confirmed."
        ),
    ),
    # --------------------------------------------------------------- AERO
    Candidate(
        token="AERO", archetype="A",
        scores={"G": 3, "F": 3, "C": 3, "A": 3, "L": 4, "S": 2, "R": 3},
        evidence="B",
        notes=(
            "G3 - the merge itself is known (+66.1% 30D). The genuine unknown is "
            "whether the AER Engine actually converts ~17%/yr dilution into "
            "revenue-linked issuance - but that parameter is UNPUBLISHED, so the "
            "gap is real yet not quantifiable in advance. | "
            "F3 - sAERO exchange-revenue share is real and verified, but the "
            "revenue line is down ~78% from its 2024Q4 peak, so there is no growth "
            "headroom to score 4. | "
            "C3 - the date is the strongest in the whole set: 2026-10-21, PRIMARY "
            "SOURCE (aero.xyz launch update 2026-09-25), confirmed by press. Held "
            "at 3, not 4, because s57 requires the economic impact to be clear and "
            "the AER Engine cap parameters are not published. | "
            "A3 - 30D +66.1%, 7D +20.5%; attention clearly rising. | "
            "L4 - $85.70M/24h on $815.2M = 10.5%, deep. OI/funding unverified so "
            "not 5. | "
            "S2 - measured supply growth ~+17%/yr against ~$100M/yr of exchange "
            "revenue (12.2% of cap): net supply is still inflationary. | "
            "R3 - Base/Aerodrome seven-chain launch is real ecosystem reflexivity. | "
            "EV B - official article plus a secondary press confirmation; revenue "
            "figures are protocol accounting with a known DefiLlama-bribe caveat."
        ),
    ),
    # ---------------------------------------------------------------- ENA
    Candidate(
        token="ENA", archetype="B",
        scores={"G": 2, "F": 3, "C": 2, "A": 3, "L": 4, "S": 1, "R": 4},
        evidence="C",
        notes=(
            "G2 - the market has ALREADY repriced (+66.8% 30D, +23.3% 7D) and the "
            "catalyst's own economics are too small to justify more: the first fee "
            "tier is ~0.33-0.65% of a $2.62B cap. | "
            "F3 - the fee switch is approved and the capture is genuine, just tiny. | "
            "C2 - a trigger, not a date: 5% arms at a $7.5B 14-day USDe average, "
            "which requires an assumption about supply growth velocity. | "
            "A3 - 30D +66.8%, 7D +23.3%; attention clearly rising. | "
            "L4 - $630.5M/24h on $2.62B = 24.1%, very deep. | "
            "S1 - ~1.5B ENA (~14.3% of float) released on 2026-10-05, inside the "
            "window, plus ongoing emissions. | "
            "R4 - synthetic-dollar is one of the strongest live narratives. | "
            "EV C - the vote is on-chain; the tier economics are a third-party "
            "backtest (L3) and the trigger date is a velocity assumption."
        ),
    ),
    # ---------------------------------------------------------------- ZRO
    Candidate(
        token="ZRO", archetype="B",
        scores={"G": 2, "F": 2, "C": 2, "A": 3, "L": 4, "S": 2, "R": 3},
        evidence="C",
        notes=(
            "G2 - 7D +30.7% means the market is already betting on the fee switch, "
            "and even a pass adds ~$2.29M/yr = 0.41% of a $545M cap. | "
            "F2 - a fee switch that has not yet converted a meaningful cash flow. | "
            "C2 - the ~2026-12-20 vote date is INFERRED from a biannual cadence, "
            "and the project has a 0-for-4 record on reaching quorum. | "
            "A3 - 30D +41.8%, 7D +30.7%; rising. | "
            "L4 - $117.6M/24h on $545.4M = 21.6%, deep. | "
            "S2 - 353.3M/1.0B, FDV/MC 2.83; 2.8x overhang. | "
            "R3 - LayerZero is a major infrastructure narrative. | "
            "EV C - inferred date, no published vote calendar confirmed."
        ),
    ),
    # -------------------------------------------------------------- SUSHI
    Candidate(
        token="SUSHI", archetype="A",
        scores={"G": 2, "F": 2, "C": 3, "A": 2, "L": 4, "S": 5, "R": 2},
        evidence="C",
        notes=(
            "G2 - 2026-10-01 monthly xSUSHI buyback start is a hard date, but the "
            "cash flow it spends is $73K/yr = 0.10% of cap, so the outcome cannot "
            "change the valuation. Textbook: nothing is mispriced because nothing "
            "is material. | "
            "F2 - buyback mechanism exists, scale is negligible. | "
            "C3 - 2026-10-01 is the one genuinely hard date in this tier. | "
            "A2 - 30D +31.8%, 7D -2.2%. | "
            "L4 - $9.34M/24h on $71.5M = 13.1%. | "
            "S5 - 286.7M/291.5M, FDV/MC 1.02, effectively fully circulating: the "
            "best supply structure in the set. | "
            "R2 - mature brand, no reflexivity. | "
            "EV C - announced program, small absolute amounts."
        ),
    ),
    # ---------------------------------------------------------------- VSN
    Candidate(
        token="VSN", archetype="A",
        scores={"G": 2, "F": 3, "C": 2, "A": 1, "L": 2, "S": 3, "R": 1},
        evidence="C",
        notes=(
            "G2 - a EUR 2.0M first-ever foundation buyback is 1.3% of a $167M cap, "
            "and the purchased tokens go to the treasury, NOT burned. | "
            "F3 - real, executed, first-ever, but immaterial. | "
            "C2 - a 2026-09-01 to 12-31 program window, not a discrete event. | "
            "A1 - 7D -0.1%. | "
            "L2 - $1.91M/24h on $167.0M = 1.14% and FALLING (was 1.55% in the v3 "
            "round). Usable for $500 with visible impact beyond that. | "
            "S3 - 3.79B/4.2B, FDV/MC 1.11, no cliff. | "
            "R1 - none. | "
            "EV C - project-reported, not on-chain verified."
        ),
    ),
    # ---------------------------------------------------------------- ORE
    Candidate(
        token="ORE", archetype="A",
        scores={"G": 1, "F": 3, "C": 0, "A": 1, "L": 2, "S": 0, "R": 1},
        evidence="C",
        notes=(
            "G1 - the 70%-of-cap cash flow is public knowledge, is a FLOW not a "
            "CATALYST, and is falling: 30D revenue -18.5%, 7D worse. | "
            "F3 - 99% of fees route to buyback, but 90% of it is BURIED and "
            "reissuable, so it is not a permanent claim. | "
            "C0 - no catalyst at all; this is a continuous program. | "
            "A1 - 7D +8.8% on 24h volume of only 2.5% of cap. | "
            "L2 - $1.02M/24h on a $41.2M cap, DEX depth only ~$838K. | "
            "S0 - CoinGecko's FDV equals market cap ONLY because it computes FDV off "
            "the 498K total supply, while the real cap is 3M: the true diluted value "
            "is ~6x the displayed number, and the buyback is reissuable. | "
            "R1 - none. | "
            "EV C - protocol-reported weekly figures."
        ),
    ),
    # ------------------------------------------- Data Insufficient (v4 s51)
    Candidate(
        token="BTT", archetype="A",
        scores={"G": 0, "F": 0, "C": 2, "A": 2, "L": 3, "S": 3, "R": 2},
        evidence="D",
        data_ok=False,
        data_note=(
            "s51 FAIL - a first 100%-of-revenue burn is announced for mid-October "
            "2026, but NO official revenue figure has ever been published and "
            "DefiLlama has no BitTorrent page (404), so burn-USD / market cap "
            "cannot be computed in advance. The mechanism is a third-party paid "
            "press release (CryptoSlate, 'TRON Eco Team' byline, 2026-08-17). "
            "Buying this means buying an unquantifiable number."
        ),
    ),
    Candidate(
        token="WIN", archetype="A",
        scores={"G": 0, "F": 0, "C": 2, "A": 2, "L": 3, "S": 3, "R": 1},
        evidence="D",
        data_ok=False,
        data_note=(
            "s51 FAIL - identical structure and identical gap to BTT: a first "
            "100%-of-oracle-revenue burn announced for October 2026 with no "
            "published revenue figure and no DefiLlama page (404). The smaller cap "
            "makes burn/market-cap larger IF the revenue exists, which is exactly "
            "the unverified part."
        ),
    ),
    # ------------------------------------------------- Priced In (v4 s69)
    Candidate(
        token="STONK", archetype="E",
        scores={"G": 1, "F": 3, "C": 0, "A": 2, "L": 4, "S": 4, "R": 4},
        evidence="C",
        override="Priced In",
        override_reason=(
            "s69 - catalyst realized, market already rerated (+1253% 30D), G<=2. "
            "And it is now BREAKING: 7D -36.2%, -37.8% from the 2026-09-21 ATH, "
            "with 7D revenue -48%. A 72%-of-cap annualised buyback yield on "
            "halving weekly revenue is a value trap in motion, not an opportunity."
        ),
    ),
    Candidate(
        token="PONS", archetype="E",
        scores={"G": 1, "F": 3, "C": 0, "A": 4, "L": 4, "S": 4, "R": 4},
        evidence="C",
        override="Priced In",
        override_reason=(
            "s69 - the ~30% burn completed around 2026-09-05, +141.9% 30D, and the "
            "token is -45.1% off its 2026-09-05 ATH with 7D -8.9%. It is the most "
            "SELL-THE-NEWS case in the set: it is currently on CoinGecko TRENDING "
            "while rolling over, and the project's own position is that future "
            "buybacks are not guaranteed. Attention is maximal and decelerating."
        ),
    ),
    Candidate(
        token="HYPE", archetype="A",
        scores={"G": 1, "F": 4, "C": 3, "A": 2, "L": 5, "S": 1, "R": 4},
        evidence="B",
        override="Priced In",
        override_reason=(
            "s69 - 3.24%-of-cap buyback-and-burn is real, but the ATH was "
            "2026-09-23 (only -10.9% below it), 30D revenue is -47%, and FDV/MC is "
            "4.29. The market has already paid for the mechanism."
        ),
    ),
    Candidate(
        token="UNI", archetype="E",
        scores={"G": 1, "F": 3, "C": 3, "A": 2, "L": 5, "S": 2, "R": 3},
        evidence="B",
        override="Priced In",
        override_reason=(
            "s69 - +87.8% 30D, and the 7D has gone completely flat (+0.14%). The "
            "Arc burn is ~$188M/yr but is offset by a 20M UNI/yr growth budget, so "
            "net deflation is only ~+0.2%. A 2x re-rate with no net supply change."
        ),
    ),
    # ------------------------------------------------- Supply shock (v4 s52)
    Candidate(
        token="MON", archetype="D",
        scores={"G": 1, "F": 1, "C": 1, "A": 3, "L": 4, "S": 0, "R": 4},
        evidence="C",
        veto=("VETO-5", "88.9B of 100.7B total supply is still unissued against "
                        "11.8B circulating; the ~2026-11-24 unlock is ~750% of "
                        "current float, far past the s52 100%-of-circulating / "
                        "90-day limit, with no absorption mechanism identified"),
    ),
    Candidate(
        token="2Z", archetype="B",
        scores={"G": 1, "F": 1, "C": 1, "A": 3, "L": 2, "S": 1, "R": 2},
        evidence="C",
        notes=(
            "Scored rather than vetoed: 47.7% of float on 2026-10-02 sits just "
            "UNDER the s52 50% line, so VETO-5 does not fire on the letter of the "
            "rule. It would if the unlock were 2.3% larger. No dated value-capture "
            "event identified in the window; FDV/MC 2.88; turnover 8.1%. G1 => "
            "fails s67 Rule B."
        ),
    ),
    Candidate(
        token="LIT", archetype="A",
        scores={"G": 1, "F": 2, "C": 1, "A": 2, "L": 3, "S": 1, "R": 3},
        evidence="C",
        notes=(
            "Perp DEX at $1.12B cap, FDV/MC 4.00 (250M of 1B circulating), 7D "
            "-6.3% against 30D +28.0% - momentum fading, no dated value-capture "
            "event identified. G1 => fails s67 Rule B."
        ),
    ),
    Candidate(
        token="ONDO", archetype="A",
        scores={"G": 2, "F": 3, "C": 2, "A": 3, "L": 4, "S": 2, "R": 3},
        evidence="C",
        notes=(
            "The RWA leader has already rerated +44.6% 30D with no dated "
            "value-capture event identified inside the window, and its 35.2% unlock "
            "lands 2027-01-17, just outside it. F3 - fee share and buyback are real. "
            "G2 => fails s67 Rule B."
        ),
    ),
    Candidate(
        token="IMX", archetype="A",
        scores={"G": 2, "F": 3, "C": 1, "A": 3, "L": 3, "S": 2, "R": 2},
        evidence="C",
        notes=(
            "Genuine tokenomics turnaround (real buybacks) and a deep -98.2% draw, "
            "but +31.4% 30D has already started the re-rate and NO dated catalyst "
            "was identified in the 30-90d window. C1 - nothing scheduled. G2 => "
            "fails s67 Rule B."
        ),
    ),

    # ====================================================================
    # ATTENTION / MOMENTUM COHORT (archetypes C and D).
    #
    # This block exists because the v3 round could not produce these at all:
    # its screen ranked protocols by holders-revenue / market cap off DefiLlama,
    # which structurally excludes anything without a published token-capture
    # line. Scoring a universe that was pre-filtered against two of v4's six
    # archetypes would be scoring a biased sample.
    #
    # Result: 1 of 11 had a dated, project-published, in-window event, and it
    # was already public a week before the screen ran. The cohort is eliminated
    # on s67 Rule B (Information Gap), not on liquidity.
    # ====================================================================
    Candidate(
        token="RUNE", archetype="A",
        scores={"G": 1, "F": 1, "C": 0, "A": 3, "L": 4, "S": 3, "R": 2},
        evidence="B",
        notes=(
            "The most liquid name in the cohort ($254.9M/24h = 1.00x turnover) and "
            "the tightest supply structure (FDV/MC 1.08, ~25% of float bonded). | "
            "G1 - NO dated event anywhere in the window; the only tokenomics news "
            "is a CUT. | "
            "F1 - THORChain's own 2026-09-23 post REDUCED the RUNE burn from 5% to "
            "1% of System Income, moving 20% to Protocol-Owned Liquidity (RUNE "
            "redeployed into pools, not returned or burned). Measured burn "
            "1,000-4,500 RUNE/day => ~$1.1M/yr = 0.45% of cap. | "
            "C0 - nothing scheduled. | "
            "A3 - +68% 30D on very high turnover, corroborated. | "
            "S3 - best float structure in the cohort, but the burn cut is "
            "directionally negative. | "
            "Bear overlay: Aug swap volume -23% to $613M, System income -23% to "
            "$615K, a third network halt (Aug 26-27) and a confirmed $10.7M "
            "exploit (2026-05-15). The +68% is running against deteriorating "
            "fundamentals. | G1 => fails s67 Rule B."
        ),
    ),
    Candidate(
        token="MARSCOIN", archetype="D",
        scores={"G": 1, "F": 0, "C": 0, "A": 3, "L": 2, "S": 3, "R": 4},
        evidence="B",
        notes=(
            "IDENTITY ERROR IN MY OWN SCREEN, corrected here: the screen labelled "
            "this 'MARSCOIN / Mars Protocol'. It is NOT Mars Protocol. It is "
            "CoinGecko id `marscoin-4`, a BNB Chain meme token, Seed-Tag listed on "
            "Binance 2026-09-04 with a 20x perp launched 2026-09-01 - i.e. "
            "derivatives BEFORE spot. It is unrelated to Mars Protocol (Cosmos, "
            "~$130K TVL) and to marscoin.org (a 2014 Bitcoin merge-mining coin). | "
            "G1 - the only catalyst is the Binance listing, which happened "
            "2026-09-04, THREE AND A HALF WEEKS BEFORE the window opens, and is "
            "fully contained in the +236% print. | "
            "F0 - no fee share, no buyback, no burn. | C0 - nothing in window. | "
            "A3 - +236% 30D, but the attention is exchange-promoted (Seed Tag = "
            "paid marketing), so v4 s58's 'not pure bot/paid promotion' condition "
            "for a 5 is not met. | "
            "L2 - $131.0M/24h against a $157.7M cap is >80% turnover with reported "
            "liquidity 'only a small fraction of market cap', during a 20x-perp "
            "week. That is leverage, not depth - precisely the s59 Volume != "
            "Liquidity warning. | "
            "S3 - 1.000B/1.000B fully circulating, FDV/MC 1.00: no overhang, and "
            "equally no supply mechanism. | "
            "R4 - a textbook reflexive loop, and the only archetype-D case in the "
            "cohort. | G1 => fails s67 Rule B."
        ),
    ),
    Candidate(
        token="GRT", archetype="B",
        scores={"G": 1, "F": 1, "C": 3, "A": 3, "L": 4, "S": 1, "R": 3},
        evidence="B",
        notes=(
            "The ONLY name in the 11 with a dated, project-published, in-window "
            "event: Subgraph Studio traffic migrates to The Graph Network on "
            "2026-10-08 (BNB Chain and Polygon first), per thegraph.com's own "
            "blog of 2026-09-26. | "
            "G1 - AND THAT IS WHY IT FAILS: the date was already reported by "
            "aggregators (TradersUnion, blockchain.news, TradingView, CMC AI) on "
            "2026-09-25 to 09-27, i.e. BEFORE the screen ran. A known dated event "
            "is not an information gap. | "
            "F1 - there is NO buyback and NO burn. The token is INFLATIONARY at "
            "~2.9%/yr (120.73 GRT/block, no max supply), and GIP-0089 - live "
            "2026-09-01 - redirected 20% of issuance (24.146 GRT/block, ~317M "
            "GRT/yr) to a Foundation-managed multisig. Token capture here is "
            "directionally NEGATIVE: it is new sell-side supply. | "
            "C3 - hard date, primary-confirmed, but the economic impact of a "
            "Studio migration is not a measurable cash-flow change. | "
            "A3 - +83% 30D but already -8.7% in 24h. | "
            "L4 - $118.2M/24h on $333.2M = 0.39. | "
            "S1 - the dominant supply fact: 2.9%/yr inflation plus a fresh "
            "20%-of-issuance Foundation redirect, with no max supply. | "
            "R3 - major infrastructure narrative. | G1 => fails s67 Rule B."
        ),
    ),
    Candidate(
        token="SEI", archetype="B",
        scores={"G": 1, "F": 1, "C": 1, "A": 3, "L": 4, "S": 1, "R": 4},
        evidence="B",
        notes=(
            "The +67% was an ETF FILING, not an event: Canary Capital filed "
            "Pre-Effective Amendment No. 2 to Form S-1 for a staked SEI ETF on "
            "2026-09-21 (BitGo custodian, Cboe BZX expected venue). | "
            "G1 - there is NO scheduled SEC decision date, and S-1 effectiveness "
            "is not on a fixed calendar. An undated catalyst cannot be scored as "
            "an in-window event. | "
            "F1 - no buyback, no burn, no fee switch; staking is a yield mechanism, "
            "not token-level cash flow. | "
            "C1 - the Giga 'Autobahn' consensus component is repeatedly called "
            "'next' with NO published date; the 'rolling out on mainnet' framing "
            "traces to an aggregator (earncrypto.dev, 2026-09-13), L4. | "
            "A3 - +67% 30D. | L4 - $237.7M/24h on $517.7M = 0.46. | "
            "S1 - and here the DATED in-window events are BEARISH: recurring "
            "monthly unlocks of 113.0M SEI (~$5.53M) on 2026-10-15 and "
            "2026-11-15, ~87% to private investors and insiders, against 6.733B of "
            "10.0B circulating (FDV/MC 1.49). | "
            "R4 - the ETF narrative is the strongest reflexivity in the cohort. | "
            "G1 => fails s67 Rule B."
        ),
    ),
    Candidate(
        token="RHEA", archetype="A",
        scores={"G": 2, "F": 3, "C": 0, "A": 3, "L": 3, "S": 1, "R": 2},
        evidence="C",
        notes=(
            "IDENTITY AMBIGUOUS, flagged rather than silently resolved: the screen's "
            "asset is CoinGecko `rhea-2` = Rhea Finance, the NEAR lending/RWA "
            "protocol (Rhea Lend $197.6M TVL, Rhea LST $43.4M, Rhea Dex $28.9M). A "
            "different 'Rhea' (rhea.run) documents a token launched on Robinhood "
            "Chain. They must not be conflated. | "
            "G2 - the only genuinely EXECUTED buyback in the cohort: the project's "
            "own account states 17,750,000 RHEA bought back since 2025-07-30, "
            "~30-40% of protocol revenue. But that is a ~$250K cumulative figure "
            "on a $46.4M cap (= 0.5%), last verifiable around 2026-07-02, with no "
            "more recent execution found. | "
            "F3 - a high capture RATE, a trivial capture AMOUNT. This is the same "
            "as AVA and the distinction matters. | C0 - nothing in window. | "
            "A3 - +822% 30D, +180% 7D, but -30.4% in 24h: a violent unwind in "
            "real time, and the screen's own figures were already stale. | "
            "L3 - $13.3M/24h on a $46.4M cap = 0.26. | "
            "S1 - 412.19M of 999.2M circulating, FDV/MC 2.42, and NO dated unlock "
            "table could be found. | G2 => fails s67 Rule B."
        ),
    ),
    Candidate(
        token="NEON", archetype="D",
        scores={"G": 0, "F": 0, "C": 0, "A": 2, "L": 1, "S": 2, "R": 3},
        evidence="D",
        notes=(
            "The +152% 30D on a $16.5M cap is not a repricing. 24h volume is "
            "$1.47M and the token is -17.6% in 24h and -99.0% from its ATH. | "
            "G0 - no dated in-window event of any kind; the only named item (a "
            "Revolut listing) is from 2025. | F0 - no capture. | C0 - none. | "
            "L1 - $1.47M/24h on a $16.5M micro-cap is inside v4's s52 VETO-4 "
            "territory for a serious book; tolerated only because the position "
            "size in question is $500. | S2 - 431M of 1B, FDV/MC 2.32, the worst "
            "overhang in the cohort. | G0 => fails s67 Rule B."
        ),
    ),
]

# Tokens swept in the same pass and eliminated on the same rule. Kept in the
# published table so the coverage is visible rather than implied.
COHORT_SWEEPED_NO_EVENT = [
    ("XDC", "FDV/MC 1.91; turnover 0.06 - the thinnest real activity of the 11. "
            "Cancun upgrade was Feb 2026, before the window; the re-basing onto "
            "go-ethereum v1.17.3 is in progress with no date. CoinGecko-trending "
            "is attention, not a dated event."),
    ("GRASS", "No buyback found; dilution via pre-minted vault releases (~45.4M) "
              "against 699.49M of 1B circulating. A Season 2 package was announced "
              "~2026-07-08 by an aggregator, before the window. -8.9% in 24h "
              "against +57% 30d."),
    ("VIRTUAL", "Weakest momentum in the cohort (+14.8% 30d) - arguably a screen "
                "artifact. 658.39M of 1B circulating. No dated event found."),
    ("PLUME", "6.606B of 10B circulating. The 'met the SEC on onchain vault rules' "
              "item is aggregator-only (CMC AI, 2026-09-24), before the window, "
              "and not primary-confirmed."),
    ("SUPER", "CoinGecko names the asset 'SuperVerse' (id `superfarm`) - the same "
              "rebranding ambiguity as MARSCOIN. DefiLlama TVL $35,445 against a "
              "$122.5M cap, i.e. essentially no on-chain footprint. All roadmap "
              "material found was price-prediction SEO."),
]

PUBLISHED = score_table(CANDIDATES, REGIME_FACTOR)


def assert_attention_cap() -> None:
    """No candidate may exceed the cap unless independently corroborated."""
    for c in CANDIDATES:
        if c.scores["A"] > ATTENTION_SCORE_CAP and c.token not in ATTENTION_CORROBORATED:
            raise AssertionError(
                f"{c.token}: Attention {c.scores['A']} exceeds the verifiable-evidence "
                f"cap {ATTENTION_SCORE_CAP} without trending/media corroboration"
            )


def main() -> None:
    assert_attention_cap()
    out = Path(__file__).resolve().parent / "out"
    out.mkdir(parents=True, exist_ok=True)

    lines = [
        f"REGIME: {REGIME_LABEL} (factor {REGIME_FACTOR:.2f})",
        "",
        "| Token | Archetype | Raw | Final | Norm | G | F | C | A | L | S | R | "
        "Conf | Qualification | Status |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|",
    ]
    for r in PUBLISHED:
        s = r["scores"]
        lines.append(
            f"| {r['token']} | {r['archetype']} | {r['raw']:.2f} | "
            f"{r['final']:.2f} | {r['norm']:.2f} | "
            + " | ".join(str(s[d]) for d in ["G", "F", "C", "A", "L", "S", "R"])
            + f" | {r['evidence']} | {r['qualification']} | **{r['status']}** |"
        )
    md = "\n".join(lines)
    (out / "v4_ranking.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
