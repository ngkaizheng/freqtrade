import requests, json, time
H={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) research','Accept':'application/json'}
ids = ['aerodrome-finance','velodrome-finance','uniswap','lido-dao','ethena','pendle','aave',
 'sky','jito','jupiter-exchange-solana','hyperliquid','gmx','dydx-chain','monad','megaeth',
 'raydium','kamino','spark-2','frax-share','curve-dao-token','morpho','compound-governance-token',
 'usual','ethereum','solana','balancer','ethena-usde','aero-2','jito-governance-token']
rows=[]
CH=['id','symbol','name','current_price','market_cap','fully_diluted_valuation','total_volume',
    'price_change_percentage_24h','price_change_percentage_7d_in_currency','price_change_percentage_30d_in_currency']
for chunk in [ids[i:i+10] for i in range(0,len(ids),10)]:
    try:
        r=requests.get('https://api.coingecko.com/api/v3/coins/markets',
            params={'vs_currency':'usd','ids':','.join(chunk),'price_change_percentage':'7d,30d'},
            headers=H, timeout=45)
        if r.status_code!=200:
            print('HTTP',r.status_code, r.text[:200]); time.sleep(3); continue
        for c in r.json():
            rows.append({k:c.get(k) for k in CH} | {'ath':c.get('ath'),'ath_date':c.get('ath_date'),
                        'ath_change_percentage':c.get('ath_change_percentage')})
    except Exception as e:
        print('EXC',str(e)[:150])
    time.sleep(2)
if not rows:
    print('COINGECKO BLOCKED - fallback to DefiLlama')
print(f"{'sym':8s} {'price':>10s} {'mcap$M':>10s} {'vol24$M':>10s} {'7d%':>7s} {'30d%':>7s} {'ATHdist%':>9s}  ath_date")
for c in rows:
    mc=c.get('market_cap'); 
    print(f"{str(c.get('symbol')).upper()[:8]:8s} {c.get('current_price') or 0:10.6f} "
          f"{(mc/1e6 if mc else 0):10.1f} {((c.get('total_volume') or 0)/1e6):10.1f} "
          f"{(c.get('price_change_percentage_7d_in_currency') or 0):7.2f} "
          f"{(c.get('price_change_percentage_30d_in_currency') or 0):7.2f} "
          f"{(c.get('ath_change_percentage') or 0):9.1f}  {str(c.get('ath_date'))[:10]}")
json.dump(rows, open('cg.json','w'), indent=1)
