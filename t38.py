import json, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
d=json.load(open("cg_cats.json"))
WANT=["Meme","Artificial Intelligence (AI)","AI Agents","Real World Assets","Gaming","Decentralized Physical Infrastructure Network (DePIN)",
      "Decentralized Exchange (DEX)","Derivatives Trading","Liquid Staking","Restaking","Privacy","Payments","Stablecoins",
      "Prediction Markets","Layer 2 (L2)","Layer 1 (L1)","DeFi","Ethereum Ecosystem","Solana Ecosystem","Base Ecosystem",
      "Gaming (Metaverse)","Decentralized AI (DeAI)","Launchpad","Yield Farming","CDP","Tokenized Assets"]
print(f"{'CATEGORY':<52} {'MCAP$B':>10} {'24h%':>7} {'VOL24h$M':>11}")
for c in sorted(d,key=lambda x:-(x.get("market_cap") or 0)):
    nm=c["name"]
    if any(nm.lower()==w.lower() or w.lower() in nm.lower() for w in WANT):
        print(f"{nm[:50]:<52} {(c.get('market_cap') or 0)/1e9:>10,.1f} {(c.get('market_cap_change_24h') or 0):>7.2f} {(c.get('volume_24h') or 0)/1e6:>11,.0f}")
print("\n--- TOP 20 CATEGORIES BY MCAP ---")
for c in sorted(d,key=lambda x:-(x.get("market_cap") or 0))[:20]:
    print(f"{c['name'][:48]:<50} {(c.get('market_cap') or 0)/1e9:>10,.1f}B  24h={c.get('market_cap_change_24h') or 0:>6.2f}%  vol24h=${(c.get('volume_24h') or 0)/1e9:>7,.1f}B")
print("\nupdated_at:", d[0].get("updated_at"))
