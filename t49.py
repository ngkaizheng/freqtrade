import requests, re, html, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) research"})
r=S.get("https://www.federalreserve.gov/monetarypolicy/fomcprojtabl20260916.htm",timeout=60)
t=re.sub(r"<script.*?</script>","",r.text,flags=re.S); t=re.sub(r"<style.*?</style>","",t,flags=re.S)
t=re.sub(r"<[^>]+>"," ",t); t=html.unescape(t); t=re.sub(r"\s+"," ",t)
i=t.find("Figure 2")
print(t[max(0,i-2200):i+2200])
