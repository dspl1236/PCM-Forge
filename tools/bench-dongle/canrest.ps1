# Restbus transmitter: send a table of frames periodically, so the PCM sees a
# car that we control rather than one we merely observe.
#
#   canrest.ps1 -Make C:\canwork\boot\mmi_...log -Out C:\canwork\rest.txt
#   canrest.ps1 -Table C:\canwork\rest.txt -Seconds 120
#   canrest.ps1 -Table C:\canwork\rest.txt -Only 3F1,6C0 -Seconds 60
#
# Table format, one frame per line:   <id> <period_ms> <hex payload>
#
# -Make derives a table from a capture: each id's LAST payload and its measured
# period. Last rather than first because the settled value is the one that says
# "running", not "booting".
#
# Replace the gateway, do not compete with it. Two nodes sending the same id
# collide on arbitration and one loses, giving unpredictable interleaving rather
# than a controlled test.

param([string]$Table, [string]$Make, [string]$Out,
      [string]$Port="COM5", [int]$Rate=500, [int]$Seconds=60,
      [string]$Only, [string]$Set)

if ($Make) {
  $last=@{}; $first=@{}; $lastT=@{}; $n=@{}
  foreach($line in (Get-Content $Make)){
    $p = $line -split '\s+'
    if($p.Count -lt 3){ continue }
    $t=[double]$p[0]; $id=$p[1]
    $data = if($p.Count -ge 4){ $p[3] } else { $p[2] }
    if(-not $first.ContainsKey($id)){ $first[$id]=$t; $n[$id]=0 }
    $last[$id]=$data; $lastT[$id]=$t; $n[$id]++
  }
  $lines=@()
  foreach($id in ($last.Keys | Sort-Object)){
    $span = $lastT[$id]-$first[$id]
    $per = if($n[$id] -gt 1 -and $span -gt 0){ [int]($span/($n[$id]-1)) } else { 1000 }
    if($per -lt 10){ $per = 10 }
    $lines += ("{0} {1} {2}" -f $id,$per,$last[$id])
  }
  $lines | Set-Content $Out -Encoding ASCII
  Write-Output ("wrote {0} frames to {1}" -f $lines.Count,$Out)
  $lines | ForEach-Object { "  $_" }
  exit 0
}

if(-not $Table){ Write-Output "need -Table or -Make"; exit 1 }
$frames=@()
foreach($line in (Get-Content $Table)){
  $p = $line -split '\s+'
  if($p.Count -lt 3 -or $line -match '^\s*#'){ continue }
  $frames += @{ id=$p[0]; per=[int]$p[1]; data=$p[2]; next=0.0 }
}
if($Only){
  $keep = $Only -split ','
  $frames = $frames | Where-Object { $keep -contains $_.id }
}
# -Set 3F1:1:02  => override byte 1 of id 3F1 with 02
if($Set){
  foreach($ov in ($Set -split ',')){
    $q = $ov -split ':'
    if($q.Count -ne 3){ continue }
    foreach($f in $frames){
      if($f.id -eq $q[0]){
        $b=[int]$q[1]
        $f.data = $f.data.Substring(0,$b*2) + $q[2] + $f.data.Substring($b*2+2)
        Write-Output ("override {0} byte {1} -> {2}   {3}" -f $q[0],$b,$q[2],$f.data)
      }
    }
  }
}

$rates=@{100='S3';250='S5';500='S6'}
$sp = New-Object System.IO.Ports.SerialPort $Port,115200,'None',8,'One'
$sp.WriteTimeout=500; $sp.ReadTimeout=50
$sp.Open()
function Cmd($c){ $sp.Write($c+"`r"); Start-Sleep -Milliseconds 120 }
Cmd 'C'; Cmd $rates[$Rate]; Cmd 'O'

Write-Output ("transmitting {0} frames for {1}s at {2}k" -f $frames.Count,$Seconds,$Rate)
$sw=[Diagnostics.Stopwatch]::StartNew(); $sent=0
while($sw.Elapsed.TotalSeconds -lt $Seconds){
  $now=$sw.Elapsed.TotalMilliseconds
  foreach($f in $frames){
    if($now -ge $f.next){
      $dlc = [int]($f.data.Length/2)
      try{ $sp.Write("t{0}{1}{2}`r" -f $f.id,$dlc,$f.data); $sent++ }catch{}
      $f.next = $now + $f.per
    }
  }
  Start-Sleep -Milliseconds 2
}
Cmd 'C'; $sp.Close()
Write-Output "$sent frames sent"
