# Memory cap for a child process, enforced by polling WorkingSet64.
#
# WHY A SEPARATE COPY
# -------------------
# `tools/leaderboard/run_capped.ps1` belongs to the other agent's line and is
# being edited concurrently. Two agents rewriting one script is how a run gets
# half-applied; this is a separate file with a different policy anyway.
#
# THE USER ASKED FOR MEMORY NEAR 70% SO THE MACHINE DOES NOT LOCK UP
# --------------------------------------------------------------------
# Measured 2026-09-28: **15.8 GB total, only ~5.1 GB FREE**, because a second
# agent is also running backtests. 70% of 15.8 GB is 11.1 GB - but starting an
# 11 GB job on a box with 5 GB free is exactly what freezes it.
#
# So the cap is the STANDING project constraint of **4 GB per Python process**:
# 25% of RAM, well under the 70% asked for, and it leaves headroom for the other
# agent. It also **refuses to start** when free memory is below a floor, because
# a cap on a machine that is already thrashing helps neither agent.
#
# A Windows Job Object (JOB_OBJECT_LIMIT_JOB_MEMORY) would be a true kernel cap,
# but SetInformationJobObject rejected the marshalled struct here ("The
# parameter is incorrect"), so this polls every 2s. A fast allocation spike can
# therefore overshoot by up to one poll interval.
#
# Usage:
#   .\tools\perp_short\run_capped.ps1 -Cmd '<command>' -CapGB 4 -Log 'file.log'

param(
    [Parameter(Mandatory = $true)][string] $Cmd,
    [int] $CapGB = 4,
    [string] $Log = "",
    [int] $Retry = 2,
    [double] $FreeFloorGB = 6.0
)

$os = Get-CimInstance Win32_OperatingSystem
$totalGB = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
$freeGB = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
$capMB = [int]$CapGB * 1024
Write-Host "[memcap] RAM $totalGB GB total, $freeGB GB free now" -ForegroundColor Yellow
Write-Host "[memcap] cap $CapGB GB per process = $([math]::Round(100*$CapGB/$totalGB,0))% of RAM" -ForegroundColor Yellow

for ($attempt = 1; $attempt -le $Retry; $attempt++) {
    $os = Get-CimInstance Win32_OperatingSystem
    $freeGB = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
    if ($freeGB -lt $FreeFloorGB) {
        Write-Host "[memcap] only $freeGB GB free (floor $FreeFloorGB GB) - waiting 60s" -ForegroundColor Yellow
        Start-Sleep -Seconds 60
        continue
    }

    Write-Host "[memcap] attempt $attempt/$Retry" -ForegroundColor Cyan
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "pwsh"
    $psi.Arguments = "-NoProfile -Command `"$Cmd`""
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true

    $proc = [System.Diagnostics.Process]::Start($psi)
    $null = $proc.StandardOutput.ReadToEndAsync()
    $null = $proc.StandardError.ReadToEndAsync()

    $peak = 0
    $killed = $false
    while (-not $proc.HasExited) {
        Start-Sleep -Seconds 2
        try {
            $proc.Refresh()
            $mb = [math]::Round($proc.WorkingSet64 / 1MB)
            if ($mb -gt $peak) { $peak = $mb }
            if ($mb -gt $capMB) {
                Write-Host "[memcap] OVER CAP ($mb MB > $capMB MB) - killing" -ForegroundColor Red
                try { $proc.Kill($true) } catch {}
                $killed = $true
                break
            }
        } catch { break }
    }
    try { $proc.WaitForExit(15000) | Out-Null } catch {}
    $code = if ($proc.HasExited) { $proc.ExitCode } else { -1 }
    Write-Host "[memcap] peak $peak MB, exit $code" -ForegroundColor Yellow

    if ($killed) {
        Write-Host "[memcap] KILLED FOR MEMORY - reduce the universe or split the run" -ForegroundColor Red
        exit 99
    }
    if ($code -ne 0) {
        Write-Host "[memcap] non-zero exit ($code); waiting 45s" -ForegroundColor Yellow
        Start-Sleep -Seconds 45
        continue
    }
    Write-Host "[memcap] SUCCESS (peak $peak MB)" -ForegroundColor Green
    if ($Log -and (Test-Path $Log)) { Write-Host "----- $Log (tail) -----"; Get-Content $Log -Tail 30 }
    exit 0
}

Write-Host "[memcap] FAILED after $Retry attempts" -ForegroundColor Red
if ($Log -and (Test-Path $Log)) { Write-Host "----- $Log (tail) -----"; Get-Content $Log -Tail 30 }
exit 1
