# Fee frontier on the freqle.org top-of-leaderboard strategy.
#
# Freqle's published harness, reproduced exactly:
#   spot, 5m, 33 Binance pairs, 1000 USDT wallet, 10 slots of 100 USDT,
#   timerange 20210101-20260101, --cache none, no --timeframe-detail
#   (their sandbox command is printed in their FAQ and is reproduced verbatim here)
#
# Only --fee changes between the three runs, so the trade count is identical at
# every point and the identity  net = gross - volume x fee  is testable.
#   1e-6    ~ gross (isolates the signal)
#   0.001   Freqle's own charge = 20 bps round trip
#   0.00175 35 bps round trip = this repo's measured COVID-regime all-in (§1b)
$ErrorActionPreference = "Continue"
$ft = ".venv\Scripts\python.exe -m freqtrade"
$common = @(
  "backtesting",
  "--config", "user_data\config_leaderboard.json",
  "--datadir", "user_data\data_leaderboard",
  "--strategy-path", "user_data\strategies\leaderboard",
  "--strategy", "NotAnotherSMAOffsetStrategy",
  "--timerange", "20210101-20260101",
  "--cache", "none"
)
New-Item -ItemType Directory -Force -Path user_data\leaderboard_out | Out-Null

foreach ($fee in @("0.000001", "0.001", "0.00175")) {
  $tag = $fee -replace "\.", "_"
  Write-Host "===== FEE $fee ====="
  Invoke-Expression "$ft $($common -join ' ') --fee $fee" 2>&1 |
    Tee-Object -FilePath "user_data\leaderboard_out\bt_$tag.log" |
    Out-Null
  Write-Host "  done $fee"
}
Write-Host "ALL DONE"
