"""Q6 / monitoring: measure the common factor in Binance USD-M funding across coins,
and the current level of carry, from the exchange's own API (primary source).

Run:  python tools/carry/funding_live.py
Writes tools/carry/_src/funding_live.json and prints a report.
"""
import datetime as dt
import json
import pathlib

import requests

UA = {"User-Agent": "Mozilla/5.0 (research)"}
OUT = pathlib.Path("tools/carry/_src")
OUT.mkdir(parents=True, exist_ok=True)

SYMS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT",
    "ADAUSDT", "BCHUSDT", "LINKUSDT", "AVAXUSDT", "LTCUSDT", "TRXUSDT",
    "SUIUSDT", "AAVEUSDT", "UNIUSDT", "DOTUSDT", "SHIBUSDT", "XLMUSDT",
]


def funding(symbol, limit=1000):
    r = requests.get("https://fapi.binance.com/fapi/v1/fundingRate",
                     params={"symbol": symbol, "limit": limit}, headers=UA, timeout=45)
    d = r.json()
    if not isinstance(d, list) or not d:
        return None
    return d


def main():
    info = {x["symbol"]: x for x in
            requests.get("https://fapi.binance.com/fapi/v1/fundingInfo",
                         headers=UA, timeout=45).json()}

    series = {}
    for s in SYMS:
        d = funding(s)
        if d is None:
            print(f"{s}: no data")
            continue
        series[s] = {int(x["fundingTime"]): float(x["fundingRate"]) for x in d}

    rows = []
    print(f"{'sym':10s} {'n':>5s} {'iv_h':>5s} {'start':>10s} {'end':>10s} "
          f"{'meanbps':>8s} {'ann%':>7s} {'sdbps':>6s} {'neg%':>5s} "
          f"{'sd/mean':>7s} {'t_iid':>6s} {'30d_ann%':>9s} {'90d_ann%':>9s}")
    for s, d in series.items():
        ts = sorted(d)
        v = [d[t] for t in ts]
        n = len(v)
        m = sum(v) / n
        var = sum((x - m) ** 2 for x in v) / (n - 1)
        sd = var ** 0.5
        ann = m * 3 * 365 * 100
        neg = sum(1 for x in v if x < 0) / n * 100
        w30 = v[-90:]
        w90 = v[-270:]
        a30 = sum(w30) / len(w30) * 3 * 365 * 100
        a90 = sum(w90) / len(w90) * 3 * 365 * 100
        t_iid = (m / (sd / n ** 0.5) * 3 * 365) if sd else float("nan")
        iv = info.get(s, {}).get("fundingIntervalHours", "?")
        print(f"{s:10s} {n:5d} {str(iv):>5s} "
              f"{dt.datetime.fromtimestamp(ts[0]/1000, dt.timezone.utc).date()} "
              f"{dt.datetime.fromtimestamp(ts[-1]/1000, dt.timezone.utc).date()} "
              f"{m*1e4:8.3f} {ann:7.2f} {sd*1e4:6.2f} {neg:5.1f} "
              f"{(sd/m if m else float('nan')):7.2f} {t_iid:6.2f} {a30:9.2f} {a90:9.2f}")
        rows.append(dict(symbol=s, n=n, interval_h=iv, mean_bps_8h=m * 1e4,
                         ann_pct=ann, sd_bps_8h=sd * 1e4, pct_neg=neg,
                         ann_30d=a30, ann_90d=a90, sd_over_mean=sd / m if m else None,
                         t_iid_annualised=t_iid,
                         cap=info.get(s, {}).get("adjustedFundingRateCap"),
                         floor=info.get(s, {}).get("adjustedFundingRateFloor")))

    # ---- equal-weight portfolio carry ----
    print("\n--- equal-weight carry across symbols present ---")
    for label, k in (("full sample", None), ("last 90 settlements (~30d)", 90),
                     ("last 270 settlements (~90d)", 270)):
        anns = [r["ann_pct"] if k is None else (r["ann_30d"] if k == 90 else r["ann_90d"])
                for r in rows]
        n = len(anns)
        m = sum(anns) / n
        sd = (sum((x - m) ** 2 for x in anns) / (n - 1)) ** 0.5
        print(f"{label:30s} EW mean {m:+6.2f}%/yr  cross-sect sd {sd:5.2f}  "
              f"n={n}  n_negative={sum(1 for x in anns if x < 0)}")

    # ---- common factor: correlation of funding CHANGES across coins ----
    common = sorted(set.intersection(*[set(d) for d in series.values()]))
    cols = {s: [series[s][t] for t in common] for s in series}
    syms = sorted(cols)
    n = len(common)
    print(f"\n--- common factor: pairwise corr of 8h funding changes "
          f"(n={n} common settlements) ---")
    print("        " + "".join(f"{s[:6]:>7s}" for s in syms))
    avg_corr = []
    for a in syms:
        row = []
        for b in syms:
            xa = cols[a]
            xb = cols[b]
            ma, mb = sum(xa) / n, sum(xb) / n
            ca = [x - ma for x in xa]
            cb = [x - mb for x in xb]
            num = sum(p * q for p, q in zip(ca, cb))
            da = (sum(p * p for p in ca)) ** 0.5
            db = (sum(q * q for q in cb)) ** 0.5
            row.append(num / (da * db) if da and db else 0.0)
        off = [v for i, v in enumerate(row) if i != syms.index(a)]
        avg_corr.append(sum(off) / len(off))
        print(f"{a[:7]:7s} " + "".join(f"{v:7.2f}" for v in row))
    grand = (sum(avg_corr) * len(avg_corr)) / (len(avg_corr) * (len(avg_corr) - 1))
    print(f"\nmean off-diagonal correlation of funding changes = {grand:.3f}")

    # first principal component share of cross-sectional variance
    import math
    C = [[0.0] * len(syms) for _ in syms]
    for i, a in enumerate(syms):
        for j, b in enumerate(syms):
            xa, xb = cols[a], cols[b]
            ma, mb = sum(xa) / n, sum(xb) / n
            ca = [x - ma for x in xa]
            cb = [x - mb for x in xb]
            da = (sum(p * p for p in ca)) ** 0.5
            db = (sum(q * q for q in cb)) ** 0.5
            C[i][j] = (sum(p * q for p, q in zip(ca, cb)) / (da * db)) if da and db else 0.0

    def power_iter(M, iters=400):
        k = len(M)
        v = [1.0 / math.sqrt(k)] * k
        lam = 0.0
        for _ in range(iters):
            w = [sum(M[i][j] * v[j] for j in range(k)) for i in range(k)]
            nw = math.sqrt(sum(x * x for x in w))
            if nw == 0:
                return 0.0, v
            v = [x / nw for x in w]
            lam = nw
        return lam, v

    lam, pc1 = power_iter(C)
    print(f"first eigenvalue of funding-change correlation matrix = {lam:.2f} "
          f"(of {len(syms)})  ->  PC1 explains {lam/len(syms)*100:.0f}% of the "
          f"equal-variance cross-sectional variance")
    ew = [pc1[i] / sum(pc1) for i in range(len(syms))]
    print("PC1 loadings (equalised): " +
          ", ".join(f"{syms[i][:6]}={ew[i]:.3f}" for i in range(len(syms))))

    (OUT / "funding_live.json").write_text(json.dumps(
        dict(generated=dt.datetime.now(dt.timezone.utc).isoformat(),
             per_symbol=rows,
             mean_offdiag_corr_funding_changes=grand,
             pc1_eigenvalue=lam, n_symbols=len(syms), n_settlements=n,
             pc1_loadings={syms[i]: ew[i] for i in range(len(syms))}), indent=2), "utf-8")
    print("\nwrote tools/carry/_src/funding_live.json")


if __name__ == "__main__":
    main()
