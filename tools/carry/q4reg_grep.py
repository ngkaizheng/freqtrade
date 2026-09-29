"""q4reg_grep.py -- search a text file for a regex, print N lines of context.

Usage: python q4reg_grep.py <file> <regex> [context_chars] [max_hits]
"""
import sys
import re
import pathlib

sys.stdout.reconfigure(encoding="utf-8")


def main():
    path = sys.argv[1]
    pat = sys.argv[2]
    ctx = int(sys.argv[3]) if len(sys.argv) > 3 else 400
    maxhits = int(sys.argv[4]) if len(sys.argv) > 4 else 20
    t = pathlib.Path(path).read_text(encoding="utf-8", errors="replace")
    t = re.sub(r"[ \t]+", " ", t)
    print(f"== {path}  chars={len(t)}  pattern={pat}")
    n = 0
    for m in re.finditer(pat, t, re.I):
        a = max(0, m.start() - ctx // 2)
        b = min(len(t), m.end() + ctx)
        print(f"\n--- hit {n+1} @ {m.start()}")
        print(t[a:b])
        n += 1
        if n >= maxhits:
            print(f"\n[stopped at {maxhits} hits]")
            break
    if n == 0:
        print("[no matches]")


if __name__ == "__main__":
    main()
