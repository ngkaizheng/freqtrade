"""Regime backstop: pull the market-regime primitives directly from CoinGecko.

This exists so the report's regime section does not depend on a single research
subagent. It is the minimum set v4 s65 needs in order to set a Regime Factor at
all, plus the breadth statistics the v3 round used.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd
import requests

OUT = Path(__file__).resolve().parent / "out"
CG = "https://api.coingecko.com/api/v3"
H = {"accept": "application/json", "user-agent": "catalyst-v4-regime/1.0"}


def get(url, **p):
    for a in range(5):
        try:
            r = requests.get(url, params=p, headers=H, timeout=45)
            if r.status_code == 200:
                return r.json()
            print(f"  [warn] {r.status_code} try{a+1}", file=sys.stderr)
            time.sleep(15 * (a + 1))
        except Exception as e:  # noqa: BLE001
            print(f"  [warn] {type(e).__name__}", file=sys.stderr)
            time.sleep(10)
    return None


def main() -> None:
    lines = []

    # --- global market -----------------------------------------------------
    # Every /global call 429'd on the first attempt of this run, so this block
    # is allowed to fail silently: the breadth statistics computed from the
    # local universe snapshot below carry the regime verdict on their own.
    g = get(f"{CG}/global")
    if isinstance(g, dict) and isinstance(g.get("data"), dict):
        d = g["data"]
        mc = d["total_market_cap"].get("usd", float("nan"))
        vol = d["total_volume"].get("usd", float("nan"))
        lines.append(f"total market cap      ${mc/1e12:.3f}T")
        lines.append(f"24h volume            ${vol/1e9:.1f}B")
        lines.append(f"BTC dominance         {d['market_cap_percentage']['btc']:.2f}%")
        lines.append(f"ETH dominance         {d['market_cap_percentage']['eth']:.2f}%")
        lines.append(f"BTC 24h               "
                     f"{d.get('price_change_percentage_24h_usd', float('nan')):+.2f}%")
        lines.append(f"market cap 24h        "
                     f"{d['market_cap_change_percentage_24h_usd']:+.2f}%")
    else:
        lines.append("global endpoint unavailable (rate-limited); "
                     "breadth below is computed locally instead")

    # --- majors, from the LOCAL snapshot rather than a fresh API call ------
    snap = pd.read_csv(OUT / "market_snapshot.csv")
    lines.append(f"universe rows: {len(snap)}  (max rank {int(snap['rank'].max())})  "
                 f"snapshot last_updated: {snap['updated'].dropna().max()}")
    majors = snap[snap["symbol"].isin(["BTC", "ETH", "SOL", "BNB", "HYPE"])]
    if not majors.empty:
        lines.append("")
        lines.append(f"{'sym':<6s}{'price':>14s}{'7d%':>9s}{'30d%':>9s}"
                     f"{'mcap$B':>10s}{'vol/MC':>8s}{'from ATH%':>11s}")
        for _, c in majors.sort_values("mcap", ascending=False).iterrows():
            lines.append(
                f"{c['symbol']:<6s}{c['price']:>14,.4f}{c['chg7']:>9.2f}"
                f"{c['chg30']:>9.2f}{c['mcap']/1e9:>10.2f}{c['vol_mcap']:>8.3f}"
                f"{c['ath_chg']:>11.2f}")
        b = majors[majors["symbol"] == "BTC"]
        e = majors[majors["symbol"] == "ETH"]
        if not b.empty and not e.empty:
            b, e = b.iloc[0], e.iloc[0]
            now = e["price"] / b["price"]
            b0 = b["price"] / (1 + b["chg30"] / 100)
            e0 = e["price"] / (1 + e["chg30"] / 100)
            then = e0 / b0
            lines.append("")
            lines.append(f"ETH/BTC now            {now:.6f}")
            lines.append(f"ETH/BTC 30d ago       {then:.6f}  "
                         f"({(now/then-1)*100:+.2f}%)")

    # --- breadth -----------------------------------------------------------
    lines.append("")
    for label, sub in [
        ("top 200", snap.nlargest(200, "mcap")),
        ("top 500", snap.nlargest(500, "mcap")),
        ("top 1000", snap.nlargest(1000, "mcap")),
    ]:
        d = sub.dropna(subset=["chg30", "ath_chg"])
        lines.append(
            f"{label:<9s} n={len(d):4d}  median 30d {d['chg30'].median():+7.2f}%  "
            f"share up 30d {(d['chg30'] > 0).mean()*100:5.1f}%  "
            f"median from ATH {d['ath_chg'].median():+7.2f}%  "
            f"within 25% of ATH {(d['ath_chg'] > -25).mean()*100:4.1f}%"
        )

    # --- category performance ---------------------------------------------
    print("categories ...", file=sys.stderr)
    cats = get(f"{CG}/coins/categories")
    if isinstance(cats, list):
        rows = []
        for c in cats:
            v = c.get("market_cap")
            ch = c.get("market_cap_change_24h")
            v = v if isinstance(v, dict) else {}
            ch = ch if isinstance(ch, dict) else {}
            cap = v.get("usd", 0) or 0
            if cap < 1e8:
                continue
            volv = c.get("volume_24h")
            volv = volv if isinstance(volv, dict) else {}
            rows.append((c.get("name", "?"), cap,
                         ch.get("usd", float("nan")), volv.get("usd", 0) or 0))
        r = pd.DataFrame(rows, columns=["cat", "mcap", "chg24", "vol"])
        if not r.empty:
            r["turnover"] = r["vol"] / r["mcap"]
            r = r.sort_values("mcap", ascending=False)
            lines.append("")
            lines.append(f"{'category':<26s}{'mcap$B':>10s}{'24h%':>9s}{'turnover':>10s}")
            for _, x in r.head(22).iterrows():
                lines.append(f"{x['cat'][:25]:<26s}{x['mcap']/1e9:>10.2f}"
                             f"{x['chg24']:>9.2f}{x['turnover']:>10.3f}")
            r.to_csv(OUT / "regime_categories.csv", index=False)
    else:
        lines.append("")
        lines.append("category endpoint unavailable (rate-limited)")

    txt = "\n".join(lines)
    (OUT / "regime.md").write_text(txt, encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
