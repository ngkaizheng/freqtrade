import requests, json, re, sys
H={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) research'}
def clean(html, n=4000):
    s = re.sub(r'(?is)<(script|style|svg)[^>]*>.*?</\1>',' ', html)
    s = re.sub(r'(?s)<br\s*/?>','\n', s)
    s = re.sub(r'(?s)</p>','\n', s)
    s = re.sub(r'(?s)<[^>]+>',' ', s)
    for a,b in [('&nbsp;',' '),('&amp;','&'),('&#39;',"'"),('&quot;','"'),('&gt;','>'),('&lt;','<'),('&#x27;',"'")]:
        s=s.replace(a,b)
    s = re.sub(r'[ \t]+',' ', s); s=re.sub(r'\n\s*\n+','\n', s)
    return s.strip()[:n]

# --- Lido NEST restructuring thread (first 2 posts) ---
print('########## LIDO NEST RESTRUCTURING (t/11921)')
try:
    j = requests.get('https://research.lido.fi/t/11921.json', headers=H, timeout=45).json()
    print('TITLE:', j['title'])
    for p in j['post_stream']['posts'][:3]:
        print(f"--- post by {p['username']} at {p['created_at']}")
        print(clean(p['cooked'], 3200))
        print()
except Exception as e:
    print('ERR', str(e)[:200])

# --- Market caps via DefiLlama coins (circulating via coingecko ids on llama) ---
print('\n########## MCAP (DefiLlama /protocols)')
want={'AERO','UNI','LDO','ENA','PENDLE','AAVE','SKY','JUP','HYPE','GMX','DYDX','MON','RAY','KMNO','CRV','MORPHO','COMP','JTO','SPK','USUAL'}
try:
    ps = requests.get('https://api.llama.fi/protocols', timeout=120).json()
    for p in ps:
        sym=(p.get('symbol') or '').upper()
        if sym in want and p.get('mcap'):
            print(f"  {sym:8s} {p.get('name','')[:26]:28s} mcap=${p['mcap']/1e6:,.1f}M chg1d={p.get('change_1d')} chg7d={p.get('change_7d')} tvl={p.get('tvl')}")
except Exception as e: print('ERR', str(e)[:200])
