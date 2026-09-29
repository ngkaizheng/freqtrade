param(
    [string]$Timerange = "20251119-20260927",
    [string]$Fee      = "0.0006",
    [string]$Tag      = "fresh_net",
    [string[]]$Arms   = @("X0","X1","X2","X3","X4","X5")
)

$ErrorActionPreference = "Continue"
$out = "user_data\backtest_results\exit_study\$Tag"
New-Item -ItemType Directory -Force -Path $out | Out-Null

foreach ($arm in $Arms) {
    Write-Output "===== ARM $arm  fee=$Fee  timerange=$Timerange ====="
    & ".\.venv\Scripts\freqtrade.exe" backtesting `
        --config user_data\config_exit_study.json `
        --config "user_data\exit_study\arms\$arm.json" `
        --datadir user_data\data\binance `
        --strategy RegimeBreakoutExitStudy `
        --timerange $Timerange `
        --fee $Fee `
        --export trades `
        --backtest-directory $out `
        --notes "arm=$arm fee=$Fee range=$Timerange" 2>&1 |
        Select-String -Pattern 'ERROR|Configuration error|Total/Daily Avg Trades|Absolute profit|Total profit %|Profit factor|Sharpe \(closed|Using fee|Backtesting with data' |
        ForEach-Object { Write-Output $_.Line }
}
Write-Output "===== DONE $Tag ====="
