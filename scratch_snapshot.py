import requests, json, datetime, time

SPACES = ['ethenagovernance.eth','lido-snapshot.eth','uniswapgovernance.eth','aave.eth',
          'gmxsnapshot.eth','frax.eth','frax-finance.eth','curve.eth','pendle.eth',
          'morpho.eth','aerodromefinance.eth','velodrome.eth','jupdao.eth','kamino.eth',
          'dydx.eth','spark.eth','sky.eth','mkrgov.eth','resupply.eth','usual.eth',
          'ondo.eth','drift.eth','zora.eth','balancer.eth','euler.eth','instadapp-gov.eth',
          'silo.eth','stargate.eth','sushigov.eth','angle.eth','gnosis.eth','arbitrumfoundation.eth']

Q = """
query($space:String!, $first:Int!, $skip:Int!){
  proposals(first:$first, skip:$skip, where:{space:$space, state:"closed"},
             orderBy:"created", orderDirection:desc){
    id title state start end created scores_total votes
    space{id} scores_state
    strategies{name}
  }
}"""

H={'Content-Type':'application/json','User-Agent':'research'}
allres={}
for sp in SPACES:
    try:
        r=requests.post('https://hub.snapshot.org/graphql',
            json={'query':Q,'variables':{'space':sp,'first':40,'skip':0}},
            headers=H, timeout=40)
        j=r.json()
        ps=(j.get('data') or {}).get('proposals')
        if ps is None:
            print('====',sp,'ERR',str(j)[:160]); continue
        allres[sp]=ps
        print('====',sp,'n=',len(ps))
        for p in ps:
            st=datetime.datetime.utcfromtimestamp(p['start']).strftime('%Y-%m-%d')
            en=datetime.datetime.utcfromtimestamp(p['end']).strftime('%Y-%m-%d')
            print(f"   {st}->{en} | {p['title'][:88]} | scores={p.get('scores_total')} votes={p.get('votes')}")
    except Exception as e:
        print('====',sp,'EXC',str(e)[:120])
    time.sleep(0.3)
json.dump(allres, open('snapshot_props.json','w'), indent=1)
