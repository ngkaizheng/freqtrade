"""Q4 vendor / exchange-academy / primary-design-doc pass (NON-ACADEMIC, clearly labelled)."""
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


def get(u, label, grep, chars=500, wid=700, maxh=3):
    try:
        r = requests.get(u, headers=UA, timeout=60)
    except Exception as e:  # noqa: BLE001
        print(f"##### {label} ERR {e}\n")
        return
    t = strip(r.text)
    print(f"##### {label} [{r.status_code}] chars={len(t)}")
    if len(t) < 400:
        print("   (too short / blocked)\n")
        return
    for kw in grep:
        hits = list(re.finditer(kw, t, re.I))
        if hits:
            print(f"  [{kw}] {len(hits)} hits")
        for m in hits[:maxh]:
            s = max(0, m.start() - 500)
            print(f"   >>> ...{t[s:m.start()+wid]}...")
            print("   ---")
    print()


TASKS = []


def add(*a):
    TASKS.append(a)


G_FUND = [r"funding rate", r"why .{0,40}(pay|paid)", r"insurance", r"compensat"]
add(get, "https://www.coinglass.com/learn/funding-rate", "CoinGlass-learn-funding", G_FUND)
add(get, "https://www.coinglass.com/pro/futures/FundingRate", "CoinGlass-fundingrate", G_FUND)
add(get, "https://academy.binance.com/en/articles/what-are-funding-rates-in-crypto-markets", "Binance-Academy", G_FUND)
add(get, "https://academy.binance.com/en/articles/what-are-perpetual-futures-contracts", "Binance-Academy-perps", G_FUND)
add(get, "https://www.okx.com/learn/what-are-funding-rates-in-crypto-derivatives-markets-beginners-guide", "OKX-Learn", G_FUND)
add(get, "https://www.bybit.com/en/help-center/article/Funding-Rate-Calculation", "Bybit-Help", G_FUND)
add(get, "https://www.deribit.com/pages/information/fees", "Deribit-fees", G_FUND)
add(get, "https://insights.glassnode.com/the-perpetual-futures-basis-funding-rate-explainer", "Glassnode-explain", G_FUND)
add(get, "https://www.bitmex.com/app/perpetualContractsGuide", "BitMEX-guide", G_FUND)
add(get, "https://www.coinbase.com/institutional/research-insights/research/primer-on-perpetual-futures", "Coinbase-Institutional", G_FUND)
add(get, "https://blog.kaiko.com/Insights", "Kaiko-insights", G_FUND)

if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=5) as ex:
        futs = [(t, ex.submit(t[0], *t[1:])) for t in TASKS]
        for t, f in futs:
            try:
                f.result()
            except Exception as e:  # noqa: BLE001
                print(f"##### TASK {t[1]} FAILED {e!r}\n")
