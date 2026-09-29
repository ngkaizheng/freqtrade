import pathlib
import re
import zlib

p = pathlib.Path("tools/carry/wfa853216.pdf")
d = p.read_bytes()
out = []
for m in re.finditer(rb"stream\r?\n(.*?)endstream", d, re.S):
    try:
        out.append(zlib.decompress(m.group(1)))
    except Exception:
        pass
raw = b"\n".join(out).decode("latin-1")
shows = re.findall(r"\[((?:[^\[\]\\]|\\.)*)\]\s*TJ", raw)
lits = []
for arr in shows:
    lits += re.findall(r"\(((?:[^()\\]|\\.)*)\)", arr)
txt = "".join(lits)
txt = re.sub(r"\\(\d{1,3})", lambda m: f"<{int(m.group(1), 8):04d}>", txt)
txt = txt.replace("(", " ").replace(")", " ")
txt = re.sub(r"<0000>", "-", txt)      # minus / decimal
txt = re.sub(r"<0011>", "ff", txt)      # ff ligature
txt = re.sub(r"<0012>", "ti", txt)      # ti ligature
txt = re.sub(r"<0013>", "fl", txt)      # fl ligature
txt = re.sub(r"<[^>]*>", "", txt)
flat = re.sub(r"\s+", "", txt)           # no spaces survive extraction
print("flat chars:", len(flat))

for probe, w in [
    ("medianfundingrate", 300),
    ("arbitraryratesetbytheexchange", 260),
    ("drivingtheprofitability", 240),
    ("abstractfrommargin", 240),
    ("abstractsfromtransactioncosts", 240),
    ("pinnedtothe0", 240),
    ("dramaticallysmaller", 300),
    ("10.06", 200),
    ("17.28", 200),
]:
    hits = list(re.finditer(re.escape(probe), flat, re.I))[:2]
    if not hits:
        print(f"\n--- {probe!r}: NOT FOUND ---")
        continue
    for m in hits:
        i = m.start()
        print(f"\n--- {probe!r} ---")
        print(flat[max(0, i - w):i + w])
