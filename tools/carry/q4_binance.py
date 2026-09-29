"""Q4: verify Binance's premium-index interest-rate component from primary docs (archive.org)."""
import io
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


G = [r"[Ii]nterest [Rr]ate", r"0\.0[0-3]%", r"Premium Index", r"clamp",
     r"funding rate.{0,80}(cap|limit)", r"three months", r"annualiz"]


def archived(url, label, wid=900, maxh=3):
    api = "https://archive.org/wayback/available?url=" + requests.utils.quote(url, safe="")
    try:
        r = requests.get(api, headers=UA, timeout=45)
        snap = (r.json().get("archived_snapshots") or {}).get("closest", {}).get("url")
    except Exception as e:  # noqa: BLE001
        print(f"##### {label} AVAIL-ERR {e}\n")
        return
    if not snap:
        print(f"##### {label} NO SNAPSHOT for {url}\n")
        return
    try:
        r2 = requests.get(snap, headers=UA, timeout=90)
    except Exception as e:  # noqa: BLE001
        print(f"##### {label} FETCH-ERR {e}\n")
        return
    t = strip(r2.text)
    print(f"##### {label} [{r2.status_code}] {snap} chars={len(t)}")
    seen = set()
    for kw in G:
        hits = list(re.finditer(kw, t))
        if hits:
            print(f"  [{kw}] {len(hits)} hits")
        for m in hits[:maxh]:
            s = max(0, m.start() - 600)
            snip = t[s:m.start() + wid]
            if snip[:80] in seen:
                continue
            seen.add(snip[:80])
            print(f"   >>> ...{snip}...")
            print("   ---")
    print()


T = [
    ("Binance-FAQ-fundingrate", "https://www.binance.com/en/support/faq/detail/360033525031"),
    ("Binance-FAQ-fundingrate2", "https://www.binance.com/en/support/faq/360033525031"),
    ("Binance-Perp-funding-doc", "https://www.binance.com/en/futures/funding-history/perpetual/real-time-funding-rate"),
    ("Binance-perps-FAQ", "https://www.binance.com/en/futures/perp-contracts/"),
]

if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = [(t, ex.submit(archived, t[1], t[0])) for t in T]
        for t, f in futs:
            try:
                f.result()
            except Exception as e:  # noqa: BLE001
                print(f"##### TASK {t[0]} FAILED {e!r}\n")
