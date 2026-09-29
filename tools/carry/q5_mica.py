import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
D = r"E:\FreqTrader\freqtrade\tools\carry\_doc"
t = open(D + r"\mica_eurlex_052ff5a2.txt", encoding="utf-8", errors="replace").read()
t = re.sub(r"(?s)<[^>]+>", " ", t)
t = " ".join(t.split())

for pat in [r"shall not.{0,200}derivat", r"derivatives?\b.{0,160}retail",
            r"ANNEX II", r"crypto-asset derivatives", r"Article 2\b.{0,600}"]:
    print(f"\n===== PATTERN: {pat}")
    seen = set()
    for m in re.finditer(pat, t, re.I):
        s = max(0, m.start() - 400)
        frag = t[s:m.start() + 700]
        if frag[:60] in seen:
            continue
        seen.add(frag[:60])
        print("  ...", frag, "\n")
        if len(seen) >= 4:
            break
