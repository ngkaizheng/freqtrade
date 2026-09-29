import requests, re, html, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) research"})
r=S.get("https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916a.htm",timeout=60)
t=re.sub(r"<script.*?</script>","",r.text,flags=re.S)
t=re.sub(r"<style.*?</style>","",t,flags=re.S)
t=re.sub(r"<[^>]+>"," ",t); t=html.unescape(t); t=re.sub(r"\s+"," ",t)
for kw in ["federal funds rate","Voting for","voted for","target range","basis point"]:
    for m in re.finditer(kw, t, re.I):
        print(">>>",kw,"@",m.start(),":", t[max(0,m.start()-900):m.start()+700])
        print("="*100)
        break
