"""Q4 vendor pass 2: static-friendly vendor / design-doc pages."""
import io
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
      "Accept-Language": "en-US,en;q=0.9"}


def strip(h):
    h = re.sub(r"(?is)<(script|style|head|nav|svg|footer)\b.*?</\1>", " ", h)
    h = re.sub(r"(?s)<!--.*?-->", " ", h)
    h = re.sub(r"<[^>]+>", " ", h)
    h = h.replace("&nbsp;", " ").replace("&amp;", "&").replace("&#x27;", "'")
    h = re.sub(r"&[a-z#0-9]+;", " ", h)
    return " ".join(h.split())


def get(u, label, grep=(), chars=2500, wid=800, maxh=2):
    try:
        r = requests.get(u, headers=UA, timeout=60)
    except Exception as e:  # noqa: BLE001
        print(f"##### {label} ERR {e}\n")
        return
    t = strip(r.text)
    print(f"##### {label} [{r.status_code}] chars={len(t)}")
    if len(t) < 400:
        print("   (too short / blocked / JS-rendered)\n")
        return
    found = False
    for kw in grep:
        hits = list(re.finditer(kw, t, re.I))
        if hits:
            found = True
            print(f"  [{kw}] {len(hits)} hits")
        for m in hits[:maxh]:
            s = max(0, m.start() - 500)
            print(f"   >>> ...{t[s:m.start()+wid]}...")
            print("   ---")
    if not found:
        print("  (no keyword hits; first 1200 chars below)")
        print("  " + t[:1200])
    print()


TASKS = []


def add(*a):
    TASKS.append(a)


G = [r"funding rate", r"long.{0,25}pay", r"short.{0,25}receiv", r"insurance", r"compensat", r"why"]
add(get, "https://www.coinbase.com/institutional/research-insights/research/primer-on-perpetual-futures",
    "Coinbase-Institutional-primer", G)
add(get, "https://www.glassnode.com/academics", "Glassnode-academics", G)
add(get, "https://docs.glassnode.com/basic-api/endpoints/derivatives/funding-rate-history", "Glassnode-docs", G)
add(get, "https://help.bybit.com/hc/en-us/articles/900000181046-Funding-Rate-Calculation", "Bybit-Help2", G)
add(get, "https://www.binance.com/en/support/faq/detail/360033525031", "Binance-FAQ-funding", G)
add(get, "https://www.coinbase.com/learn/crypto-funding-rates", "Coinbase-learn", G)
add(get, "https://www.investopedia.com/terms/f/fundingrate.asp", "Investopedia", G)
add(get, "https://www.bitmex.com/fees", "BitMEX-fees", G)
add(get, "https://www.kaiko.com/insights", "Kaiko-insights2", G)
add(get, "https://research.kaiko.com/insights", "Kaiko-research", G)

if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=5) as ex:
        futs = [(t, ex.submit(t[0], *t[1:])) for t in TASKS]
        for t, f in futs:
            try:
                f.result()
            except Exception as e:  # noqa: BLE001
                print(f"##### TASK {t[1]} FAILED {e!r}\n")
