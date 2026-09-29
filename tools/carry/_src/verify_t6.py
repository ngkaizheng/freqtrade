import html
import pathlib
import re

t = pathlib.Path("tools/carry/_src/he2026.html").read_text(encoding="utf-8")
tabs = re.findall(r"(?is)<table.*?</table>", t)
tb = tabs[24]
rows = re.findall(r"(?is)<tr.*?</tr>", tb)
cur = None
out = {}
for r in rows:
    cells = []
    for c in re.findall(r"(?is)<t[hd][^>]*>(.*?)</t[hd]>", r):
        c = re.sub(r"(?is)<math[^>]*alttext=\"(.*?)\"[^>]*>.*?</math>",
                   lambda m: html.unescape(m.group(1)), c)
        c = html.unescape(re.sub(r"(?s)<[^>]+>", " ", c))
        cells.append(re.sub(r"\s+", " ", c).strip())
    if not any(cells):
        continue
    if cells[0] in ("BTC", "ETH", "BNB", "DOGE", "ADA"):
        cur = cells[0]
        out[cur] = {}
        print()
    if cur and len(cells) >= 2 and cells[0] not in ("Sharpe ratio",):
        out[cur][cells[0]] = cells[1:5]

hdr = ["SR", "Return", "Volatility", "MaxDD", "alpha", "t_alpha", "Active%", "OtC"]
print("He et al. Table 6 - 'Carry' column (Christin et al. strategy), Binance 2020-2024")
for a in ("BTC", "ETH", "BNB", "DOGE", "ADA"):
    d = out[a]
    # order in the table: SR, Return, Volatility, MaxDD, alpha, t_alpha, Active%, OtC
    keys = ["Sharpe ratio", "Return", "Volatility", "MaxDD", "", "t", "Active %", "OtC time"]
    vals = [d.get(k, ["?"])[3] for k in
            ["Sharpe ratio", "Return", "Volatility", "MaxDD", "", "t", "Active %", "OtC time"]]
    print(f"{a:5s} SR={vals[0]:>7s} Return={vals[1]:>7s} Vol={vals[2]:>7s} "
          f"MaxDD={vals[3]:>7s} alpha={vals[4]:>8s} t_alpha={vals[5]:>6s}")
