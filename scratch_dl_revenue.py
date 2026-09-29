import requests, json, datetime

CAND = {
 'ethena':'ENA','aave':'AAVE','uniswap':'UNI','curve-dex':'CRV','lido':'LDO','pendle':'PENDLE',
 'morpho':'MORPHO','aerodrome-v1':'AERO','aerodrome':'AERO','velodrome-v2':'VELO',
 'jupiter':'JUP','raydium':'RAY','kamino':'KMNO','hyperliquid':'HYPE','spark':'SPK',
 'sky':'SKY','maker':'MKR','frax':'FRAX','gmx':'GMX','dydx':'DYDX','drift':'DRIFT',
 'zora':'ZORA','berachain':'BERA','sonic':'S','monad':'MON','gains-network':'GNS',
 'eigenlayer':'EIGEN','jito':'JTO','sanctum':'CLOUD','solayer':'LAYER','usual':'USUAL',
 'resupply':'RSUP','convex-finance':'CVX','yearn-finance':'YFI','balancer':'BAL',
 'sushiswap':'SUSHI','pancakeswap-amm':'CAKE','thorchain':'RUNE','osmosis':'OSMO',
 'compound-finance':'COMP','maple-finance':'MPL','ondo-finance':'ONDO','ethena-usde':'USDE',
 'pump':'PUMP','meteora':'MET','orca':'ORCA','save':'SAVE','marginfi':'MRGN',
 'vertex-protocol':'VRTX','paradex':'DIME','lighter':'LIT','aster':'ASTER',
 'avantis':'AVNT','hedgey':'HDGY','stable':'STABLE','plasma':'XPL',
}

out=[]
for dtype in ['dailyRevenue','dailyFees']:
    r = requests.get('https://api.llama.fi/overview/'+('fees' if dtype.startswith('dailyR') or dtype=='dailyFees' else 'fees'),
                     params={'excludeTotalDataChart':'true','excludeTotalDataChartBreakdown':'true','dataType':dtype}, timeout=120)
    j = r.json()
    recs=[]
    for p in j.get('protocols',[]):
        slug = p.get('slug') or p.get('module','')
        recs.append({'name':p.get('name'),'slug':slug,'cat':p.get('category'),
                     'rev30':p.get('total30d'),'rev7':p.get('total7d'),'rev24':p.get('total24h'),
                     'rev1y':p.get('total1y'),'mcap':p.get('mcap'),'chg7':p.get('change_7dover7d'),
                     'chg30':p.get('change_30dover30d'),'chg1y':p.get('change_1yover1y')})
    out.append((dtype, recs))
    print('===',dtype,'n=',len(recs))

json.dump({k:v for k,v in out}, open('dl_rev.json','w'))
# print candidates
for dtype, recs in out:
    print('\n#####', dtype)
    hits=[x for x in recs if (x['slug'] or '').lower() in CAND]
    for x in sorted(hits, key=lambda z: -(z['rev30'] or 0)):
        print(f"{x['name'][:34]:36s} {str(x['slug'])[:22]:24s} r30={x['rev30'] and round(x['rev30']/1e6,2)}M r7={x['rev7'] and round(x['rev7']/1e6,2)}M r1y={x['rev1y'] and round(x['rev1y']/1e6,1)}M mcap={x['mcap'] and round(x['mcap']/1e6,1)}M chg7={x['chg7']} chg30={x['chg30']} cat={x['cat']}")
