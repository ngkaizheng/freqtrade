import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
D = r"E:\FreqTrader\freqtrade\tools\carry\_doc"
for f in sorted(os.listdir(D)):
    p = os.path.join(D, f)
    t = open(p, encoding="utf-8", errors="replace").read()
    ti = re.search(r"Title: (.*)", t)
    dead = "This article does not exist" in t
    title = (ti.group(1)[:70] if ti else "")
    print(f"{f[:46]:<48} {'DEAD' if dead else 'OK':<5} {len(t):>8}  {title}")
