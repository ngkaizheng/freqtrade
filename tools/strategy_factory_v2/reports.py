"""Human-readable reporting for the Phase A/B audit.

The reports written here exist to answer one question honestly: *what can V2
actually do with the data on this machine?* They are deliberately blunt. A
report that reads well while the data cannot support the research is worse than
no report, so anything unavailable is stated as unavailable, in the summary
table, not buried in an appendix.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Iterable, Sequence

from tools.strategy_factory_v2.data import AVAILABLE, DEGRADED, MISSING
from tools.strategy_factory_v2.spec import (
    DISCOVERY_TIMEFRAMES,
    FUNDING_PERCENTILE_CUTS,
    LIQUIDITY_PERCENTILE_CUTS,
    OI_PERCENTILE_CUTS,
    PRIMARY_TIMEFRAMES,
    SPEC_VERSION,
    SURVIVOR_CRITERIA,
    VOL_PERCENTILE_CUTS,
)
from tools.strategy_factory_v2 import regime as regime_module
from tools.strategy_factory_v2 import spec as spec_module

_STATUS_MARK = {AVAILABLE: "OK", DEGRADED: "PARTIAL", MISSING: "ABSENT"}


def _fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return "--"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int,)):
        return str(value)
    if isinstance(value, float):
        return f"{value:,.{digits}f}"
    return str(value)


def _short(value: str | None, digits: int = 10) -> str:
    if not value:
        return "--"
    text = str(value)
    return text[:digits]


def write_data_audit_json(manifest: dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "data_audit.json"
    path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    return path


def write_data_reality_report(
    manifest: dict[str, Any],
    registry: dict[str, Any],
    causality: dict[str, Any] | None,
    output_dir: Path,
) -> Path:
    """Write ``DATA_REALITY.md``: the one document a reviewer should read first."""

    output_dir.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    add = lines.append

    add("# Strategy Factory V2 - data reality report")
    add("")
    add(f"- Spec version: `{SPEC_VERSION}`")
    add(f"- Data directory: `{manifest['data_dir']}`")
    add(f"- Symbols discovered: **{manifest['symbols_discovered']}**")
    add(f"- Primary timeframes ready: **{', '.join(manifest['primary_timeframes_ready']) or 'none'}**")
    missing_primary = manifest.get("missing_primary_timeframes") or []
    if missing_primary:
        add(f"- Primary timeframes missing: **{', '.join(missing_primary)}**")
    add("")
    add("> This report describes what is on disk, not what would be nice to have on")
    add("> disk. A field marked ABSENT is not estimated, not proxied and not")
    add("> substituted; the hypothesis families that depend on it are reported")
    add("> BLOCKED and will not be evaluated.")
    add("")

    # ---- verdict -------------------------------------------------------
    blocked = registry.get("blocked_hypotheses", 0)
    testable = registry.get("testable_hypotheses", 0)
    total = registry.get("hypothesis_count", 0)
    add("## Headline")
    add("")
    add(f"| Metric | Value |")
    add("|---|---:|")
    add(f"| Preregistered hypotheses | {total} |")
    add(f"| Testable with current data | **{testable}** |")
    add(f"| BLOCKED by missing data | **{blocked}** |")
    add(f"| Families | {registry.get('family_count')} |")
    if causality is not None:
        add(f"| Causality checks passed | {_fmt(causality.get('passed'))} |")
        add(f"| Causality findings | {len(causality.get('findings', []))} |")
        add(f"| Values compared by causality probes | {causality.get('rows_compared', 0):,} |")
    add("")

    # ---- fields --------------------------------------------------------
    add("## Derivatives fields, symbol by symbol")
    add("")
    add("| Symbol | funding_rate | open_interest | mark_price | index_price | basis | taker_buy | taker_sell |")
    add("|---|---|---|---|---|---|---|---|")
    for symbol, audit in sorted(manifest["symbol_audits"].items()):
        status = audit.get("field_status", {})
        cells = [
            _STATUS_MARK.get(status.get(name, MISSING), "?")
            for name in (
                "funding_rate",
                "open_interest",
                "mark_price",
                "index_price",
                "basis",
                "taker_buy_volume",
                "taker_sell_volume",
            )
        ]
        add(f"| {symbol} | " + " | ".join(cells) + " |")
    add("")

    totals = manifest.get("field_totals", {})
    absent = [name for name, counts in totals.items() if counts.get(AVAILABLE, 0) == 0]
    if absent:
        add("### Fields absent on every symbol")
        add("")
        for name in absent:
            add(f"- `{name}` - unavailable on all {manifest['symbols_discovered']} symbols")
        add("")

    # ---- price coverage ------------------------------------------------
    add("## Price coverage")
    add("")
    add("| Symbol | Timeframe | Rows | Span | Gaps | Dups | Invalid | Usable |")
    add("|---|---|---:|---|---:|---:|---:|---|")
    for symbol, audit in sorted(manifest["symbol_audits"].items()):
        for timeframe, report in sorted(
            audit.get("timeframes", {}).items(),
            key=lambda kv: spec_module.TIMEFRAME_MINUTES.get(kv[0], 10**9),
        ):
            add(
                f"| {symbol} | {timeframe} | {report.get('rows', 0):,} | "
                f"{_short(report.get('start'), 10)} -> {_short(report.get('end'), 10)} | "
                f"{report.get('gap_events', 0)} | {report.get('duplicates', 0)} | "
                f"{report.get('invalid_ohlcv', 0)} | {_fmt(report.get('usable'))} |"
            )
    add("")

    # ---- funding -------------------------------------------------------
    add("## Funding detail")
    add("")
    add("| Symbol | Events | Interval | First | Last | Missing | Completeness | Clamped | Selected source |")
    add("|---|---:|---|---|---|---:|---:|---:|---|")
    for symbol, audit in sorted(manifest["symbol_audits"].items()):
        funding = audit.get("funding", {})
        selected = funding.get("selected", {})
        if selected.get("status") != AVAILABLE:
            add(f"| {symbol} | 0 | -- | -- | -- | -- | -- | -- | **ABSENT** |")
            continue
        add(
            f"| {symbol} | {selected.get('rows', 0):,} | "
            f"{_fmt(selected.get('observed_interval_hours'), 1)}h | "
            f"{_short(selected.get('start'), 16)} | {_short(selected.get('end'), 16)} | "
            f"{selected.get('missing_events', 0)} | "
            f"{_fmt(selected.get('completeness_ratio'), 4)} | "
            f"{_fmt(selected.get('clamped_ratio'), 4)} | "
            f"`{Path(str(selected.get('source'))).name}` |"
        )
    add("")
    add("### Cross-source funding agreement")
    add("")
    for symbol, audit in sorted(manifest["symbol_audits"].items()):
        cross = (audit.get("funding", {}) or {}).get("cross_source", {})
        if cross.get("status") == AVAILABLE:
            add(
                f"- {symbol}: {cross['identical_settlements']:,} of "
                f"{cross['shared_settlements']:,} shared settlements identical "
                f"({_fmt(cross['identical_ratio'], 4)}), max spread "
                f"{_fmt(cross['max_spread_bps'], 6)} bps"
            )
        else:
            add(f"- {symbol}: {cross.get('reason', 'single source')}")
    add("")

    # ---- regime readiness ----------------------------------------------
    add("## Regime engine readiness")
    add("")
    add("| Regime | States | Preregistered percentile cuts | Ready |")
    add("|---|---|---|---|")
    for name, states, cuts, ready in (
        ("trend", regime_module.TREND_STATES, regime_module.TREND_SCORE_CUTS, True),
        ("volatility", regime_module.VOL_STATES, VOL_PERCENTILE_CUTS, True),
        ("liquidity", regime_module.LIQUIDITY_STATES, LIQUIDITY_PERCENTILE_CUTS, True),
        ("open_interest", regime_module.OI_STATES, OI_PERCENTILE_CUTS, False),
        ("funding", regime_module.FUNDING_STATES, FUNDING_PERCENTILE_CUTS, True),
    ):
        status = "yes" if ready else "**no - emits UNKNOWN for every bar**"
        add(f"| {name} | {', '.join(states)} | {', '.join(str(c) for c in cuts)} | {status} |")
    add("")

    # ---- hypotheses ----------------------------------------------------
    add("## Hypothesis registry readiness")
    add("")
    add("| Family | Count | Requires | Testable | Blocked |")
    add("|---|---:|---|---:|---:|")
    for name, entry in sorted(registry.get("families", {}).items()):
        add(
            f"| {name} | {entry['count']} | "
            f"{', '.join(entry['required_fields'])} | "
            f"{entry['testable']} | **{entry['blocked']}** |"
        )
    add("")
    blocked_ids = registry.get("blocked_hypothesis_ids") or []
    if blocked_ids:
        add("### BLOCKED hypothesis ids")
        add("")
        add("```text")
        for hypothesis_id in blocked_ids:
            add(hypothesis_id)
        add("```")
        add("")

    # ---- what is still missing -----------------------------------------
    add("## What is missing, and what it blocks")
    add("")
    add("| Missing input | Consequence | Where it would come from |")
    add("|---|---|---|")
    add(
        "| `open_interest` | H1, H2, H5, H6, H7 are BLOCKED | Binance Vision "
        "`data/futures/um/monthly/metrics/<SYMBOL>/` (5-minute grid, ~30 months) "
        "or the `openInterestHist` REST endpoint (rolling 30 days only) |"
    )
    add(
        "| `taker_buy_volume` / `taker_sell_volume` | taker-imbalance limb of H6 is BLOCKED | "
        "Binance Vision monthly klines, which carry "
        "`taker_buy_base_asset_volume` / `taker_buy_quote_asset_volume` columns that the "
        "Freqtrade downloader currently discards |"
    )
    add(
        "| `index_price` | H10 (basis extremes) is BLOCKED | Binance Vision "
        "`data/futures/um/monthly/indexPriceKlines/` or the `indexPriceKlines` REST endpoint |"
    )
    add(
        "| `4h` and `30m` price | optional horizons unavailable | derived from stored 1m, "
        "or a further download |"
    )
    add(
        "| price data after the stored end | the final holdout and the 30-90 day forward "
        "window cannot be started | a fresh download; **the holdout must stay untouched "
        "once reserved** |"
    )
    add("")
    add("### Symbols the plan asked for that are not usable")
    add("")
    add("| Symbol | Funding present | Price present | Verdict |")
    add("|---|---|---|---|")
    for symbol, audit in sorted(manifest["symbol_audits"].items()):
        has_funding = (audit.get("funding", {}) or {}).get("selected", {}).get("status") == AVAILABLE
        has_price = bool(audit.get("timeframes"))
        verdict = "usable" if (has_price and has_funding) else "**not usable: no price data**"
        add(f"| {symbol} | {_fmt(has_funding)} | {_fmt(has_price)} | {verdict} |")
    add("")
    add("## Next gate before Phase C")
    add("")
    add("1. Confirm the data audit above against the files on disk.")
    add("2. Decide whether to acquire the missing derivatives inputs. Without them")
    add("   roughly a third of the registry stays BLOCKED by construction.")
    add("3. Reserve the final holdout period *before* the Phase C experiment runs.")
    add("4. Only then freeze the spec version and execute the conditional-return")
    add("   engine. No survivor may be produced before that.")
    add("")

    path = output_dir / "DATA_REALITY.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_html_report(
    manifest: dict[str, Any],
    registry: dict[str, Any],
    causality: dict[str, Any] | None,
    output_dir: Path,
) -> Path:
    """A dependency-free HTML view, matching the MVP's no-plotting-library rule."""

    output_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for symbol, audit in sorted(manifest["symbol_audits"].items()):
        status = audit.get("field_status", {})
        cells = "".join(
            f"<td class='{status.get(name, MISSING).lower()}'>"
            f"{html.escape(_STATUS_MARK.get(status.get(name, MISSING), '?'))}</td>"
            for name in (
                "funding_rate",
                "open_interest",
                "mark_price",
                "index_price",
                "basis",
                "taker_buy_volume",
                "taker_sell_volume",
            )
        )
        rows.append(f"<tr><th>{html.escape(symbol)}</th>{cells}</tr>")

    family_rows = "".join(
        "<tr>"
        f"<td>{html.escape(name)}</td><td>{entry['count']}</td>"
        f"<td>{html.escape(', '.join(entry['required_fields']))}</td>"
        f"<td>{entry['testable']}</td><td class='blocked'>{entry['blocked']}</td>"
        "</tr>"
        for name, entry in sorted(registry.get("families", {}).items())
    )

    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Strategy Factory V2 data reality</title>
