"""Enumerate Deribit Insights + CoinDesk + Kaiko article URLs by search term."""
import concurrent.futures as cf
import re
import sys

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) research"}
TERMS = ["funding", "basis", "cash and carry", "flash crash", "liquidation",
         "perpetual", "carry trade", "October 2025"]


def deribit(term):
    out = [f"== deribit '{term}'"]
    for page in (1, 2):
        try:
            r = requests.get(
                "https://insights.deribit.com/wp-json/wp/v2/posts",
                params={"search": term, "per_page": 20, "page": page,
                        "_fields": "title,link,date"},
                headers=UA, timeout=30)
        except Exception as e:  # noqa: BLE001
            out.append(f"  EXC {e}")
            return out
        if r.status_code != 200:
            out.append(f"  [{r.status_code}]")
            break
        for p in r.json():
            t = re.sub(r"<[^>]+>", "", (p.get("title") or {}).get("rendered", ""))
            out.append(f"  {p.get('date','')[:10]}  {t[:95]}  {p.get('link')}")
    return out


def coindesk(term):
    out = [f"== coindesk '{term}'"]
    try:
        r = requests.get("https://www.coindesk.com/search", params={"q": term},
                         headers=UA, timeout=30)
        out.append(f"  [{r.status_code}] len={len(r.text)}")
        urls = sorted(set(re.findall(
            r'https://www\.coindesk\.com/[a-z\-]+/\d{4}/\d{2}/\d{2}/[a-z0-9\-]+', r.text)))
        for u in urls[:15]:
            out.append("  " + u)
    except Exception as e:  # noqa: BLE001
        out.append(f"  EXC {e}")
    return out


def kaiko(term):
    out = [f"== kaiko '{term}'"]
    try:
        r = requests.get("https://blog.kaiko.com/", headers=UA, timeout=30)
        urls = sorted(set(re.findall(r'https://blog\.kaiko\.com/[a-z0-9\-]+/?', r.text)))
        out.append(f"  [{r.status_code}] {len(urls)} urls on index")
    except Exception as e:  # noqa: BLE001
        out.append(f"  EXC {e}")
    return out


jobs = []
for t in TERMS:
    jobs.append((deribit, t))
for t in ("flash crash", "liquidation", "USDT depeg"):
    jobs.append((coindesk, t))
jobs.append((kaiko, "index"))

with cf.ThreadPoolExecutor(max_workers=6) as ex:
    for lines in ex.map(lambda j: j[0](j[1]), jobs):
        print("\n".join(lines))
        print()
        sys.stdout.flush()
