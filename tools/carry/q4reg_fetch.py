"""q4reg_fetch.py -- scratch fetcher for the official/regulatory literature review.

Usage:  python q4reg_fetch.py <url> <outfile> [html|pdf]
Writes raw bytes (pdf) or normalized plain text (html) to <outfile>.
No bs4 available in this venv, so HTML is stripped with a regex pass that
turns block-level tags into newlines.
"""
import sys
import re
import html as _html
import requests
from pathlib import Path

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/pdf,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}

DROP = re.compile(
    r"<(script|style|noscript|svg|head)\b.*?</\1>", re.I | re.S)
BLOCK = re.compile(
    r"</?(p|div|br|tr|li|h[1-6]|section|article|td|th|blockquote|pre|"
    r"table|ul|ol|dl|dd|dt|figcaption|hr)\b[^>]*>", re.I)
TAG = re.compile(r"<[^>]+>", re.S)


def to_text(s: str) -> str:
    s = DROP.sub(" ", s)
    s = BLOCK.sub("\n", s)
    s = TAG.sub("", s)
    s = _html.unescape(s)
    s = s.replace("\r", "\n")
    s = re.sub(r"[ \t\xa0]+", " ", s)
    s = re.sub(r" *\n *", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def fetch(url, mode="html"):
    r = requests.get(url, headers=UA, timeout=90, allow_redirects=True)
    print(f"status={r.status_code} bytes={len(r.content)} ct={r.headers.get('content-type','')[:40]} final={r.url}")
    r.raise_for_status()
    if mode == "pdf":
        if r.content[:4] != b"%PDF":
            print("WARNING not a PDF, first 120 bytes:", r.content[:120])
        return r.content
    return to_text(r.text).encode("utf-8")


def main():
    url, out = sys.argv[1], sys.argv[2]
    mode = sys.argv[3] if len(sys.argv) > 3 else "html"
    data = fetch(url, mode)
    Path(out).write_bytes(data)
    print(f"wrote {out} ({len(data)} bytes)")


if __name__ == "__main__":
    main()
