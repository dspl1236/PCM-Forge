# Capture both buses across a cold power-on.
#
#   capture_both.ps1 -Seconds 180
#
# COM5 = CANable on the MMI/PCM bus.  COM8 = Nano/MCP2515 on the gateway's
# diagnostic pair. Both are started as jobs and stamped with the same wall
# clock so the two logs can be laid side by side afterwards.
#
# One unavoidable contamination: the CANable will not receive until it has
# transmitted, so it emits a short burst BEFORE the unit is powered. That is
# deliberate and happens while the bus is dead, so it cannot colour the boot.
# After that both sides are purely passive on the MMI bus.
#
# The Nano opens in normal mode on purpose -- it must acknowledge the gateway
# or the gateway climbs TEC to 255 and stops transmitting on the diag pair.

param([int]$Seconds = 180, [string]$OutDir = "C:\canwork\boot")

New-Item -ItemType Directory -Force $OutDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$mmi  = Join-Path $OutDir "mmi_$stamp.log"
$diag = Join-Path $OutDir "diag_$stamp.log"

$t0 = Get-Date
Write-Output ("started " + $t0.ToString("HH:mm:ss.fff"))
Write-Output ("  MMI  -> $mmi")
Write-Output ("  DIAG -> $diag")

$jMmi = Start-Job -ScriptBlock {
  param($sec,$log)
  powershell -ExecutionPolicy Bypass -File C:\canwork\canwatch.ps1 `
    -Port COM5 -Rate 500 -Seconds $sec -LogFile $log
} -ArgumentList $Seconds,$mmi

$jDiag = Start-Job -ScriptBlock {
  param($sec,$log)
  powershell -ExecutionPolicy Bypass -File C:\canwork\nanolisten.ps1 `
    -Port COM8 -Rate 500 -Seconds $sec -LogFile $log
} -ArgumentList $Seconds,$diag

Write-Output ""
Write-Output "*** BOTH LISTENING - POWER THE BENCH UNIT ON NOW ***"
Write-Output ""

Wait-Job $jMmi,$jDiag -Timeout ($Seconds + 60) | Out-Null
Write-Output "=================== MMI BUS (COM5) ==================="
Receive-Job $jMmi
Write-Output ""
Write-Output "=================== DIAG BUS (COM8) =================="
Receive-Job $jDiag
Remove-Job $jMmi,$jDiag -Force -ErrorAction SilentlyContinue

Write-Output ""
Write-Output "logs: $mmi"
Write-Output "      $diag"
