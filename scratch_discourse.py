import requests, json, time, urllib.parse

FORUMS = {
 'aave':'https://governance.aave.com',
 'lido':'https://research.lido.fi',
 'ethena':'https://gov.ethenafoundation.com',
 'uniswap':'https://gov.uniswap.org',
 'curve':'https://gov.curve.fi',
 'pendle':'https://forum.pendle.finance',
 'morpho':'https://forum.morpho.org',
 'sky':'https://forum.sky.money',
 'jupiter':'https://discuss.jup.ag',
 'kamino':'https://gov.kamino.finance',
 'dydx':'https://dydx.forum',
 'gmx':'https://gov.gmx.io',
 'aerodrome':'https://gov.aerodrome.finance',
 'frax':'https://gov.frax.finance',
 'balancer':'https://forum.balancer.fi',
 'compound':'https://comp.xyz',
 'spark':'https://forum.sky.money',
 'instadapp':'https://forum.instadapp.io',
 'euler':'https://forum.euler.finance',
 'resupply':'https://forum.resupply.fi',
 'usual':'https://gov.usual.money',
 'ondo':'https://forum.ondo.finance',
 'drift':'https://forum.drift.trade',
 'zora':'https://forum.zora.co',
}

QUERIES = ['buyback after:2026-08-15', 'fee switch after:2026-08-15',
           'revenue share after:2026-08-15', 'activation after:2026-09-01',
           'burn after:2026-08-15', 'buyback order:latest']

H = {'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) research-bot'}
res={}
for name, base in FORUMS.items():
    hits=[]
    for q in QUERIES[:3]:
        try:
            u = base + '/search.json?q=' + urllib.parse.quote(q)
            r = requests.get(u, headers=H, timeout=25)
            if r.status_code != 200:
                hits.append({'q':q,'err':r.status_code}); continue
            j = r.json()
            topics = {t['id']:t for t in j.get('topics',[])}
            for p in j.get('posts',[])[:12]:
                t = topics.get(p.get('topic_id'))
                if not t: continue
                hits.append({'q':q,'title':t.get('title'),'created':p.get('created_at'),
                             'blurb':(p.get('blurb') or '')[:220],'id':t.get('id'),
                             'slug':t.get('slug')})
        except Exception as e:
            hits.append({'q':q,'exc':str(e)[:80]})
        time.sleep(0.4)
    res[name]=hits
    print('=====',name,len(hits))
    for h in hits:
        if 'err' in h or 'exc' in h:
            print('   ',h); continue
        print(f"   [{h['created'][:10]}] {h['title'][:78]}")
        print(f"        {h['blurb'][:170]}")
json.dump(res, open('discourse_hits.json','w'), indent=1)
