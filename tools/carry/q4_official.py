"""Q4 official/regulatory quick pass: BIS, CFTC, IOSCO, FSB, BoE on perps / leverage / liquidation."""
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
    h = h.replace("&nbsp;", " ").replace("&amp;", "&")
    h = re.sub(r"&[a-z#0-9]+;", " ", h)
    return " ".join(h.split())


G = [r"perpetual", r"leverag", r"liquidat", r"derivativ", r"short position", r"not own"]


def get(u, label, wid=900, maxh=2, chars=0):
    try:
        r = requests.get(u, headers=UA, timeout=70)
    except Exception as e:  # noqa: BLE001
        print(f"##### {label} ERR {e}\n")
        return
    t = strip(r.text)
    print(f"##### {label} [{r.status_code}] chars={len(t)}")
    if len(t) < 600:
        print("  (too short / blocked)\n")
        return
    seen = set()
    for kw in G:
        hits = list(re.finditer(kw, t, re.I))
        if hits:
            print(f"  [{kw}] {len(hits)} hits")
        for m in hits[:maxh]:
            s = max(0, m.start() - 700)
            snip = t[s:m.start() + wid]
            key = snip[100:180]
            if key in seen:
                continue
            seen.add(key)
            print(f"   >>> ...{snip}...")
            print("   ---")
    print()


TASKS = []


def add(*a):
    TASKS.append(a)


add(get, "https://www.bis.org/publ/arpdf/ar2021e3.htm", "BIS-AER-2021-Ch3")
add(get, "https://www.cftc.gov/PressRoom/PressReleases/9100-24", "CFTC-9100-24")
add(get, "https://www.fsb.org/2023/07/global-regulatory-framework-for-crypto-asset-activities-and-related-activities-2/", "FSB-GRF")
add(get, "https://www.iosco.org/library/pubdocs/pdf/IOSCOPD747.pdf", "IOSCO-PD747")
add(get, "https://www.bankofengland.co.uk/financial-stability-report/2024/march", "BoE-FSR-2024")
add(get, "https://www.esma.europa.eu/publications-and-data/interactive-single-rulebook/cryptos-assets", "ESMA-crypto")

if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = [(t, ex.submit(t[0], *t[1:])) for t in TASKS]
        for t, f in futs:
            try:
                f.result()
            except Exception as e:  # noqa: BLE001
                print(f"##### TASK {t[1]} FAILED {e!r}\n")
