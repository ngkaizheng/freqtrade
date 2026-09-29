"""Targeted fetch + extract helper: grab a URL, strip HTML, print matching context.

Usage: python tools/carry/grab.py <url> [regex ...]
       python tools/carry/grab.py --pdf <url> <outfile.pdf>
"""
import re
import sys

import requests

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
}


def get(url, tries=3):
    for a in range(tries):
        try:
            r = requests.get(url, headers=UA, timeout=60, allow_redirects=True)
            if r.status_code == 200:
                return r
            print(f"   [{r.status_code}] {url}")
        except Exception as e:  # noqa: BLE001
            print(f"   !! {e}")
    return None


def strip(html):
    html = re.sub(r"(?is)<(script|style|svg|noscript)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?is)<br\s*/?>", "\n", html)
    html = re.sub(r"(?is)</(p|div|tr|li|h[1-6]|section)>", "\n", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    import html as H

    txt = H.unescape(html)
    txt = re.sub(r"[ \t\xa0]+", " ", txt)
    txt = re.sub(r"\n\s*\n+", "\n", txt)
    return txt


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[0] == "--pdf":
        r = get(args[1])
        if r is not None:
            open(args[2], "wb").write(r.content)
            print(f"wrote {args[2]} {len(r.content)} bytes")
        sys.exit()
    url = args[0]
    pats = args[1:] or [
        r"funding", r"basis", r"annuali[sz]ed", r"Sharpe", r"bps", r"basis point",
        r"per 8", r"8 hour", r"eight hour", r"carry", r"premium", r"annualized",
    ]
    r = get(url)
    if r is None:
        print("FAILED")
        sys.exit()
    ct = r.headers.get("content-type", "")
    if "pdf" in ct.lower() or r.content[:4] == b"%PDF":
        print("GOT PDF - use --pdf")
        sys.exit()
    txt = strip(r.text)
    print(f"### {url}  len={len(txt)}")
    for p in pats:
        try:
            rx = re.compile(p, re.I)
        except re.error:
            continue
        hits = [m for m in rx.finditer(txt)]
        if not hits:
            print(f"\n-- /{p}/  NO HITS")
            continue
        print(f"\n-- /{p}/  {len(hits)} hits")
        for m in hits[:25]:
            s = max(0, m.start() - 320)
            e = min(len(txt), m.end() + 420)
            print("   ...", " ".join(txt[s:e].split()), "...")
