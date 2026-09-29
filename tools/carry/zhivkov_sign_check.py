"""Resolve the sign of Zhivkov (2026) Table 2 funding rates.

My first text extraction dropped a minus-sign glyph, rendering the rates as
positive. Check the raw PDF content stream for the glyph actually used.
"""
import pathlib
import re
import zlib

d = pathlib.Path("tools/carry/_src/mdpi_2026.pdf").read_bytes()
out = []
for m in re.finditer(rb"stream\r?\n(.*?)endstream", d, re.S):
    try:
        out.append(zlib.decompress(m.group(1)))
    except Exception:
        pass
txt = b"\n".join(out).decode("latin-1")

# Find the region around the descriptive-statistics table
i = txt.find("1.91")
print("=== raw content-stream window around '1.91' ===")
print(repr(txt[max(0, i - 700):i + 400]))
print()

# The minus sign in this font is likely octal-escaped. Collect the byte that
# immediately precedes "1.91" in the Tj/TJ show strings.
for m in re.finditer(r"(.)\s*(1\.91|1\.74|1\.00|0\.80)", txt):
    ctx = txt[max(0, m.start() - 60):m.end() + 10]
    print(repr(ctx))
    print("   leading char before number:", repr(m.group(1)))
