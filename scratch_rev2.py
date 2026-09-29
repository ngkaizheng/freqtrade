import requests, datetime
def show(slug,dtype):
    try:
        j=requests.get(f'https://api.llama.fi/summary/fees/{slug}',params={'dataType':dtype},timeout=60).json()
        print(f"{slug:18s} {dtype:12s} 24h={j.get('total24h')} 7d={j.get('total7d')} 30d={j.get('total30d')} 1y={j.get('total1y')} chg30={j.get('change_30dover30d')}")
    except Exception as e:
        print(slug,dtype,'ERR',str(e)[:70])
for s in ['lido','aerodrome-v1','velodrome-v2','uniswap','aave-v3','ethena','hyperliquid','jito','pendle','morpho','gmx','dydx-v4','jupiter','raydium','spark','sky-lending']:
    show(s,'dailyRevenue')
print()
r=requests.get('https://coins.llama.fi/prices/current/coingecko:ethereum,coingecko:aerodrome-finance,coingecko:velodrome-finance',timeout=40).json()
for k,v in r['coins'].items():
    print(k, round(v['price'],4), datetime.datetime.utcfromtimestamp(v['timestamp']).isoformat())
