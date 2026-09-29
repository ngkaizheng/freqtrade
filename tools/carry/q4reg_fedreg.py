"""q4reg_fedreg.py -- search the Federal Register API (official US primary source).

Usage: python q4reg_fedreg.py "term" ["term2" ...]
Prints document titles, dates, agency and official URLs.
"""
import sys
import json
import requests

sys.stdout.reconfigure(encoding="utf-8")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0 Safari/537.36"}


def main():
    for term in sys.argv[1:]:
        url = ("https://www.federalregister.gov/api/v1/documents.json"
               "?per_page=10&order=relevance&conditions%5Bterm%5D="
               + requests.utils.quote(term))
        try:
            r = requests.get(url, headers=UA, timeout=60)
            data = r.json()
        except Exception as e:
            print(f"### {term} -> ERR {e}")
            continue
        print(f"### {term}  count={data.get('count')}")
        for d in data.get("results", []):
            print("   ", d.get("publication_date"), "|", d.get("type"), "|",
                  d.get("title")[:130])
            print("      ", d.get("html_url"))


if __name__ == "__main__":
    main()
