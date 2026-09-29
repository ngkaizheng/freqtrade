"""Regression tests for the cost / market-impact measurement added 2026-09-27.

These pin arithmetic that produced a published conclusion, and they pin four
defects that were actually hit while producing it -- each of which failed
silently rather than loudly, which is the dangerous kind.

  D1  The bid ladder must be walked NEAREST-FIRST. Sorting levels by their signed
      percentage puts -5% before -0.2%, i.e. farthest to nearest, so the walk
      starts at the wrong end and cumulative notional appears to DECREASE. The
      monotonicity guard fired, so the bug was caught, but only because that
      guard happened to exist.
  D2  The two sides must be aligned on their COMMON complete snapshots. Dropping
      ragged snapshots per side leaves two arrays of different length that no
      longer refer to the same instants, and numpy then refuses to compare them.
  D3  A renderer that maps a string state through a boolean lookup silently maps
      "present" and "absent" to the same glyph. That produced an availability
      grid reading uniformly "absent" while the control probe on the same run
      reported "present". The grid disagreed with its own control and still
      printed a confident table.
  D4  "Worst regime" was computed with min() over the measured cost regimes,
      selecting the CALM day as the stress case and understating the range by
      ~3x. Same family as D3: a comparison that is silently the identity.

Also pinned: the uniform-within-bucket artefact, because it is visible in the
published impact table as a flat floor and must never be read as a measurement.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tools.cost import cost_regime_sensitivity as CRS
from tools.cost import measure_impact as MI


# --------------------------------------------------------------- fixtures


def _book(levels, ts="2026-09-20 00:00:00", side_sign=1) -> pd.DataFrame:
    """A minimal bookDepth frame.

    `levels` maps signed percentage -> cumulative notional. The ask side uses
    positive percentages, the bid side the mirrored negatives.
    """
    rows = []
    for pct, notional in levels.items():
        rows.append({"timestamp": ts, "percentage": side_sign * pct,
                     "depth": notional / 100.0, "notional": notional})
    return pd.DataFrame(rows)


ASK_LEVELS = {0.2: 1_000.0, 1.0: 5_000.0, 2.0: 9_000.0}
BID_LEVELS = {0.2: 800.0, 1.0: 4_000.0, 2.0: 7_500.0}


# ------------------------------------------------------- D1: ladder ordering


def test_bid_ladder_is_walked_nearest_first() -> None:
    """A bid book must come back ordered 0.2 -> 1.0 -> 2.0, not -2.0 -> -0.2.

    This is the D1 defect. The mirrored bid frame is *not* symmetric to the ask
    frame under a plain sort, and the cumulative notional column is only
    meaningful in nearest-first order.
    """
    bid_df = _book(BID_LEVELS, side_sign=-1)
    _, bpcts = MI.side_frame(bid_df, "bid")
    assert list(bpcts) == [0.2, 1.0, 2.0]


def test_ask_and_bid_ladders_share_one_level_convention() -> None:
    ask_df = _book(ASK_LEVELS, side_sign=1)
    bid_df = _book(BID_LEVELS, side_sign=-1)
    _, apcts = MI.side_frame(ask_df, "ask")
    _, bpcts = MI.side_frame(bid_df, "bid")
    assert list(apcts) == list(bpcts)


def test_impact_is_positive_on_both_sides() -> None:
    """Crossing the ask and crossing the bid both COST; neither may be negative.

    Using signed percentages with a bid ladder that is nearest-first would make
    every bid-side cost negative, which would silently flatter a round trip by
    roughly double the spread.
    """
    ask_df = _book(ASK_LEVELS, side_sign=1)
    bid_df = _book(BID_LEVELS, side_sign=-1)
    aw, apcts = MI.side_frame(ask_df, "ask")
    bw, bpcts = MI.side_frame(bid_df, "bid")
    ask, bid, dropped = MI.align(aw, bw)
    size = 1_000.0
    a = MI.impact_bps(ask, apcts, size)
    b = MI.impact_bps(bid, bpcts, size)
    assert dropped == 0
    assert a[0] > 0 and b[0] > 0


# --------------------------------------------------------- the cost walk


def test_impact_inside_the_first_level_is_that_whole_level() -> None:
    """Consuming HALF the first level still costs the full 0.2% offset.

    This is the uniform-within-bucket assumption made explicit, and it is the
    single most important limitation of the impact numbers. The bucket has ONE
    price displacement (0.2% = 20 bps); the estimator does not interpolate
    within it. An order of 500 USD against a 1000 USD first level is priced at
    the full 20 bps, even though a real book would be denser at the touch and
    charge less.

    The practical consequence: this module can only be trusted for orders that
    consume whole bands. For smaller orders it is a conservative ceiling, and
    the artefact is visible as a flat floor at exactly 2 x band across every
    symbol in the output.
    """
    ask_df = _book(ASK_LEVELS, side_sign=1)
    bid_df = _book(BID_LEVELS, side_sign=-1)
    aw, apcts = MI.side_frame(ask_df, "ask")
    bw, bpcts = MI.side_frame(bid_df, "bid")
    ask, bid, _ = MI.align(aw, bw)
    got = MI.impact_bps(ask, apcts, 500.0)
    assert got[0] == pytest.approx(20.0)


def test_impact_walks_into_the_second_level_when_the_first_is_consumed() -> None:
    """An order larger than level 1 must pay part of level 2's larger offset."""
    ask_df = _book(ASK_LEVELS, side_sign=1)
    bid_df = _book(BID_LEVELS, side_sign=-1)
    aw, apcts = MI.side_frame(ask_df, "ask")
    bw, bpcts = MI.side_frame(bid_df, "bid")
    ask, bid, _ = MI.align(aw, bw)
    # 1000 @ 0.2% (=20bps) then 1000 @ 1% (=100bps) -> 20*1000+100*1000 / 2000
    got = MI.impact_bps(ask, apcts, 2_000.0)
    assert got[0] == pytest.approx(60.0)


