"""Extract the Nth HTML table (as rows of cells) from a saved HTML file."""
import html
import pathlib
import re
import sys

src = pathlib.Path(sys.argv[1])
want = [int(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else None
t = src.read_text(encoding="utf-8")
tables = re.findall(r"(?is)<table.*?</table>", t)
for i, tb in enumerate(tables):
    if want is not None and i not in want:
        continue
    rows = re.findall(r"(?is)<tr.*?</tr>", tb)
    print(f"\n########## TABLE {i}  ({len(rows)} rows)")
    for r in rows:
        cells = re.findall(r"(?is)<t[hd][^>]*>(.*?)</t[hd]>", r)
        out = []
        for c in cells:
            c = re.sub(r"(?is)<math[^>]*alttext=\"(.*?)\"[^>]*>.*?</math>", lambda m: html.unescape(m.group(1)), c)
            c = re.sub(r"(?s)<[^>]+>", " ", c)
            c = html.unescape(c)
            c = re.sub(r"\s+", " ", c).strip()
            out.append(c)
        if any(out):
            print(" | ".join(out))
