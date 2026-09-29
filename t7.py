import requests
S=requests.Session(); S.headers.update({"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) research"})
for u in ["https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
          "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916a.htm",
          "https://www.federalreserve.gov/feeds/press_all.xml"]:
    try:
        r=S.get(u,timeout=60); print(u,"->",r.status_code,len(r.text))
    except Exception as e: print(u,"-> ERR",e)