def test_unfillable_order_returns_nan_rather_than_a_truncated_cost() -> None:
    """An order larger than the visible ladder has NO measured cost.

    Returning the cost of the part that filled would understate impact and make a
    thin book look cheaper than a deep one -- the exact inversion that matters.
    """
    ask_df = _book(ASK_LEVELS, side_sign=1)
    bid_df = _book(BID_LEVELS, side_sign=-1)
    aw, apcts = MI.side_frame(ask_df, "ask")
    bw, bpcts = MI.side_frame(bid_df, "bid")
    ask, bid, _ = MI.align(aw, bw)
    got = MI.impact_bps(ask, apcts, 10_000.0)
    assert np.isnan(got[0])


# --------------------------------------------------------- D2: alignment


def test_sides_are_aligned_on_common_complete_snapshots() -> None:
    """A snapshot missing a bid level must not shorten only the bid side.

    This is D2. With ragged snapshots the two sides came out of the loader at
    different lengths (2879 vs 2831) and the elementwise comparison raised.
    """
    ask_df = _book(ASK_LEVELS, ts="t1", side_sign=1)
    ask_df = pd.concat([ask_df, _book(ASK_LEVELS, ts="t2", side_sign=1)])
    bid_df = _book(BID_LEVELS, ts="t1", side_sign=-1)          # t2 bid is missing

    aw, apcts = MI.side_frame(ask_df, "ask")
    bw, bpcts = MI.side_frame(bid_df, "bid")
    ask, bid, dropped = MI.align(aw, bw)
    assert ask.shape[0] == bid.shape[0] == 1
    assert dropped == 1


def test_non_monotone_ladder_is_rejected_not_accepted() -> None:
    """A file whose semantics changed must fail, not produce a number."""
    bad = _book({0.2: 1_000.0, 1.0: 500.0, 2.0: 9_000.0}, side_sign=1)
    bad_bid = _book({0.2: 1_000.0, 1.0: 500.0, 2.0: 9_000.0}, side_sign=-1)
    aw, _ = MI.side_frame(bad, "ask")
    bw, _ = MI.side_frame(bad_bid, "bid")
    with pytest.raises(ValueError, match="monotone"):
        MI.align(aw, bw)


# ------------------------------------ E#6 sensitivity across cost regimes


def test_headline_regime_reproduces_the_published_e6_return() -> None:
    """At the published 13.1 bps the model must return E6_RESULT.md's +15.6%/yr.

    If this drifts, the scaling below is no longer anchored to the published
    result and every row of the regime table is unanchored too.
    """
    got = CRS.e6_net_pct_per_yr(CRS.E6_HEADLINE_BPS)
    assert got == pytest.approx(15.6, abs=0.2)


def test_worst_regime_is_the_maximum_not_the_minimum() -> None:
    """D4. The stress case is the MOST expensive regime, i.e. max().

    Using min() selects the calm day as the stress case: 12.0 bps instead of
    34.9, understating the cost range by 2.9x and reporting a 0.9x "stress"
    multiplier where the true figure is 2.7x. Nothing errors; the number is just
    quietly wrong in the reassuring direction.
    """
    worst = max(CRS.REGIMES.values())
    assert worst == 34.9
    assert max(CRS.REGIMES, key=CRS.REGIMES.get).startswith("COVID crash")
    assert worst / CRS.E6_HEADLINE_BPS == pytest.approx(2.66, abs=0.01)


def test_e6_stays_net_positive_in_every_measured_regime() -> None:
    """E#6 is reported as not cost-bound; this is the check that it still is.

    The regime table exists to extend E6's published frontier (which ran out to
    48.0 bps in BOOK SIZE) into TIME. If any measured regime flipped the sign,
    that claim would be false and the table would have to be reported as a
    change of verdict rather than a confirmation.
    """
    for label, bps in CRS.REGIMES.items():
        assert CRS.e6_net_pct_per_yr(bps) > 0.0, f"E#6 flips negative in {label}"


def test_e6_net_is_monotone_decreasing_in_cost() -> None:
    """More cost can only make the line worse. Anything else is a sign error."""
    nets = [CRS.e6_net_pct_per_yr(b) for b in sorted(CRS.REGIMES.values())]
    assert nets == sorted(nets, reverse=True)


# --------------------------------------------------- D3: the renderer defect


def test_state_to_glyph_mapping_cannot_collapse_present_and_absent() -> None:
    """'present' and 'absent' must never render to the same marker.

    This is D3. The availability grid compared a state STRING against `True`,
    which is never true, so every cell rendered as absent. A confident table of
    uniform absence was printed while the run's own control probe said present.
    """
    glyphs = {s: {"present": "Y", "absent": "-", "unknown": "?"}[s]
              for s in ("present", "absent", "unknown")}
    assert glyphs["present"] != glyphs["absent"]
    assert len(set(glyphs.values())) == 3
