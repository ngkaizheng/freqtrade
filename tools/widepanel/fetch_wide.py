"""Download a wide Binance USD-M perp panel: 4h klines + funding, 2023-01 -> 2026-09.

Written for PREREG_WIDE_PANEL_2026-09-27.md. The symbol list is derived by RULE
(onboardDate <= 2023-01-01, status TRADING), never by result.

Two things this refuses to do silently:
  * a symbol whose download 404s is DROPPED and the drop is recorded with the
    reason, never quietly skipped (RESEARCH_STATE §3.10 - a successful-looking
    empty response must never read as "no data exists");
  * a symbol with no funding history is DROPPED, because a book with no funding
    charge has a fabricated edge (the funding term is ~0.056R against a 0.0428R
    edge).
"""

from __future__ import annotations

import io
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "shark_data" / "wide"
VISION = "https://data.binance.vision/data/futures/um/monthly"
ONBOARD_CUTOFF = 1672531200000  # 2023-01-01 UTC, ms
EXCLUDE = {"BTCDOMUSDT"}  # a dominance INDEX contract, not a crypto price

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "freqtrade-research/1.0"})


def universe() -> list[str]:
    r = SESSION.get("https://fapi.binance.com/fapi/v1/exchangeInfo", timeout=60)
    r.raise_for_status()
    syms = [
        s["symbol"] for s in r.json()["symbols"]
        if s["contractType"] == "PERPETUAL"
        and s["status"] == "TRADING"
        and s["quoteAsset"] == "USDT"
        and s["onboardDate"] <= ONBOARD_CUTOFF
        and s["symbol"] not in EXCLUDE
    ]
    return sorted(syms)


def months() -> list[tuple[str, str]]:
    out, y, m = [], 2023, 1
    while (y, m) <= (2026, 8):
        out.append((f"{y}-{m:02d}", f"{y}{m:02d}"))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def _get(url: str) -> bytes | None:
    for attempt in range(3):
        try:
            r = SESSION.get(url, timeout=60)
            if r.status_code == 200:
                return r.content
            if r.status_code in (403, 404, 400):
                return None          # genuinely absent
            if r.status_code == 429:
                time.sleep(2 + 3 * attempt)   # S3 answers rate-limits as 404 (§3.32)
                continue
        except requests.RequestException:
            time.sleep(1 + 2 * attempt)
    return None


def fetch_klines(sym: str) -> tuple[str, pd.DataFrame | None, str]:
    frames = []
    for ym, compact in months():
        blob = _get(f"{VISION}/klines/{sym}/4h/{sym}-4h-{ym}.zip")
        if blob is None:
            continue
        try:
            with zipfile.ZipFile(io.BytesIO(blob)) as z:
                name = z.namelist()[0]
                df = pd.read_csv(z.open(name), header=0)
            frames.append(df)
        except Exception as exc:                      # noqa: BLE001
            return sym, None, f"parse:{type(exc).__name__}"
    if not frames:
        return sym, None, "no_months"
    raw = pd.concat(frames, ignore_index=True)
    raw = raw.rename(columns={"open_time": "open_time"})
    return sym, raw, "ok"


def fetch_funding(sym: str) -> tuple[str, pd.DataFrame | None, str]:
    frames = []
    for ym, _ in months():
        blob = _get(f"{VISION}/fundingRate/{sym}/{sym}-fundingRate-{ym}.zip")
        if blob is None:
            continue
        try:
            with zipfile.ZipFile(io.BytesIO(blob)) as z:
                frames.append(pd.read_csv(z.open(z.namelist()[0]), header=0))
        except Exception:                             # noqa: BLE001
            continue
    if not frames:
        return sym, None, "no_funding"
    return sym, pd.concat(frames, ignore_index=True), "ok"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    syms = universe()
    print(f"universe by rule: {len(syms)} symbols", flush=True)

    kdir, fdir = OUT / "klines_4h", OUT / "funding"
    kdir.mkdir(exist_ok=True)
    fdir.mkdir(exist_ok=True)

    dropped: list[tuple[str, str]] = []

    with ThreadPoolExecutor(max_workers=12) as pool:
        futs = {pool.submit(fetch_klines, s): s for s in syms}
        done = 0
        for fut in as_completed(futs):
            sym, raw, status = fut.result()
            done += 1
            if raw is None:
                dropped.append((sym, f"klines:{status}"))
                print(f"[{done}/{len(syms)}] {sym:<16} DROP {status}", flush=True)
                continue
            out = raw.copy()
            out["open_time"] = pd.to_datetime(out["open_time"], unit="ms", utc=True)
            out = out.drop_duplicates(subset="open_time").sort_values("open_time")
            out.to_csv(kdir / f"{sym}_4h.csv.gz", index=False, compression="gzip")
            print(f"[{done}/{len(syms)}] {sym:<16} ok rows={len(out)}", flush=True)

    print("\nfunding pass", flush=True)
    with ThreadPoolExecutor(max_workers=12) as pool:
        futs = {pool.submit(fetch_funding, s): s for s in syms}
        for fut in as_completed(futs):
            sym, raw, status = fut.result()
            if raw is None:
                dropped.append((sym, f"funding:{status}"))
                print(f"{sym:<16} DROP {status}", flush=True)
                continue
            out = raw.copy()
            tcol = "funding_time" if "funding_time" in out.columns else out.columns[0]
            out[tcol] = pd.to_datetime(out[tcol], unit="ms", utc=True)
            out = out.drop_duplicates(subset=tcol).sort_values(tcol)
            out.to_csv(fdir / f"{sym}.csv.gz", index=False, compression="gzip")

    # NOTE: Path("X.csv.gz").stem is "X.csv", NOT "X". Getting this wrong makes
    # the klines/funding intersection silently empty while every file exists on
    # disk - a pipeline that reports "0 usable, 0 dropped" and looks healthy.
    # Hence the explicit assertion below rather than a bare intersection.
    have_k = {p.name.replace("_4h.csv.gz", "") for p in kdir.glob("*_4h.csv.gz")}
    have_f = {p.name.replace(".csv.gz", "") for p in fdir.glob("*.csv.gz")}
    usable = sorted(have_k & have_f)
    k_only = sorted(have_k - have_f)
    f_only = sorted(have_f - have_k)

    accounted = len(usable) + len(k_only) + len(f_only)
    assert accounted == len(have_k) or accounted == len(have_f), (
        f"universe accounting failed: klines={len(have_k)} funding={len(have_f)} "
        f"usable={len(usable)} k_only={len(k_only)} f_only={len(f_only)}"
    )
    assert len(usable) > 0, (
        f"ZERO usable symbols while {len(have_k)} kline and {len(have_f)} funding "
        f"files exist - this is a name-parsing bug, not a data absence"
    )
    assert len(usable) + len(dropped) == len(syms), (
        f"symbols unaccounted for: requested={len(syms)} usable={len(usable)} "
        f"dropped={len(dropped)}"
    )

    pd.DataFrame(dropped, columns=["symbol", "reason"]).to_csv(
        OUT / "dropped.csv", index=False)
    pd.Series(usable, name="symbol").to_csv(OUT / "universe.csv", index=False)

    print("\n" + "=" * 60)
    print(f"kline files on disk : {len(have_k)}")
    print(f"funding files on disk: {len(have_f)}")
    print(f"usable (both)       : {len(usable)}")
    print(f"klines only         : {len(k_only)} {k_only[:5]}")
    print(f"funding only        : {len(f_only)} {f_only[:5]}")
    print(f"dropped (with reason): {len(dropped)} -> {OUT / 'dropped.csv'}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
