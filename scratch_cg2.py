import requests, json, time
H={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) research','Accept':'application/json'}
ids=['hyperliquid','jito','gmx','dydx-chain','raydium','kamino','spark-2','curve-dao-token',
     'morpho','monad','megaeth','frax-share','aerodrome-finance','ethena-usde','usual','jito-governance-token']
rows=[]
for i in range(0,len(ids),5):
    for attempt in range(3):
        try:
            r=requests.get('https://api.coingecko.com/api/v3/coins/markets',
              params={'vs_currency':'usd','ids':','.join(ids[i:i+5]),'price_change_percentage':'7d,30d'},
              headers=H,timeout=45)
            if r.status_code==200:
                for c in r.json():
                    rows.append({'sym':(c.get('symbol') or '').upper(),'name':c.get('name'),
                     'price':c.get('current_price'),'mcap':c.get('market_cap'),'fdv':c.get('fully_diluted_valuation'),
                     'vol':c.get('total_volume'),'chg7':c.get('price_change_percentage_7d_in_currency'),
                     'chg30':c.get('price_change_percentage_30d_in_currency'),
                     'athd':c.get('ath_change_percentage'),'athdate':str(c.get('ath_date'))[:10]})
                break
            time.sleep(6)
        except Exception as e:
            print('EXC',str(e)[:80]); time.sleep(5)
    time.sleep(3)
print(f"{'sym':9s}{'price':>11s}{'mcap$M':>10s}{'vol24$M':>10s}{'7d%':>8s}{'30d%':>8s}{'ATHdist%':>10s}  ath")
for c in rows:
    print(f"{c['sym'][:9]:9s}{(c['price'] or 0):11.5f}{((c['mcap'] or 0)/1e6):10.1f}{((c['vol'] or 0)/1e6):10.1f}"
          f"{(c['chg7'] or 0):8.2f}{(c['chg30'] or 0):8.2f}{(c['athd'] or 0):10.1f}  {c['athdate']}")
json.dump(rows,open('cg2.json','w'),indent=1)
