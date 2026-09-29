import re
import sys

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) research"}
for url in ("https://r.jina.ai/https://www.justice.gov/news/press-releases?search_api_fulltext=Binance",
            "https://r.jina.ai/https://www.cftc.gov/PressRoom/PressReleases?field_press_release_title_value=Binance",
            "https://r.jina.ai/https://www.justice.gov/opa/pr/binance-admits-misconduct-and-pays-penalties"):
    try:
        r = requests.get(url, headers=UA, timeout=40)
        t = re.sub(r"(?s)<[^>]+>", " ", r.text)
        t = " ".join(t.split())
        print(f"=== [{r.status_code}] {url}  len={len(t)}")
        print(t[:1800])
    except Exception as e:  # noqa: BLE001
        print(f"=== EXC {url} {e}")
    print()
