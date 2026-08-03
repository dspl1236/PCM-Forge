# CAN listener for a CANable-class slcan adapter, no Python required.
#
#   canlisten.ps1 -Port COM5 -Rate 100 -Seconds 90
#   canlisten.ps1 -Port COM5 -Rate 500 -Seconds 30 -ListenOnly
#
# slcan is ASCII over serial: Sn sets the bitrate, O opens normally (which
# ACKs, giving a lone transmitter a partner), L opens listen-only, C closes.
# Received frames arrive as  tIIILDD..  terminated by CR.

param(
  [string]$Port = "COM5",
  [int]$Rate = 100,           # kbit/s
  [int]$Seconds = 60,
  [switch]$ListenOnly,
  [string]$LogFile = ""
)

$rates = @{ 10='S0'; 20='S1'; 50='S2'; 100='S3'; 125='S4';
            250='S5'; 500='S6'; 800='S7'; 1000='S8' }
if (-not $rates.ContainsKey($Rate)) {
  Write-Output "unsupported rate $Rate (use 10/20/50/100/125/250/500/800/1000)"
  exit 1
}

$sp = New-Object System.IO.Ports.SerialPort $Port,115200,'None',8,'One'
$sp.ReadTimeout  = 200
$sp.WriteTimeout = 500
$sp.NewLine = "`r"
try { $sp.Open() } catch { Write-Output "cannot open $Port : $_"; exit 1 }

function Send-Cmd([string]$c) {
  try { $sp.Write($c + "`r"); Start-Sleep -Milliseconds 120 } catch {}
}

Send-Cmd 'C'                       # close first; harmless if already closed
$sp.DiscardInBuffer()
Send-Cmd $rates[$Rate]
if ($ListenOnly) { Send-Cmd 'L' } else { Send-Cmd 'O' }

$mode = if ($ListenOnly) { 'listen-only' } else { 'normal (we ACK)' }
Write-Output "listening on $Port at ${Rate}k, $mode, for ${Seconds}s"
Write-Output "t=0.0  START"

$ids = @{}
$total = 0
$sw = [Diagnostics.Stopwatch]::StartNew()
$buf = ""

while ($sw.Elapsed.TotalSeconds -lt $Seconds) {
  try { $chunk = $sp.ReadExisting() } catch { $chunk = "" }
  if ($chunk) { $buf += $chunk }
  while ($buf.Contains("`r")) {
    $i = $buf.IndexOf("`r")
    $line = $buf.Substring(0, $i).Trim()
    $buf = $buf.Substring($i + 1)
    if ($line.Length -lt 5) { continue }
    if ($line[0] -eq 't') {
      $id  = $line.Substring(1,3)
      $dlc = [Convert]::ToInt32($line.Substring(4,1),16)
      $dat = if ($line.Length -ge 5+$dlc*2) { $line.Substring(5, $dlc*2) } else { "" }
      $total++
      $t = "{0:F1}" -f $sw.Elapsed.TotalSeconds
      if (-not $ids.ContainsKey($id)) {
        $ids[$id] = 0
        Write-Output "t=$t  NEW ID $id  dlc=$dlc  $dat"
      }
      $ids[$id]++
      if ($LogFile) { Add-Content $LogFile "$t $id $dlc $dat" }
    }
  }
  Start-Sleep -Milliseconds 20
}

Send-Cmd 'C'
$sp.Close()

Write-Output ""
Write-Output "=== $total frames, $($ids.Count) distinct IDs ==="
foreach ($k in ($ids.Keys | Sort-Object)) {
  Write-Output ("   {0}   {1,6} frames" -f $k, $ids[$k])
}
if ($total -eq 0) { Write-Output "   (silence)" }
