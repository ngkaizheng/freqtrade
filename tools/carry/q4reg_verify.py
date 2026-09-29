"""q4reg_verify.py -- assert each intended quote appears in its source document,
so a paraphrase can never slip through as a quote.

Stage 1 (strict): whitespace collapsed, quotes/dashes/ligatures unified.
Stage 2 (loose) : ALL whitespace removed, which repairs the PDF text layer's
                  habit of breaking a word across a line ("pr otocols").
                  A stage-2 hit is reported as OK~ and means the quote is right
                  but the extraction inserted a space inside a word.

Usage: python q4reg_verify.py <specfile>
specfile lines:  <doc-stem>|<quote>
"""
import re
import sys
import pathlib

sys.stdout.reconfigure(encoding="utf-8")
D = pathlib.Path(r"E:\FreqTrader\freqtrade\tools\carry\docs")

PUNCT = {
    "’": "'", "‘": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "−": "-", "ﬁ": "fi", "ﬂ": "fl",
}


def norm(s: str) -> str:
    for a, b in PUNCT.items():
        s = s.replace(a, b)
    # extraction artefacts: a page break marker splits the sentence
    s = re.sub(r"===\s*PAGE\s+\d+\s*===\s*\d*", " ", s)
    # ... and a line break can strand a space next to a hyphen ("crypto -asset")
    s = re.sub(r"\s+-\s+", "-", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()


def squeeze(s: str) -> str:
    return re.sub(r"\s+", "", norm(s))


def main():
    spec = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()
    cache, cache2 = {}, {}
    bad = checked = 0
    for line in spec:
        line = line.rstrip()
        if not line.strip() or line.startswith("#"):
            continue
        checked += 1
        stem, quote = line.split("|", 1)
        if stem not in cache:
            raw = (D / f"{stem}.txt").read_text(encoding="utf-8", errors="replace")
            cache[stem] = norm(raw)
            cache2[stem] = squeeze(raw)
        if norm(quote) in cache[stem]:
            tag = "OK   "
        elif squeeze(quote) in cache2[stem]:
            tag = "OK~  "
        else:
            tag = "FAIL "
            bad += 1
        print(f"{tag}[{stem}] {quote[:92]}")
    print(f"\n{checked} quotes checked, {bad} FAILED "
          f"(OK~ = PDF text layer split a word across a line)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
