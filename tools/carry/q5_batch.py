"""Doc fetch, short timeouts, writes each result to tools/carry/_doc/<label>.txt, prints a summary."""
import hashlib
import os
import sys
import concurrent.futures as cf

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) research"}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_doc")
os.makedirs(OUT, exist_ok=True)


def one(label, url):
    res = {"label": label, "url": url, "tries": []}
    cands = [url, "https://r.jina.ai/" + url]
    for c in cands:
        try:
            r = requests.get(c, headers=UA, timeout=35, allow_redirects=True)
            res["tries"].append((c[:120], r.status_code, len(r.text)))
            if r.status_code == 200 and len(r.text.strip()) > 300:
                fn = os.path.join(OUT, f"{label}_{hashlib.md5(url.encode()).hexdigest()[:8]}.txt")
                with open(fn, "w", encoding="utf-8") as fh:
                    fh.write(f"SOURCE_URL: {c}\nHTTP: {r.status_code}  LEN: {len(r.text)}\n\n")
                    fh.write(r.text)
                res["file"] = fn
                return res
        except Exception as e:  # noqa: BLE001
            res["tries"].append((c[:120], "EXC", str(e)[:120]))
    return res


def job(spec):
    label, url = spec
    return one(label, url)


if __name__ == "__main__":
    specs = []
    for line in sys.stdin:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        label, url = line.split("\t", 1)
        specs.append((label, url))
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        for res in ex.map(job, specs):
            print(res["label"], "->", res.get("file", "NO RESULT"), res["tries"])
            sys.stdout.flush()
