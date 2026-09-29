import requests, os, json, re, time
OUT = os.path.dirname(os.path.abspath(__file__))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
H = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none", "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

cands = [
    ("mdpi-res", "https://mdpi-res.com/d_attachment/mathematics/mathematics-14-00346/article_deploy/mathematics-14-00346-v2.pdf"),
    ("mdpi-res-noV", "https://mdpi-res.com/d_attachment/mathematics/mathematics-14-00346/article_deploy/mathematics-14-00346.pdf"),
    ("mdpi-res-pdf", "https://mdpi-res.com/d_attachment/mathematics/mathematics-14-00346/article_deploy/mathematics-14-00346.pdf?version=1768916036"),
    ("mdpi-ver", "https://www.mdpi.com/2227-7390/14/2/346/pdf?version=1768916036"),
    ("mdpi-html-ver", "https://www.mdpi.com/2227-7390/14/2/346"),
    ("doaj", "https://doaj.org/article/89794728d94043eda3c9a05c69cfaa88"),
    ("mdpi-hier", "https://www.mdpi.com/2227-7390/14/2/346/xml"),
]
for name, url in cands:
    try:
        r = requests.get(url, headers=H, timeout=90)
        ct = r.headers.get("Content-Type", "")
        print(f"=== {name:14s} {r.status_code} len={len(r.content):9d} ct={ct}  {url[:95]}")
        if r.status_code == 200:
            fn = os.path.join(OUT, f"_v1_{name}.bin")
            open(fn, "wb").write(r.content)
            if "pdf" in ct or r.content[:4] == b"%PDF":
                print("      *** PDF SAVED ->", fn)
            else:
                t = r.text
                # dump any text
                t2 = re.sub(r"<script.*?</script>", " ", t, flags=re.S)
                t2 = re.sub(r"<style.*?</style>", " ", t2, flags=re.S)
                t2 = re.sub(r"<[^>]+>", "\n", t2)
                t2 = re.sub(r"\n\s*\n+", "\n", t2)
                open(os.path.join(OUT, f"_v1_{name}.txt"), "w", encoding="utf8").write(t2)
                print("      text len", len(t2))
    except Exception as e:
        print(f"=== {name:14s} ERR {type(e).__name__}: {e}")
    time.sleep(1)
