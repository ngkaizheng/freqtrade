# Memory cap for a child process, enforced by polling WorkingSet64 and killing
# the process tree when it exceeds the cap.
#
# A Windows Job Object (JOB_OBJECT_LIMIT_JOB_MEMORY) would be a hard kernel-level
# cap, but SetInformationJobObject rejected the marshalled struct here
# ("The parameter is incorrect"), so this uses a 2-second poll instead. The
# practical difference is that a fast allocation spike can overshoot by up to one
# poll interval.
#
# Usage:
#   .\tools\leaderboard\run_capped.ps1 -Cmd '<command>' -CapGB 4 -Log 'file.log'

param(
    [Parameter(Mandatory = $true)][string] $Cmd,
    [int] $CapGB = 4,
    [string] $Log = "",
    [int] $Retry = 3
)

$capMB = [int]$CapGB * 1024
Write-Host "[memcap] hard-ish cap = $CapGB GB ($capMB MB), poll 2s" -ForegroundColor Yellow

for ($attempt = 1; $attempt -le $Retry; $attempt++) {
    Write-Host "[memcap] attempt $attempt/$Retry" -ForegroundColor Cyan

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "pwsh"
    $psi.Arguments = "-NoProfile -Command `"$Cmd`""
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true

    $proc = [System.Diagnostics.Process]::Start($psi)
    $outTask = $proc.StandardOutput.ReadToEndAsync()
    $errTask = $proc.StandardError.ReadToEndAsync()

    $peak = 0
    $killed = $false
    while (-not $proc.HasExited) {
        Start-Sleep -Seconds 2
        try {
            $proc.Refresh()
            $mb = [math]::Round($proc.WorkingSet64 / 1MB)
            if ($mb -gt $peak) {
                $peak = $mb
                if ($mb % 250 -lt 5) { Write-Host "[memcap] $mb MB" }
            }
            if ($mb -gt $capMB) {
                Write-Host "[memcap] OVER CAP ($mb MB > $capMB MB) - killing" -ForegroundColor Red
                try { $proc.Kill($true) } catch {}
                $killed = $true
                break
            }
        } catch { break }
    }
    try { $proc.WaitForExit(10000) | Out-Null } catch {}
    $code = if ($proc.HasExited) { $proc.ExitCode } else { -1 }

    Write-Host "[memcap] peak = $peak MB, exit = $code" -ForegroundColor Yellow

    if ($killed) {
        Write-Host "[memcap] KILLED FOR MEMORY - reduce the universe and retry" -ForegroundColor Red
        exit 99
    }
    if ($code -ne 0) {
        Write-Host "[memcap] non-zero exit ($code); retrying in 20s" -ForegroundColor Yellow
        Start-Sleep -Seconds 20
        continue
    }
    Write-Host "[memcap] SUCCESS" -ForegroundColor Green
    if ($Log -and (Test-Path $Log)) { Write-Host "----- $Log (tail) -----"; Get-Content $Log -Tail 40 }
    exit 0
}

Write-Host "[memcap] FAILED after $Retry attempts" -ForegroundColor Red
if ($Log -and (Test-Path $Log)) { Write-Host "----- $Log (tail) -----"; Get-Content $Log -Tail 40 }
exit 1
