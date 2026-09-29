"""Extract He et al. v7 Table 6 as proper rows (verify the corrected carry numbers)."""
import io
import re
import sys

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
UA = {"User-Agent": "Mozilla/5.0 (research; contact via local repo)"}

r = requests.get("https://arxiv.org/html/2212.06888v7", headers=UA, timeout=120)
h = r.text

# find every <table> with its caption, and locate the one whose caption mentions
# "Comparison of Different Arbitrage Trading Strategies"
for m in re.finditer(r"(?is)<figure.*?</figure>", h):
    seg = m.group(0)
    if "Comparison of Different Arbitrage Trading Strategies" in seg:
        tbl = re.search(r"(?is)<table.*?</table>", seg)
        if not tbl:
            continue
        rows = re.findall(r"(?is)<tr.*?</tr>", tbl.group(0))
        print(f"rows={len(rows)}")
        for row in rows:
            cells = re.findall(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>", row)
            cells = [" ".join(re.sub(r"<[^>]+>", " ", c).split()) for c in cells]
            cells = [c for c in cells if c]
            if cells:
                print(" || ".join(cells))
        break
else:
    print("!! figure not matched; falling back to raw caption search")
    i = h.find("Comparison of Different Arbitrage Trading Strategies")
    print("caption idx", i)
    # print all tables with >=20 rows
    for k, t in enumerate(re.findall(r"(?is)<table.*?</table>", h)):
        rows = re.findall(r"(?is)<tr.*?</tr>", t)
        if len(rows) >= 20:
            print(f"\n--- table {k}: {len(rows)} rows ---")
            for row in rows[:40]:
                cells = re.findall(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>", row)
                cells = [" ".join(re.sub(r"<[^>]+>", " ", c).split()) for c in cells]
                cells = [c for c in cells if c]
                if cells:
                    print(" || ".join(cells))
