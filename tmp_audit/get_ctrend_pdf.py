"""Pull the CTREND paper's own numbers rather than trusting a paraphrase.

The abstract is already enough to overturn one of this project's claims
("the effect cannot be subsumed by known factors ... survives the impact of
transaction costs ... persists in big and liquid coins"). But the effect SIZE
is what determines whether the corrected 0.95-Sharpe benchmark is reachable,
so the numbers have to come from the paper.
"""

import io
import re
import urllib.request
from pathlib import Path

from pypdf import PdfReader

URL = ("https://www.cambridge.org/core/services/aop-cambridge-core/content/view/"
       "4C1509ACBA33D5DCAF0AC24379148178/S0022109024000747a.pdf/"
       "div-class-title-a-trend-factor-for-the-cross-section-of-cryptocurrency-returns-div.pdf")
OUT = Path("tmp_audit/ctrend.pdf")

req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
raw = urllib.request.urlopen(req, timeout=120).read()
OUT.write_bytes(raw)
print(f"downloaded {len(raw):,} bytes -> {OUT}")

reader = PdfReader(io.BytesIO(raw))
print(f"pages: {len(reader.pages)}")
text = "\n".join((p.extract_text() or "") for p in reader.pages)
Path("tmp_audit/ctrend.txt").write_text(text, encoding="utf-8")
print(f"text: {len(text):,} chars")

# ---- pull the numbers that matter
print()
print("=" * 74)
print("KEY PASSAGES")
print("=" * 74)
patterns = [
    r"transaction cost[^.]{0,260}\.",
    r"net of[^.]{0,220}\.",
    r"\bbps\b[^.]{0,200}\.",
    r"t-statistic[^.]{0,200}\.",
    r"big and liquid[^.]{0,240}\.",
    r"largest\s+\d+\s+coins?[^.]{0,220}\.",
    r"weekly[^.]{0,200}\.",
]
seen = set()
for pat in patterns:
    for m in re.finditer(pat, text, flags=re.I):
        s = " ".join(m.group(0).split())
        key = s[:70]
        if key in seen:
            continue
        seen.add(key)
        print(" *", s[:300])
        if len(seen) > 34:
            break

print()
print("=" * 74)
print("ABSTRACT")
print("=" * 74)
m = re.search(r"Abstract(.{0,1400})", text, flags=re.S)
print(" ".join(m.group(1).split()) if m else "(not located)")
