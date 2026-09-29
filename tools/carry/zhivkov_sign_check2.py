"""Locate the exact TJ show-strings for Zhivkov Table 2's descriptive statistics
and identify what glyph precedes each number, so the sign is not guessed."""
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

# Pull every literal string inside TJ arrays, in order, keeping escapes intact.
shows = re.findall(r"\[((?:[^\[\]\\]|\\.)*)\]\s*TJ", txt)
lits = []
for arr in shows:
    for s in re.findall(r"\(((?:[^()\\]|\\.)*)\)", arr):
        lits.append(s)


def unesc(s):
    # keep octal escapes visible so we can see what code 0 is used for
    return re.sub(r"\\(\d{1,3})", lambda m: f"<{int(m.group(1), 8):04d}>", s)


flat = "".join(unesc(x) for x in lits)
for probe in ["Descriptive", "Std", "Dev", "1.91", "1.74", "2.82", "17.24"]:
    i = flat.find(probe)
    if i >= 0:
        print(f"--- {probe!r} at {i} ---")
        print(repr(flat[max(0, i - 260):i + 260]))
        print()

# The question: does code <0000> appear immediately before a digit, and is it used
# for min/max? Count occurrences.
zeros = len(re.findall(r"<0000>", flat))
print("total <0000> glyph occurrences in extracted text:", zeros)
print("contexts of <0000> followed by a digit (i.e. a sign):")
for m in list(re.finditer(r"<0000>(?=[\d])", flat))[:20]:
    print("   ", repr(flat[max(0, m.start() - 45):m.start() + 22]))
