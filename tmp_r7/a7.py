import json, math
C = r"user_data/strategy_factory_runs/v2/20260926-phaseC"
hr = [l for l in open(C+"/trial_ledger.jsonl", encoding="utf-8") if "H13_BTC_FILTER_1H" in l]
for l in hr: print(json.dumps(json.loads(l), indent=2))
