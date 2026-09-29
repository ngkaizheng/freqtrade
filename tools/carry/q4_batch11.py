"""Q4 batch 11: last attempt at Christin et al. 'The crypto carry trade'."""
import io
import re
import sys

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"}


def strip(h):
    h = re.sub(r"(?is)<(script|style|head|nav|footer)\b.*?</\1>", " ", h)
    h = re.sub(r"<[^>]+>", " ", h)
    h = re.sub(r"&[a-z#0-9]+;", " ", h)
    return " ".join(h.split())


def ddg(q):
    try:
        r = requests.post("https://html.duckduckgo.com/html/", data={"q": q},
                          headers=UA, timeout=40)
        t = strip(r.text)
        print(f"===== DDG {q!r} [{r.status_code}] chars={len(t)}")
        print(t[:3500])
    except Exception as e:  # noqa: BLE001
        print(f"===== DDG {q!r} ERR {e}")
    print()


def try_get(u, label, grep=None, chars=3500):
    try:
        r = requests.get(u, headers=UA, timeout=60)
    except Exception as e:  # noqa: BLE001
        print(f"===== {label} ERR {e}\n")
        return
    t = strip(r.text)
    print(f"===== {label} [{r.status_code}] chars={len(t)}")
    if grep:
        for kw in grep:
            for m in list(re.finditer(kw, t, re.I))[:3]:
                s = max(0, m.start() - 700)
                print(f"  >>> {t[s:m.start()+1200]}\n  ---")
    else:
        print(t[:chars])
    print()


if __name__ == "__main__":
    ddg('"crypto carry trade" Christin Routledge Soska Zetlin-Jones pdf')
    ddg('"The crypto carry trade" bitcoin perpetual differences of opinion leverage')
    try_get("https://www.nick-soska.com/", "soska-site")
    try_get("https://sites.google.com/site/nicksoska/", "soska-sites")
    try_get("https://www.aqr.com/Insights/Journal/Commentary/Crypto-Carry", "aqr-commentary")
