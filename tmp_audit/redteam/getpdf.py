import requests, re, os, sys
from pypdf import PdfReader
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
def dl(url, name):
    p=os.path.join("tmp_audit","redteam",name)
    if os.path.exists(p) and os.path.getsize(p)>10000:
        return p
    r=requests.get(url, headers=H, timeout=90)
    print(name, r.status_code, len(r.content))
    r.raise_for_status()
    open(p,"wb").write(r.content); return p
def txt(p, pages=None):
    rd=PdfReader(p)
    out=[]
    for i,pg in enumerate(rd.pages):
        if pages and i not in pages: continue
        out.append(f"\n===PAGE {i+1}===\n"+(pg.extract_text() or ""))
    return "\n".join(out)
if __name__=="__main__":
    url=sys.argv[1]; name=sys.argv[2]
    p=dl(url,name)
    t=txt(p)
    open(p+".txt","w",encoding="utf-8").write(t)
    print("chars:",len(t))
