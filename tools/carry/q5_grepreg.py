import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
D = r"E:\FreqTrader\freqtrade\tools\carry\_doc"

TARGETS = [
    ("mica_eurlex_052ff5a2.txt", r"[Aa]rticle 6[78]"),
    ("bis_qtr2212_07050815.txt", r"(?i)(leverage|derivative|liquidat|margin|perpetual)"),
    ("iosco_688_859194ae.txt", r"(?i)(leverage|derivativ|perpetual)"),
]
for fn, pat in TARGETS:
    import os
    p = os.path.join(D, fn)
    if not os.path.exists(p):
        print(fn, "MISSING")
        continue
    t = open(p, encoding="utf-8", errors="replace").read()
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    t = " ".join(t.split())
    print(f"\n########## {fn}  len={len(t)}")
    seen = set()
    for m in re.finditer(pat, t):
        s = max(0, m.start() - 320)
        frag = t[s:m.start() + 400]
        key = frag[:80]
        if key in seen:
            continue
        seen.add(key)
        print("  ...", frag, "\n")
        if len(seen) > 12:
            break
