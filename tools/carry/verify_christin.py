"""Verify the load-bearing Christin et al. (2022/2023) numbers from the cached PDF.

Checking, because several numbers have come through this pipeline with sign or
column errors:
  1. headline carry in bps/8h and %/yr, and whether it is GROSS
  2. their own statement that the MEDIAN funding rate is the exchange's 0.01%
  3. the 2021-07-23 leverage cut and the BTC/ETH funding collapse across it
  4. the Sharpe figure and what it is net of
"""
import pathlib
import re
import zlib

for name in ("wfa853216.pdf", "_v6_christin_carry.pdf"):
    p = pathlib.Path("tools/carry") / name
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
    # keep octal escapes visible so signs are not silently dropped
    txt = re.sub(r"\\(\d{1,3})", lambda m: f"<{int(m.group(1), 8):04d}>", txt)
    txt = txt.replace("(", " ").replace(")", " ")
    txt = re.sub(r"<0000>", "-", txt)  # minus/decimal glyph, resolved by context
    txt = re.sub(r"\s+", " ", txt)
    if "median funding rate" in txt.lower() or "Crypto Carry Trade" in txt:
        print(f"########## {name}  ({len(txt)} chars)")
        break
    print(f"{name}: no marker found ({len(txt)} chars)")

for probe, w in [
    ("median funding rate", 320),
    ("0.01% per", 300),
    ("arbitrary rate", 300),
    ("driving the profitability", 320),
    ("abstract from margin", 300),
    ("abstracts from transaction costs", 300),
    ("leverage eras", 420),
    ("2021-07-23", 420),
]:
    for m in list(re.finditer(re.escape(probe), txt, re.I))[:2]:
        i = m.start()
        print(f"\n--- {probe!r} ---")
        print(txt[max(0, i - w):i + w])
