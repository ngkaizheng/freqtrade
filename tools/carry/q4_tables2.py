"""Flat-text extraction of He et al. v7 Table 6/7 region."""
import io
import re
import sys

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
UA = {"User-Agent": "Mozilla/5.0 (research; contact via local repo)"}


def strip(h):
    h = re.sub(r"(?is)<(script|style|head|nav|footer|math)\b.*?</\1>", " ", h)
    h = re.sub(r"<[^>]+>", " ", h)
    h = re.sub(r"&[a-z#0-9]+;", " ", h)
    return " ".join(h.split())


r = requests.get("https://arxiv.org/html/2212.06888v7", headers=UA, timeout=120)
t = strip(r.text)
print(f"chars={len(t)}")
for kw in [r"Trading Strategies\s+Correct", r"Return\s+52\.55", r"MaxDD\s+-5\.69",
           r"Whenever there is a deviation large", r"four-hour", r"funding rate.{0,30}annualiz"]:
    print(f"\n##### {kw!r}")
    for m in list(re.finditer(kw, t))[:2]:
        print(f"  >>> {t[max(0, m.start()-1500):m.start()+2200]}\n  ---")
