"""Q4 batch 3: fetch full texts / abstracts of the key academic works."""
import io
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
UA = {"User-Agent": "Mozilla/5.0 (research; contact via local repo)"}


def _get(url, timeout=60):
    return requests.get(url, headers=UA, timeout=timeout)


def strip(h):
    h = re.sub(r"(?is)<(script|style|head|nav|footer|math)\b.*?</\1>", " ", h)
    h = re.sub(r"(?s)<!--.*?-->", " ", h)
    h = re.sub(r"<[^>]+>", " ", h)
    h = h.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    h = h.replace("&#x2019;", "'").replace("&#x201C;", '"').replace("&#x201D;", '"')
    h = re.sub(r"&[a-z#0-9]+;", " ", h)
    return " ".join(h.split())


def arxiv_html(aid, chars=14000, grep=None):
    """Try the arXiv HTML5 rendering, else ar5iv."""
    for url in (f"https://arxiv.org/html/{aid}", f"https://ar5iv.labs.arxiv.org/html/{aid}"):
        try:
            r = _get(url)
        except Exception as e:  # noqa: BLE001
            print(f"===== ARXIV-HTML {aid} ERR {url}: {e}")
            continue
        if r.status_code != 200 or len(r.text) < 5000:
            print(f"===== ARXIV-HTML {aid} [{r.status_code}] {url} len={len(r.text)}")
            continue
        t = strip(r.text)
        print(f"===== ARXIV-HTML {aid} OK {url} chars={len(t)}")
        if grep:
            for kw in grep:
                for m in re.finditer(kw, t, re.I):
                    s = max(0, m.start() - 500)
                    print(f"  ...[{kw}]... {t[s:m.start()+900]}")
                    print("  ---")
        else:
            print(t[:chars])
        print()
        return
    print(f"===== ARXIV-HTML {aid}: no HTML rendering available\n")


def fetch(url, chars=6000, label=None, grep=None):
    try:
        r = _get(url)
    except Exception as e:  # noqa: BLE001
        print(f"===== GET {label or url} ERR {e}\n")
        return
    t = strip(r.text)
    print(f"===== GET {label or url} [{r.status_code}] chars={len(t)}")
    if grep:
        for kw in grep:
            hits = list(re.finditer(kw, t, re.I))
            print(f"  [{kw}] {len(hits)} hits")
            for m in hits[:6]:
                s = max(0, m.start() - 600)
                print(f"  ...{t[s:m.start()+900]}")
                print("  ---")
    else:
        print(t[:chars])
    print()


if __name__ == "__main__":
    G = ["convenience yield", "risk premi", "liquidation", "retail", "service fee", "insurance",
         "leverage", "sentiment", "short"]
    with ThreadPoolExecutor(max_workers=6) as ex:
        f1 = ex.submit(arxiv_html, "2212.06888v7", 0, G)
        f2 = ex.submit(arxiv_html, "2609.05433v1", 0, G)
        f3 = ex.submit(arxiv_html, "2310.11771v3", 0, G)
        f4 = ex.submit(fetch, "https://www.nber.org/papers/w33640", 9000)
        f5 = ex.submit(fetch, "https://doi.org/10.1287/mnsc.2024.05069", 6000, "CryptoCarry-MS")
        f6 = ex.submit(fetch, "https://arxiv.org/abs/2203.07733", 6000, "arxiv2203.07733?")
        for f in (f1, f2, f3, f4, f5, f6):
            f.result()
