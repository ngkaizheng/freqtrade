"""q4reg_pdf.py -- download a PDF and extract its text to a .txt file.

Usage: python q4reg_pdf.py <url> <out.txt>
"""
import sys
import io
import requests
import pathlib
from pypdf import PdfReader

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0 Safari/537.36"}
sys.stdout.reconfigure(encoding="utf-8")


def main():
    url, out = sys.argv[1], sys.argv[2]
    r = requests.get(url, headers=UA, timeout=180, allow_redirects=True)
    print("status", r.status_code, "bytes", len(r.content), "ct", r.headers.get("content-type", "")[:40])
    r.raise_for_status()
    if r.content[:4] != b"%PDF":
        print("NOT A PDF, head:", r.content[:200])
        sys.exit(1)
    pdf_path = pathlib.Path(out).with_suffix(".pdf")
    pdf_path.write_bytes(r.content)
    rd = PdfReader(io.BytesIO(r.content))
    print("pages", len(rd.pages))
    parts = []
    for i, pg in enumerate(rd.pages):
        try:
            parts.append(f"\n\n=== PAGE {i+1} ===\n" + (pg.extract_text() or ""))
        except Exception as e:
            parts.append(f"\n\n=== PAGE {i+1} ===\n[extract error {e}]")
    txt = "".join(parts)
    pathlib.Path(out).write_text(txt, encoding="utf-8")
    print("wrote", out, len(txt), "chars")


if __name__ == "__main__":
    main()
