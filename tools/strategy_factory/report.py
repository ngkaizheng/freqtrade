"""Human-readable report and dependency-free HTML heatmaps."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def _fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not np.isfinite(number):
        return "—"
    return f"{number:.{digits}f}"


def _gate_text(value: Any) -> str:
    return "PASS" if bool(value) else "FAIL"


def write_heatmaps(trial_results: pd.DataFrame, output_dir: Path) -> None:
    """Write small HTML tables without adding a plotting dependency."""

    if trial_results.empty:
        return
    for hypothesis, group in trial_results.groupby("hypothesis_id", sort=True):
        rows: list[dict[str, Any]] = []
        for params_json in group["params"].dropna().unique():
            try:
                params = json.loads(params_json)
            except (TypeError, json.JSONDecodeError):
                continue
            rows.append(
                {
                    "params": params,
                    "value": float(
                        group.loc[group["params"] == params_json, "validation_expectancy"].mean()
                    ),
                }
            )
        if not rows:
            continue
        keys = list(rows[0]["params"])
        if len(keys) < 2:
            continue
        x_key, y_key = keys[0], keys[1]
        x_values = sorted({row["params"][x_key] for row in rows}, key=str)
        y_values = sorted({row["params"][y_key] for row in rows}, key=str)
        lookup = {
            (str(row["params"][x_key]), str(row["params"][y_key])): row["value"]
            for row in rows
        }
        finite = [value for value in lookup.values() if np.isfinite(value)]
        scale = max(abs(value) for value in finite) if finite else 1.0
        table_rows = []
        for y_value in y_values:
            cells = [f"<th>{html.escape(str(y_value))}</th>"]
            for x_value in x_values:
                value = lookup.get((str(x_value), str(y_value)), np.nan)
                if np.isfinite(value):
                    intensity = min(1.0, abs(value) / scale)
                    color = (
                        "#86efac" if value >= 0 else "#fecaca"
                    )
                    alpha = 0.35 + 0.65 * intensity
                    style = f"background:rgba({34 if value >= 0 else 239},{197 if value >= 0 else 68},{94 if value >= 0 else 68},{alpha:.2f})"
                    text = _fmt(value)
                else:
                    style = "background:#f3f4f6"
                    text = "—"
                cells.append(f'<td style="{style};padding:6px;text-align:right">{text}</td>')
            table_rows.append("<tr>" + "".join(cells) + "</tr>")
        header = "".join(f"<th>{html.escape(str(value))}</th>" for value in x_values)
        document = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{html.escape(hypothesis)} heatmap</title>
<style>body{{font-family:system-ui,sans-serif;margin:2rem}}table{{border-collapse:collapse}}
th,td{{border:1px solid #fff;padding:6px;min-width:72px}}thead th{{background:#e5e7eb}}
caption{{text-align:left;font-weight:600;margin-bottom:.6rem}}</style></head>
<body><table><caption>{html.escape(hypothesis)} — mean validation expectancy; x={x_key}, y={y_key}</caption>
<thead><tr><th>{html.escape(y_key)} \\ {html.escape(x_key)}</th>{header}</tr></thead>
<tbody>{''.join(table_rows)}</tbody></table></body></html>"""
        (output_dir / f"heatmap_{hypothesis}.html").write_text(document, encoding="utf-8")


def write_report(
    output_dir: Path,
    manifest: dict[str, Any],
    summary: pd.DataFrame,
    fold_winners: pd.DataFrame,
) -> None:
    """Write a concise report with explicit limitations and gate outcomes."""

    lines = [
        "# Strategy Factory MVP report",
        "",
        f"- Run ID: `{manifest.get('run_id')}`",
        f"- Spec version: `{manifest.get('spec_version')}`",
        f"- Data fingerprint: `{manifest.get('data_fingerprint')}`",
        f"- Source hash: `{manifest.get('source_hash')}`",
        f"- Executed trials: `{manifest.get('executed_trial_count')}` / `{manifest.get('full_trial_count')}`",
        f"- Truncated diagnostic search: `{manifest.get('truncated_search')}`",
        f"- Walk-forward origin override: `{manifest.get('walk_forward_override')}`",
        "",
        "## Data and execution",
        "",
    ]
    for audit in manifest.get("data_audits", []):
        one = audit["one_minute"]
        five = audit["five_minute"]
        cross = audit.get("cross_timeframe", {})
        funding = audit["funding"]
        lines.extend(
            [
                f"### {audit['pair']}",
                f"- 1m: {one['rows']} rows, {one['start']} → {one['end']}, gaps={one['gaps']}, duplicates={one['duplicates']}, invalid={one['invalid_ohlcv']}",
                f"- 5m: {five['rows']} rows, {five['start']} → {five['end']}, gaps={five['gaps']}, duplicates={five['duplicates']}, invalid={five['invalid_ohlcv']}",
                f"- 1m/5m cross-check: {cross.get('mismatched_buckets', '—')} mismatched common buckets; stored 5m remains authoritative",
                f"- funding: {funding['rows']} observed events ({funding.get('layout', 'unknown')}), {funding['start']} → {funding['end']}",
                f"- mark: {audit.get('files', {}).get('mark', {}).get('layout', 'not loaded')}", 
            ]
        )
    lines.extend(["", "## Hypothesis results", ""])
    if summary.empty:
        lines.append("No hypothesis produced a complete walk-forward selection.")
    else:
        lines.append("| Hypothesis | Trades | Expectancy | PF | Stress PF | DSR | RC p | Survivor |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|:---:|")
        for _, row in summary.iterrows():
            lines.append(
                f"| {row['hypothesis_id']} | {int(row['oos_trades'])} | {_fmt(row['oos_expectancy'])} | {_fmt(row['oos_profit_factor'])} | {_fmt(row['stress_profit_factor'])} | {_fmt(row['dsr'])} | {_fmt(row['reality_check_p'])} | {_gate_text(row['survivor'])} |"
            )
        lines.extend(["", "### Gates", ""])
        for _, row in summary.iterrows():
            gate_names = [key[5:] for key in row.index if key.startswith("gate_")]
            lines.append(
                f"- **{row['hypothesis_id']}**: "
                + ", ".join(f"{name}={_gate_text(row[f'gate_{name}'])}" for name in gate_names)
            )
    lines.extend(
        [
            "",
            "## Interpretation limits",
            "",
            "- OOS folds are selection-aware walk-forward estimates, not a final untouched holdout.",
            "- The 1m/5m data is treated as stored; cross-timeframe discrepancies are audited, not repaired.",
            "- Funding uses observed legacy event files and an adverse-payer convention. Current Freqtrade 2026.8 parity requires a separately staged canonical 1h funding/mark dataset.",
            "- BTC/ETH are equal-weight standalone sleeves. Families do not compete for shared cash and are not an executable combined portfolio.",
            "- DSR/Reality Check/Monte Carlo quantify sensitivity to selection and dependence; none guarantees future profitability.",
            "- A survivor would still require a separate Freqtrade parity backtest, lookahead audit, and forward dry-run.",
            "",
            "## Reproduce",
            "",
            "```powershell",
            ".\\.venv\\Scripts\\python.exe -m tools.strategy_factory run --data-dir user_data\\data\\binance\\futures --output <new-run-dir>",
            "```",
        ]
    )
    (output_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
