import requests, os, re
import pymupdf
OUT = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
u = "https://mdpi-res.com/d_attachment/ijfs/ijfs-14-00103/article_deploy/ijfs-14-00103.pdf"
r = requests.get(u, headers=UA, timeout=120)
print(r.status_code, len(r.content), r.headers.get("Content-Type"))
if r.status_code == 200 and r.content[:4] == b"%PDF":
    p = os.path.join(OUT, "_v6_ijfs14050103.pdf"); open(p, "wb").write(r.content)
    d = pymupdf.open(p)
    t = "".join(f"\n\n=== PAGE {i+1} ===\n" + pg.get_text() for i, pg in enumerate(d))
    open(os.path.join(OUT, "_v6_ijfs14050103.txt"), "w", encoding="utf8").write(t)
    print("pages", d.page_count, "chars", len(t))
    # print sentences containing bps / basis points / mean funding
    for m in re.finditer(r"[^.\n]{0,240}(?:basis points|bps|Mean Spread|mean funding|mean rate)[^.\n]{0,240}\.", t, re.I):
        print("  >>", " ".join(m.group(0).split()))