<style>
 body {{ font-family: ui-sans-serif, system-ui, sans-serif; margin: 2rem; color:#111; }}
 h1, h2 {{ font-weight: 600; }}
 table {{ border-collapse: collapse; margin: 1rem 0; font-size: .9rem; }}
 th, td {{ border: 1px solid #d4d4d4; padding: .35rem .6rem; text-align: left; }}
 th {{ background: #f5f5f5; }}
 td.available {{ background: #dcfce7; }}
 td.degraded {{ background: #fef3c7; }}
 td.missing  {{ background: #fee2e2; color:#7f1d1d; }}
 td.blocked  {{ background: #fee2e2; color:#7f1d1d; font-weight:600; }}
 .banner {{ background:#fee2e2; border-left:4px solid #dc2626; padding:.75rem 1rem; margin:1rem 0; }}
</style></head><body>
<h1>Strategy Factory V2 - data reality</h1>
<p>Spec version <code>{html.escape(SPEC_VERSION)}</code></p>
<div class="banner">
 <strong>Read this first.</strong> {registry.get('testable_hypotheses')} of
 {registry.get('hypothesis_count')} preregistered hypotheses are testable with the data
 on this machine; {registry.get('blocked_hypotheses')} are BLOCKED because a required
 input does not exist. Blocked families are not approximated or re-scoped.
</div>
<h2>Derivatives fields</h2>
<table><tr><th>Symbol</th><th>funding</th><th>OI</th><th>mark</th><th>index</th>
<th>basis</th><th>taker buy</th><th>taker sell</th></tr>
{''.join(rows)}</table>
<h2>Hypothesis families</h2>
<table><tr><th>Family</th><th>Count</th><th>Requires</th><th>Testable</th><th>Blocked</th></tr>
{family_rows}</table>
<h2>Causality</h2>
<p>{'All checks passed' if (causality or {}).get('passed') else 'CHECKS FAILED'}:
{(causality or {}).get('rows_compared', 0):,} values compared across
{html.escape(', '.join((causality or {}).get('checks_run', [])))}.</p>
</body></html>
"""
    path = output_dir / "report.html"
    path.write_text(document, encoding="utf-8")
    return path


def write_run_report(manifest: dict[str, Any], output_dir: Path) -> Path:
    """The machine-readable run manifest, written last, as in the MVP."""

    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "manifest.json"
    path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    return path
