import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
D = r"E:\FreqTrader\freqtrade\tools\carry\_doc"


def flat(fn):
    t = open(D + "\\" + fn, encoding="utf-8", errors="replace").read()
    t = re.sub(r"(?s)<(script|style)[^>]*>.*?</\1>", " ", t)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    return " ".join(t.split())


print("########## CFTC 8482-22 (Binance / FTX)")
t = flat("cftc_8482_22_77b53dbd.txt")
i = t.find("8482")
print(t[max(0, i - 200):i + 3200])

print("\n\n########## MiCA recitals on retail / derivatives")
t = flat("mica_eurlex_052ff5a2.txt")
for m in re.finditer(r"(?i)\(22\)|retail (?:client|customer|investor)|investment-like", t):
    s = max(0, m.start() - 420)
    print("  ...", t[s:m.start() + 620], "\n")

print("\n########## SEC 2022-78 (FTX / enforcement)")
t = flat("sec_202278_b628acb7.txt")
m = re.search(r"(?i)(customer|commingl|unlawful|charges|penalt)", t)
print(t[max(0, m.start() - 100):m.start() + 2400] if m else t[:1500])
