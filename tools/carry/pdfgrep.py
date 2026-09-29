"""Extract text from a local PDF and grep for numeric context.

Usage: python tools/carry\pdfgrep.py <file.pdf> [regex ...]
"""
import re
import sys

import pymupdf


def main(path, pats=None):
    doc = pymupdf.open(path)
    pages = [p.get_text() for p in doc]
    txt = "\n".join(pages)
    print(f"### {path} pages={len(pages)} chars={len(txt)}")
    if pats is None:
        print(txt[:6000])
        return
    for p in pats:
        rx = re.compile(p, re.I)
        print(f"\n===== /{p}/")
        n = 0
        for i, ptxt in enumerate(pages):
            for m in rx.finditer(ptxt):
                s = max(0, m.start() - 400)
                e = min(len(ptxt), m.end() + 500)
                print(f"\n--- p.{i+1}: ...{' '.join(ptxt[s:e].split())}...")
                n += 1
                if n >= 30:
                    break
            if n >= 30:
                break
        if n == 0:
            print("   NO HITS")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:] or None)
