import fitz, os, re, sys
OUT = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(OUT, "_v1_mdpi-res-noV.bin")
doc = fitz.open(src)
print("pages:", doc.page_count)
pages = []
for i, p in enumerate(doc):
    pages.append(f"\n\n========== PAGE {i+1} ==========\n" + p.get_text())
full = "".join(pages)
dst = os.path.join(OUT, "_v1_math14020346.txt")
open(dst, "w", encoding="utf8").write(full)
print("chars:", len(full), "->", dst)
print(full[:6000])
