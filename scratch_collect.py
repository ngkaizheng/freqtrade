import requests, json, re, sys, urllib.parse, time
H={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) research'}
def txt(html, n=3000):
    s = re.sub(r'(?is)<(script|style|svg|nav|footer|head)[^>]*>.*?</\1>',' ', html)
    s = re.sub(r'(?s)<[^>]+>',' ', s)
    s = re.sub(r'&nbsp;',' ', s); s = re.sub(r'&amp;','&', s); s = re.sub(r'&#39;',"'", s)
    s = re.sub(r'&quot;','"', s); s = re.sub(r'&gt;','>', s); s = re.sub(r'&lt;','<', s)
    s = re.sub(r'[ \t]+',' ', s); s = re.sub(r'\n\s*\n+','\n', s)
    return s.strip()[:n]

def get(url, n=2500):
    try:
        r = requests.get(url, headers=H, timeout=45)
        return r.status_code, txt(r.text, n) if 'json' not in (r.headers.get('content-type') or '') else r.text[:n]
    except Exception as e:
        return 'EXC', str(e)[:200]

# ---------- 1. DefiLlama prices / market caps ----------
ids = {'aerodrome-finance':'AERO','velodrome-finance':'VELO','uniswap':'UNI','lido-dao':'LDO',
 'ethena':'ENA','pendle':'PENDLE','aave':'AAVE','sky':'SKY','jito':'JTO','jupiter-exchange-solana':'JUP',
 'hyperliquid':'HYPE','gmx':'GMX','dydx-chain':'DYDX','monad':'MON','megaeth':'MEGA',
 'raydium':'RAY','kamino':'KMNO','spark-2':'SPK','frax':'FRAX','curve-dao-token':'CRV',
 'morpho':'MORPHO','compound-governance-token':'COMP','jito-staked-sol':'x','usual':'USUAL'}
print('##### PRICES / MCAP')
try:
    u='https://coins.llama.fi/prices/current/' + ','.join('coingecko:'+k for k in ids)
    r=requests.get(u,timeout=60).json()
    for k,v in r.get('coins',{}).items():
        cg=k.split(':')[1]
        print(f"  {ids.get(cg,cg):10s} price=${v.get('price')} conf={v.get('confidence')} ts={v.get('timestamp')}")
except Exception as e: print('  ERR',e)

# ---------- 2. Ethena USDe supply ----------
print('\n##### USDe SUPPLY (DefiLlama stablecoins)')
for u in ['https://stablecoins.llama.fi/stablecoin/146','https://api.llama.fi/protocol/ethena-usde']:
    try:
        r=requests.get(u,timeout=60)
        j=r.json()
        if 'circulating' in j:
            c=j['circulating']
            print('  last 6 pts:', [(p['date'], round(p['peggedUSD']/1e9,3)) for p in c[-6:]])
        else:
            print('  keys:', list(j)[:12])
    except Exception as e: print('  ERR',u,str(e)[:120])

# ---------- 3. Lido snapshot proposal result ----------
print('\n##### LIDO SNAPSHOT (passed proposals mid-2026)')
Q="""query($space:String!,$first:Int!){proposals(first:$first,where:{space:$space,state:"closed"},orderBy:"created",orderDirection:desc){id title start end scores_total votes scores}}"""
try:
    r=requests.post('https://hub.snapshot.org/graphql',json={'query':Q,'variables':{'space':'lido-snapshot.eth','first':6}},headers={'Content-Type':'application/json'},timeout=40).json()
    for p in r['data']['proposals']:
        import datetime as dt
        print(f"  {p['title'][:70]} | {dt.datetime.utcfromtimestamp(p['start']):%Y-%m-%d}->{dt.datetime.utcfromtimestamp(p['end']):%Y-%m-%d} | scores={p['scores']}")
except Exception as e: print('  ERR',str(e)[:200])
