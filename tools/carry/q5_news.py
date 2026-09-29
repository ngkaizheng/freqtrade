"""CoinDesk / decrypt / theblock style search via site search endpoints that are not blocked."""
import concurrent.futures as cf
import re
import sys

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) research"}
TERMS = ["october 2025 crypto flash crash liquidations",
         "USDT depeg March 2023 SVB",
         "USDC depeg March 2023",
         "funding rate arbitrage negative funding",
         "three arrows capital basis trade funding"]


def cd(term):
    out = [f"== coindesk '{term}'"]
    for base, pat in (
        ("https://www.coindesk.com/search/", r'https://www\.coindesk\.com/[a-z\-]+/\d{4}/\d{2}/\d{2}/[a-z0-9\-]+'),
        ("https://www.coindesk.com/tag/", r'https://www\.coindesk\.com/[a-z\-]+/\d{4}/\d{2}/\d{2}/[a-z0-9\-]+'),
    ):
        try:
            r = requests.get(base, params={"q": term}, headers=UA, timeout=30)
            urls = sorted(set(re.findall(pat, r.text)))
            out.append(f"  [{r.status_code}] {base} -> {len(urls)} urls")
            for u in urls[:12]:
                out.append("   " + u)
        except Exception as e:  # noqa: BLE001
            out.append(f"  EXC {base} {e}")
    return out


with cf.ThreadPoolExecutor(max_workers=5) as ex:
    for lines in ex.map(cd, TERMS):
        print("\n".join(lines))
        print()
        sys.stdout.flush()
