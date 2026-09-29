"""Extract text from Note-From-Wechat.pdf (190 pages).

Writes a plain-text dump plus a page-count/text-density report so I can tell
whether extraction succeeded or whether the pages are images needing OCR.
"""

import os
import re

from pypdf import PdfReader

PATH = "docs-myself/Note-From-Wechat.pdf"
OUT = "user_data/note_from_wechat.txt"

reader = PdfReader(PATH)
n = len(reader.pages)
print(f"pages: {n}")

pages_text = []
empty = 0
for i, page in enumerate(reader.pages):
    try:
        t = page.extract_text() or ""
    except Exception as e:
        t = ""
        print(f"  page {i+1}: extract error {type(e).__name__}")
    if len(t.strip()) < 20:
        empty += 1
    pages_text.append(t)
    if (i + 1) % 25 == 0:
        print(f"  ...{i+1}/{n} pages processed")

total_chars = sum(len(t) for t in pages_text)
print(f"\ntotal characters extracted : {total_chars:,}")
print(f"pages with <20 chars       : {empty}/{n}")
print(f"avg chars/page             : {total_chars/n:,.0f}")

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    for i, t in enumerate(pages_text, 1):
        f.write(f"\n\n===== PAGE {i} =====\n")
        f.write(t)
print(f"\nwrote {OUT}")

# show a preview so the content type is visible
print("\n--- PREVIEW (first 2 non-empty pages) ---")
shown = 0
for i, t in enumerate(pages_text, 1):
    if len(t.strip()) >= 20:
        print(f"\n[page {i}]")
        print(t.strip()[:1500])
        shown += 1
        if shown >= 2:
            break
if shown == 0:
    print("NO TEXT EXTRACTED -- pages are likely images; OCR required.")
