"""Strip arXiv HTML to plain text for reading/grepping."""
import html
import pathlib
import re
import sys

p = pathlib.Path(sys.argv[1])
out = pathlib.Path(sys.argv[2])
t = p.read_text(encoding="utf-8")
t = re.sub(r"(?is)<(script|style|svg)[^>]*>.*?</\1>", " ", t)
t = re.sub(r"(?is)<math[^>]*alttext=\"(.*?)\"[^>]*>.*?</math>", lambda m: " $" + html.unescape(m.group(1)) + "$ ", t)
t = re.sub(r"(?is)<(p|div|br|tr|h1|h2|h3|h4|li|table|section)[^>]*>", "\n", t)
t = re.sub(r"(?is)</(p|div|tr|h1|h2|h3|h4|li|table|section)>", "\n", t)
t = re.sub(r"(?is)</?(td|th)[^>]*>", " | ", t)
t = re.sub(r"(?s)<[^>]+>", " ", t)
t = html.unescape(t)
t = re.sub(r"[ \t\xa0]+", " ", t)
t = re.sub(r"\n\s*\n+", "\n", t)
out.write_text(t.strip(), encoding="utf-8")
print(out, len(t))
