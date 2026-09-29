import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
D = r"E:\FreqTrader\freqtrade\tools\carry\_doc"
JOBS = [
    ("bis_crypto_chapter_9bb99d77.txt", r"(?i)(leverage|liquidat|perpetual|stablecoin|margin)"),
    ("tether_march2023_52ec95cf.txt", r"(?i)(SVB|Signature|depeg|discount|redeem|reserves|0\.9)"),
    ("congress_ftx_report_476a76fe.txt", r"(?i)(customer asset|commingl|Alameda|basis|funding|liquidat)"),
]
for fn, pat in JOBS:
    t = open(D + "\\" + fn, encoding="utf-8", errors="replace").read()
    t = re.sub(r"(?s)<(script|style)[^>]*>.*?</\1>", " ", t)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    t = " ".join(t.split())
    print("#####", fn, "len", len(t))
    print("  HEAD:", t[:260])
    seen = set()
    for m in re.finditer(pat, t):
        s = max(0, m.start() - 300)
        frag = t[s:m.start() + 450]
        if frag[:50] in seen:
            continue
        seen.add(frag[:50])
        print("  ...", frag, "\n")
        if len(seen) >= 4:
            break
    print()
