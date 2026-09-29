"""q4reg_ddg.py -- find URLs without the web_search tool, via DuckDuckGo HTML.

Usage: python q4reg_ddg.py "query" ["query2" ...]
Prints result titles + URLs. HTML only; a search engine is a locator for a
primary document, not a citable source -- always fetch the primary document.
"""
import sys
import re
import html as _html
import requests

sys.stdout.reconfigure(encoding="utf-8")
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
}


def main():
    for q in sys.argv[1:]:
        url = "https://html.duckduckgo.com/html/"
        try:
            r = requests.post(url, data={"q": q}, headers=UA, timeout=60)
        except Exception:
            try:
                r = requests.get(url + "?q=" + requests.utils.quote(q), headers=UA, timeout=60)
            except Exception as e:
                print(f"### {q} -> ERR {e}")
                continue
        print(f"### {q}  status={r.status_code} len={len(r.text)}")
        hits = re.findall(r'<a rel="nofollow" class="result__a" href="([^"]+)"[^>]*>(.*?)</a>', r.text, re.S)
        if not hits:
            hits = re.findall(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', r.text, re.S)
        for u, t in hits[:10]:
            t = re.sub(r"<[^>]+>", "", t)
            if "uddg=" in u:
                u = requests.utils.unquote(u.split("uddg=")[1].split("&")[0])
            print("   ", _html.unescape(t.strip())[:110], "\n      ", u)


if __name__ == "__main__":
    main()
