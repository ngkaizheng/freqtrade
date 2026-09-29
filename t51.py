import requests, re, html, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"})
r=S.get("https://www.federalreserve.gov/monetarypolicy/fomcprojtabl20260916.htm",timeout=60)
print("status",r.status_code)
# find the figure2 table
m=re.search(r'Figure 2\.(.{0,30000}?)Figure 3\.A', r.text, re.S)
seg=m.group(1) if m else r.text
rows=re.findall(r'<tr[^>]*>(.*?)</tr>', seg, re.S)
for row in rows:
    cells=re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', row, re.S)
    cl=[re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>','',c))).strip() for c in cells]
    if any(cl): print(" | ".join(cl))
