"""q4reg_counts.py -- term frequency table across every downloaded official doc.

This is the evidence for the negative finding: do the global standard setters
ever discuss the economics of perpetual funding / cash-and-carry?
"""
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

TERMS = [
    "perpetual", "funding rate", "funding", "cash-and-carry", "cash and carry",
    "carry trade", "carry", "basis trade", "basis", "delta[- ]neutral",
    "leverag", "liquidat", "margin call", "margin", "short[- ]sell", "short position",
    "counterparty", "volatil", "derivative", "tokeni[sz]", "tokenis",
]


def main():
    d = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else
                     r"E:\FreqTrader\freqtrade\tools\carry\docs")
    files = sorted(d.glob("*.txt"))
    hdr = f"{'document':<40}" + "".join(f"{t[:9]:>10}" for t in TERMS)
    print(hdr)
    print("-" * len(hdr))
    for f in files:
        if f.stat().st_size < 5000:
            continue
        t = re.sub(r"\s+", " ", f.read_text(encoding="utf-8", errors="replace"))
        row = f"{f.stem[:39]:<40}"
        for term in TERMS:
            n = len(re.findall(term, t, re.I))
            row += f"{(n if n else '.'):>10}"
        print(row)
    print("\n(columns: regex term, case-insensitive; '.' = zero occurrences)")


if __name__ == "__main__":
    main()
