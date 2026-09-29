"""q4reg_sitemap.py -- pull a sitemap (plain or index) and list URLs matching a regex.

Usage: python q4reg_sitemap.py <url> <regex> [regex2 ...]
Follows sitemap index entries one level deep.
"""
import re
import sys
import gzip
import requests

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"E:\FreqTrader\freqtrade\tools\carry")
from q4reg_fetch import UA  # noqa: E402


def get(u):
    r = requests.get(u, headers=UA, timeout=120)
    r.raise_for_status()
    if r.content[:2] == b"\x1f\x8b":
        r._content = gzip.decompress(r.content)
        return r._content.decode("utf-8", "replace")
    return r.text


def main():
    root = sys.argv[1]
    pats = [re.compile(p, re.I) for p in sys.argv[2:]]
    seen = set()
    try:
        txt = get(root)
    except Exception as e:
        print(f"### {root} -> ERR {e}")
        return
    print(f"### {root} len={len(txt)}")
    locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", txt)
    if locs and all(l.endswith(".xml") or l.endswith(".xml.gz") for l in locs[:5]):
        for l in locs[:20]:
            try:
                sub = get(l)
            except Exception as e:
                print("  sub ERR", l, e)
                continue
            for u in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sub):
                seen.add(u)
    else:
        seen.update(locs)
    print("  total urls:", len(seen))
    n = 0
    for u in sorted(seen):
        if any(p.search(u) for p in pats):
            print("   ", u)
            n += 1
    if n == 0:
        print("    [no match]")


if __name__ == "__main__":
    main()
