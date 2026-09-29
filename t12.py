import requests, re, html, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) research"})
r=S.get("https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",timeout=60)
t=re.sub(r"<script.*?</script>","",r.text,flags=re.S)
t=re.sub(r"<[^>]+>"," ",t); t=html.unescape(t); t=re.sub(r"\s+"," ",t)
# find 2026 calendar section
for m in re.finditer(r"2026 FOMC Meetings|October 2[0-9]|2026 FOMC", t):
    print(">>>", t[max(0,m.start()-300):m.start()+1400]); print("="*100); break
i=t.find("October")
print("OCT SEG:", t[max(0,i-200):i+900])
