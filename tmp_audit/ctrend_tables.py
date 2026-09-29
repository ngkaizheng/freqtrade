"""Extract CTREND Tables 8 and 9 -- the panels that matter for a liquid universe."""

import re
from pathlib import Path

text = Path("tmp_audit/ctrend.txt").read_text(encoding="utf-8")
text = " ".join(text.split())
# the PDF text layer carries non-cp1252 glyphs; keep only printable ASCII-ish
text = text.encode("ascii", "ignore").decode("ascii")

for label, anchor, span in [
    ("TABLE 8 -- big and liquid", "Table 8 reports", 4200),
    ("TABLE 9 -- transaction costs", "Table 9 reports", 3800),
    ("BETC / breakeven", "BETC", 1600),
]:
    i = text.find(anchor)
    print("=" * 78)
    print(label)
    print("=" * 78)
    if i < 0:
        print("  (anchor not found)")
        continue
    print(text[i:i + span])
    print()

print("=" * 78)
print("SHARPE-RATIO SENTENCES")
print("=" * 78)
for m in re.finditer(r"[^.]{0,260}Sharpe ratio[^.]{0,260}\.", text):
    print(" *", m.group(0).strip()[:520])
    print()
