"""Compact digest for a DefiLlama protocol: methodology ( = the actual economic
mechanism as DefiLlama models it) plus revenue aggregates and the last N daily
values, so revenue TREND is visible rather than just a 30-day total.

Usage:
    python tools/catalyst_scan/llama_digest.py ore-protocol pons-v1 stonkfun
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_market as fm  # noqa: E402


def digest(slug: str, data_type: str = "dailyHoldersRevenue", tail: int = 14) -> None:
    d = fm.get(f"{fm.LLAMA}/summary/fees/{slug}", dataType=data_type)
    if not isinstance(d, dict):
        print(f"--- {slug}: NO DATA ({data_type}) ---\n")
        return
    print(f"=== {slug} [{data_type}] ===")
    print(f"name        : {d.get('name')}  ({d.get('symbol')})  category={d.get('category')}")
    print(f"chain(s)    : {d.get('chains')}  gecko_id={d.get('gecko_id')}  url={d.get('url')}")
    print(f"listedAt    : {_ts(d.get('listedAt'))}")
    meth = d.get("methodology") or {}
    for k in ("Fees", "Revenue", "ProtocolRevenue", "HoldersRevenue", "SupplySideRevenue"):
        if k in meth:
            print(f"  {k:18s}: {meth[k]}")
    bd = d.get("breakdownMethodology") or {}
    for k, v in (bd.get("HoldersRevenue") or {}).items():
        print(f"  HoldersRevenue[{k}]: {v}")
    print(f"  doublecounted={d.get('doublecounted')}  parent={d.get('parentProtocol')}")
    for k in ("total24h", "total7d", "total30d", "total1y", "annualized1y"):
        v = d.get(k)
        if isinstance(v, (int, float)):
            print(f"  {k:14s}: ${v:,.0f}")
    cb = d.get("chainBreakdown") or {}
    for ch, m in cb.items():
        print(
            f"  [{ch}] change_7d={m.get('change_7d')}%  change_1m={m.get('change_1m')}%  "
            f"7d_over_7d={m.get('change_7dover7d')}%  30d_over_30d={m.get('change_30dover30d')}%"
        )
    chart = d.get("totalDataChart") or []
    if chart:
        print(f"  last {tail} daily values (USD):")
        for ts, v in chart[-tail:]:
            print(f"    {_ts(ts)}  ${v:>12,.0f}")
        vals = [v for _, v in chart]
        n = len(vals)
        print(f"  {n} days of history; max ${max(vals):,.0f}; mean ${sum(vals)/n:,.0f}; last ${vals[-1]:,.0f}")
        if n >= 60:
            print(f"  mean first-half ${sum(vals[:n//2])/(n//2):,.0f} vs second-half ${sum(vals[n//2:])/(n-n//2):,.0f}")
    print()


def _ts(x) -> str:
    if x is None:
        return "n/a"
    try:
        return datetime.fromtimestamp(int(x), tz=timezone.utc).strftime("%Y-%m-%d")
    except Exception:  # noqa: BLE001
        return str(x)


if __name__ == "__main__":
    args = sys.argv[1:]
    dtype = "dailyHoldersRevenue"
    if args and args[0].startswith("--type="):
        dtype = args[0].split("=", 1)[1]
        args = args[1:]
    for s in args:
        digest(s, dtype)
