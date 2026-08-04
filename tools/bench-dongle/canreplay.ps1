# Replay a capture verbatim: same frames, same order, same timing, looped.
#
# Beats a synthesised table because it reproduces rolling counters, alive-flags
# and state machines exactly -- it is literally what the gateway transmitted.
# A frozen counter tells a receiver the sender has stopped updating, so the data
# is discarded as stale; that is almost certainly why the constructed table was
# heard but not believed.
#
#   canreplay.ps1 -Log mmi.log -Skip 30000 -Seconds 90
#
# -Skip discards the first N ms so the boot sequence is not replayed on loop;
# what remains is the settled "car running" state.
# PCM-transmitted ids are excluded -- we are impersonating the gateway, and
# transmitting the PCM's own ids would put us in conflict with it.
param([string]$Log, [string]$Port="COM5", [int]$Rate=500,
      [int]$Seconds=90, [double]$Skip=30000, [string]$Exclude="539,541,5FA,5FB,6AB,6D3")

$skipIds = $Exclude -split ','
$t=@(); $ids=@(); $data=@()
foreach($line in (Get-Content $Log)){
  $p = $line -split '\s+'
  if($p.Count -lt 4){ continue }
  $ts=[double]$p[0]
  if($ts -lt $Skip){ continue }
  if($skipIds -contains $p[1]){ continue }
  $t += $ts; $ids += $p[1]; $data += $p[3]
}
if($t.Count -eq 0){ Write-Output "nothing to replay"; exit 1 }
$base = $t[0]; $span = $t[$t.Count-1] - $base
Write-Output ("replaying {0} frames spanning {1:F1}s, looped, for {2}s" -f $t.Count,($span/1000),$Seconds)

$rates=@{100='S3';250='S5';500='S6'}
$sp = New-Object System.IO.Ports.SerialPort $Port,115200,'None',8,'One'
$sp.WriteTimeout=1000; $sp.ReadTimeout=50
$sp.Open()
function Cmd($c){ $sp.Write($c+"`r"); Start-Sleep -Milliseconds 150 }
Cmd 'C'; Cmd $rates[$Rate]; Cmd 'O'

$sent=0; $rx=@{}; $forms=@{}; $buf=""; $i=0; $loop=0
$sw=[Diagnostics.Stopwatch]::StartNew()
while($sw.Elapsed.TotalSeconds -lt $Seconds){
  $now = $sw.Elapsed.TotalMilliseconds - ($loop * $span)
  while($i -lt $t.Count -and ($t[$i]-$base) -le $now){
    $d=[int]($data[$i].Length/2)
    try{ $sp.Write("t"+$ids[$i]+$d+$data[$i]+"`r"); $sent++ }catch{}
    $i++
  }
  if($i -ge $t.Count){ $i=0; $loop++ }      # loop the settled state
  try{ $c=$sp.ReadExisting() }catch{ $c="" }
  if($c){ $buf+=$c }
  while($buf.Contains("`r")){
    $j=$buf.IndexOf("`r"); $l=$buf.Substring(0,$j).Trim(); $buf=$buf.Substring($j+1)
    if($l.Length -lt 5 -or $l[0] -ne 't'){ continue }
    $id=$l.Substring(1,3)
    if(-not ($skipIds -contains $id)){ continue }   # only the PCM's own ids
    $dl=[Convert]::ToInt32($l.Substring(4,1),16)
    $pl = if($l.Length -ge 5+$dl*2){ $l.Substring(5,$dl*2) } else { "" }
    if(-not $rx.ContainsKey($id)){ $rx[$id]=0; $forms[$id]=@{} }
    $rx[$id]++; $forms[$id][$pl]=1
  }
  Start-Sleep -Milliseconds 1
}
Cmd 'C'; $sp.Close()
Write-Output "$sent frames sent, $loop loops"
Write-Output "=== what the PCM says back ==="
foreach($id in ($rx.Keys | Sort-Object)){
  foreach($f in @($forms[$id].Keys)){
    Write-Output ("  {0}  n={1,-5} {2}" -f $id,$rx[$id],(($f -split '(..)' | Where-Object {$_}) -join ' '))
  }
}
