"""Extract He et al. v7 tables 6 and 7 verbatim (carry-strategy performance, funding decomposition)."""
import io
import re
import sys

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
UA = {"User-Agent": "Mozilla/5.0 (research; contact via local repo)"}

r = requests.get("https://arxiv.org/html/2212.06888v7", headers=UA, timeout=120)
h = r.text
print(f"status={r.status_code} len={len(h)}")


def table_before(label):
    i = h.find(label)
    if i < 0:
        print(f"!! {label!r} not found")
        return
    j = h.rfind("<table", 0, i)
    if j < 0:
        print(f"!! no <table> before {label!r}")
        return
    k = h.find("</table>", j)
    seg = h[j:k]
    rows = re.findall(r"(?is)<tr.*?</tr>", seg)
    print(f"\n===== TABLE before {label!r} ({len(rows)} rows)")
    for row in rows[:80]:
        cells = re.findall(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>", row)
        cells = [" ".join(re.sub(r"<[^>]+>", " ", c).split()) for c in cells]
        cells = [c for c in cells if c != ""]
        if cells:
            print(" | ".join(cells))


table_before("Table 6: Comparison of Different Arbitrage Trading Strategies")
table_before("Table 7: Return Decomposition")
table_before("The clamp versus a linear funding rate")
