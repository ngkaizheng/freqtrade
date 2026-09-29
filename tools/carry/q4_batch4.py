"""Q4 batch 4: dig out references + specific sections from already-fetched full texts."""
import io
import re
import sys

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
UA = {"User-Agent": "Mozilla/5.0 (research; contact via local repo)"}


def strip(h):
    h = re.sub(r"(?is)<(script|style|head|nav|footer|math)\b.*?</\1>", " ", h)
    h = re.sub(r"(?s)<!--.*?-->", " ", h)
    h = re.sub(r"<[^>]+>", " ", h)
    h = re.sub(r"&[a-z#0-9]+;", " ", h)
    return " ".join(h.split())


def sec(aid, patterns, width=1400, before=300, maxhits=3):
    url = f"https://arxiv.org/html/{aid}"
    r = requests.get(url, headers=UA, timeout=90)
    t = strip(r.text)
    print(f"##### {aid}  len={len(t)}")
    for p in patterns:
        hits = list(re.finditer(p, t, re.I))
        print(f"\n##### PATTERN {p!r}: {len(hits)} hits")
        for m in hits[:maxhits]:
            s = max(0, m.start() - before)
            print(f"  >>> {t[s:m.start()+width]}")
            print("  ---")


if __name__ == "__main__":
    sec("2212.06888v7", [
        r"Cong, Lin William",
        r"Cong, L\.",
        r"Schmeling",
        r"Christin",
        r"Ferko",
        r"Angeris",
        r"retail (trader|investor|participant|demand)",
        r"trading cost.{0,40}basis point",
        r"funding rate payments have",
    ], width=1200, maxhits=2)
