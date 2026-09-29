"""Q4 vendor pass 3: archive.org snapshots of vendor/exchange funding explainers."""
import io
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
UA = {"User-Agent": "Mozilla/5.0 (research; contact via local repo)"}


def strip(h):
    h = re.sub(r"(?is)<(script|style|head|nav|svg|footer)\b.*?</\1>", " ", h)
    h = re.sub(r"(?s)<!--.*?-->", " ", h)
    h = re.sub(r"<[^>]+>", " ", h)
    h = h.replace("&nbsp;", " ").replace("&amp;", "&").replace("&#x27;", "'")
    h = re.sub(r"&[a-z#0-9]+;", " ", h)
    return " ".join(h.split())


G = [r"funding rate", r"longs pay", r"long.{0,30}pay short", r"insurance",
     r"compensat", r"premium", r"why"]

TARGETS = [
    ("Glassnode-perp-funding", "https://insights.glassnode.com/perpetual-futures-the-basis-and-funding-rate"),
    ("BinanceAcademy-funding", "https://academy.binance.com/en/articles/what-are-funding-rates-in-crypto-markets"),
    ("CoinGlass-glossary", "https://www.coinglass.com/Learn/Detail funding"),
    ("OKX-learn", "https://www.okx.com/learn/what-are-funding-rates-in-crypto-derivatives-markets-beginners-guide"),
    ("Deribit-learn", "https://support.deribit.com/hc/en-us/articles/25944711076957-Inverse-Perpetual"),
    ("Investopedia-fundingrate", "https://www.investopedia.com/terms/f/fundingrate.asp"),
    ("Coinbase-primer", "https://www.coinbase.com/institutional/research-insights/research/primer-on-perpetual-futures"),
]


def archived(url, label, chars=1000, wid=800, maxh=2):
    api = ("https://archive.org/wayback/available?url=" + requests.utils.quote(url, safe=""))
    try:
        r = requests.get(api, headers=UA, timeout=45)
        snap = (r.json().get("archived_snapshots") or {}).get("closest", {}).get("url")
    except Exception as e:  # noqa: BLE001
        print(f"##### {label} AVAIL-ERR {e}\n")
        return
    if not snap:
        print(f"##### {label} NO SNAPSHOT\n")
        return
    try:
        r2 = requests.get(snap, headers=UA, timeout=90)
    except Exception as e:  # noqa: BLE001
        print(f"##### {label} FETCH-ERR {e}\n")
        return
    t = strip(r2.text)
    print(f"##### {label} [{r2.status_code}] {snap} chars={len(t)}")
    found = False
    for kw in G:
        hits = list(re.finditer(kw, t, re.I))
        if hits:
            found = True
            print(f"  [{kw}] {len(hits)} hits")
        for m in hits[:maxh]:
            s = max(0, m.start() - 550)
            print(f"   >>> ...{t[s:m.start()+wid]}...")
            print("   ---")
    if not found:
        print("  (no keyword hits) " + t[:chars])
    print()


if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = [(t, ex.submit(archived, t[1], t[0])) for t in TARGETS]
        for t, f in futs:
            try:
                f.result()
            except Exception as e:  # noqa: BLE001
                print(f"##### TASK {t[0]} FAILED {e!r}\n")
