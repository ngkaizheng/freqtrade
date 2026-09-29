"""Fetch a URL and store raw bytes or extracted PDF/HTML text.

Usage:
  python tools/carry/pdftext.py pdf <url> <outfile.pdf> [outfile.txt]
  python tools/carry/pdftext.py html <url> <outfile.html> [outfile.txt]
  python tools/carry/pdftext.py txt <existing-file> [outfile.txt]
"""
import pathlib
import re
import sys

import requests

S = requests.Session()
S.headers.update({"User-Agent": "Mozilla/5.0 (research-bot; mailto:research@example.com)"})


def fetch(url, tries=5, pause=5.0):
    for a in range(tries):
        try:
            r = S.get(url, timeout=120, allow_redirects=True)
        except Exception as e:  # noqa: BLE001
            print(f"!! {type(e).__name__}: {e}")
            import time

            time.sleep(pause * (a + 1))
            continue
        if r.status_code in (429, 500, 502, 503, 504):
            print(f"!! http {r.status_code}")
            import time

            time.sleep(pause * (a + 1))
            continue
        return r
    return None


def pdf_text(path):
    import pymupdf

    doc = pymupdf.open(path)
    out = []
    for i, page in enumerate(doc):
        out.append(f"\n===== PAGE {i + 1} =====\n")
        out.append(page.get_text())
    return "".join(out)


def html_text(path):
    import html as htmlmod

    t = pathlib.Path(path).read_text(encoding="utf-8", errors="replace")
    t = re.sub(r"(?is)<(script|style|svg)[^>]*>.*?</\1>", " ", t)
    t = re.sub(
        r"(?is)<(p|div|br|tr|h1|h2|h3|h4|h5|li|table|section|td|th)[^>]*>", "\n", t
    )
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    t = htmlmod.unescape(t)
    t = re.sub(r"[ \t\xa0]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n", t)
    return t


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "pdf":
        url, outp = sys.argv[2], sys.argv[3]
        r = fetch(url)
        if r is None or r.status_code != 200:
            print("FAILED", None if r is None else (r.status_code, r.text[:200]))
            sys.exit(1)
        p = pathlib.Path(outp)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(r.content)
        print("saved", p, len(r.content))
        txt = pdf_text(str(p))
        outt = sys.argv[4] if len(sys.argv) > 4 else str(p) + ".txt"
        pathlib.Path(outt).write_text(txt, encoding="utf-8")
        print("text", outt, len(txt))
    elif mode == "html":
        url, outp = sys.argv[2], sys.argv[3]
        r = fetch(url)
        if r is None or r.status_code != 200:
            print("FAILED", None if r is None else (r.status_code, r.text[:200]))
            sys.exit(1)
        p = pathlib.Path(outp)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(r.text, encoding="utf-8")
        print("saved", p, len(r.text))
        txt = html_text(str(p))
        outt = sys.argv[4] if len(sys.argv) > 4 else str(p) + ".txt"
        pathlib.Path(outt).write_text(txt, encoding="utf-8")
        print("text", outt, len(txt))
    else:
        p = sys.argv[2]
        outt = sys.argv[3] if len(sys.argv) > 3 else p + ".txt"
        txt = pdf_text(p) if p.lower().endswith(".pdf") else html_text(p)
        pathlib.Path(outt).write_text(txt, encoding="utf-8")
        print("text", outt, len(txt))
