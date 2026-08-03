# Watch a CAN bus and characterise it: per-ID cadence, and which payload bytes
# are live versus fixed. Raw frame dumps are hard to compare between runs --
# this is meant to be run before and after a change (ignition, a module added)
# so the difference is obvious.
#
#   canwatch.ps1 -Port COM5 -Rate 500 -Seconds 60 -LogFile C:\canwork\base.log
#
# Opens in normal mode and transmits a short burst first. Both are necessary on
# the CANable2 firmware: listen-only does not receive at all, and it will not
# start receiving until it has transmitted.

param([string]$Port="COM5", [int]$Rate=500, [int]$Seconds=60,
      [string]$LogFile="", [switch]$NoStir)

$rates = @{ 100='S3'; 125='S4'; 250='S5'; 500='S6'; 1000='S8' }
$sp = New-Object System.IO.Ports.SerialPort $Port,115200,'None',8,'One'
$sp.ReadTimeout = 200; $sp.WriteTimeout = 500
try { $sp.Open() } catch { Write-Output "cannot open $Port : $_"; exit 1 }
function Cmd($c){ try{ $sp.Write($c + "`r"); Start-Sleep -Milliseconds 120 }catch{} }

Cmd 'C'; $sp.DiscardInBuffer(); Cmd $rates[$Rate]; Cmd 'O'
if (-not $NoStir) {
  for($i=0; $i -lt 40; $i++){ try{ $sp.Write("t7DF80000000000000000`r") }catch{}; Start-Sleep -Milliseconds 5 }
  Start-Sleep -Milliseconds 200
  $sp.DiscardInBuffer()
}

Write-Output "watching $Port at ${Rate}k for ${Seconds}s"
$first=@{}; $last=@{}; $count=@{}; $dlc=@{}; $vals=@{}; $gaps=@{}
$total=0; $buf=""
$sw=[Diagnostics.Stopwatch]::StartNew()

while($sw.Elapsed.TotalSeconds -lt $Seconds){
  try{ $c=$sp.ReadExisting() }catch{ $c="" }
  if($c){ $buf+=$c }
  while($buf.Contains("`r")){
    $i=$buf.IndexOf("`r"); $l=$buf.Substring(0,$i).Trim(); $buf=$buf.Substring($i+1)
    if($l.Length -lt 5 -or $l[0] -ne 't'){ continue }
    $id=$l.Substring(1,3)
    $d=[Convert]::ToInt32($l.Substring(4,1),16)
    $data = if($l.Length -ge 5+$d*2){ $l.Substring(5,$d*2) } else { "" }
    $now=$sw.Elapsed.TotalMilliseconds
    $total++
    if(-not $count.ContainsKey($id)){
      $count[$id]=0; $dlc[$id]=$d; $first[$id]=$now; $vals[$id]=@{}; $gaps[$id]=@()
    } else {
      $gaps[$id] += ($now - $last[$id])
    }
    $count[$id]++; $last[$id]=$now; $vals[$id][$data]=1
    if($LogFile){ Add-Content $LogFile ("{0:F1} {1} {2} {3}" -f $now,$id,$d,$data) }
  }
  Start-Sleep -Milliseconds 10
}
Cmd 'C'; $sp.Close()

Write-Output ""
Write-Output "=== $total frames, $($count.Count) IDs in ${Seconds}s ==="
Write-Output ""
Write-Output ("{0,-5} {1,6} {2,8} {3,4} {4,6}  {5}" -f "ID","count","period","dlc","forms","payload  (.. = fixed, XX = varies)")

foreach($id in ($count.Keys | Sort-Object)){
  $p = if($gaps[$id].Count){ ($gaps[$id] | Measure-Object -Average).Average } else { 0 }
  $forms = $vals[$id].Keys
  $n = $dlc[$id]
  # mark a byte position as varying if it differs across observed payloads
  $mask = @()
  for($b=0; $b -lt $n; $b++){
    $seen = @{}
    foreach($f in $forms){ if($f.Length -ge ($b*2+2)){ $seen[$f.Substring($b*2,2)]=1 } }
    $mask += if($seen.Count -gt 1){ "XX" } else { (@($seen.Keys)[0]) }
  }
  Write-Output ("{0,-5} {1,6} {2,7:F0}m {3,4} {4,6}  {5}" -f `
    $id, $count[$id], $p, $n, $forms.Count, ($mask -join ' '))
}

Write-Output ""
Write-Output "=== distinct payloads per ID (up to 4) ==="
foreach($id in ($count.Keys | Sort-Object)){
  $k = @($vals[$id].Keys) | Select-Object -First 4
  foreach($v in $k){
    $sp2 = ($v -split '(..)' | Where-Object { $_ }) -join ' '
    Write-Output ("  {0}  {1}" -f $id, $sp2)
  }
  if($vals[$id].Keys.Count -gt 4){ Write-Output ("  {0}  ... {1} more forms" -f $id, ($vals[$id].Keys.Count-4)) }
}
