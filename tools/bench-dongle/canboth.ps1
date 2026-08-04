# Transmit a restbus AND capture at the same time on one adapter.
#
# Needed because the two cannot be separated here: stop transmitting to listen
# and the PCM goes back to sleep within ~1.2s, so a listen-only pass measures
# the silence you caused. This interleaves both on one port.
#
#   canboth.ps1 -Table gw.txt -Seconds 60
param([string]$Table, [string]$Port="COM5", [int]$Rate=500,
      [int]$Seconds=60, [string]$Only, [string]$LogFile="")

$ids=@(); $pers=@(); $datas=@()
foreach($line in (Get-Content $Table)){
  if($line -match '^\s*#' -or $line.Trim() -eq ''){ continue }
  $p = ($line.Trim() -split '\s+'); if($p.Count -lt 3){ continue }
  if($Only -and (($Only -split ',') -notcontains $p[0])){ continue }
  $ids += $p[0]; $pers += [int]$p[1]; $datas += $p[2]
}
$mine = @{}; foreach($i in $ids){ $mine[$i] = 1 }

$rates=@{100='S3';250='S5';500='S6'}
$sp = New-Object System.IO.Ports.SerialPort $Port,115200,'None',8,'One'
$sp.WriteTimeout=1000; $sp.ReadTimeout=50
$sp.Open()
function Cmd($c){ $sp.Write($c+"`r"); Start-Sleep -Milliseconds 150 }
Cmd 'C'; Cmd $rates[$Rate]; Cmd 'O'
Write-Output ("transmitting {0} frames, listening, {1}s" -f $ids.Count,$Seconds)

$next = New-Object double[] $ids.Count
$sent=0; $rx=@{}; $forms=@{}; $buf=""; $firstAt=@{}
$sw=[Diagnostics.Stopwatch]::StartNew()
while($sw.Elapsed.TotalSeconds -lt $Seconds){
  $now=$sw.Elapsed.TotalMilliseconds
  for($i=0;$i -lt $ids.Count;$i++){
    if($now -ge $next[$i]){
      $dlc=[int]($datas[$i].Length/2)
      try{ $sp.Write("t"+$ids[$i]+$dlc+$datas[$i]+"`r"); $sent++ }catch{}
      $next[$i]=$now+$pers[$i]
    }
  }
  try{ $c=$sp.ReadExisting() }catch{ $c="" }
  if($c){ $buf+=$c }
  while($buf.Contains("`r")){
    $j=$buf.IndexOf("`r"); $l=$buf.Substring(0,$j).Trim(); $buf=$buf.Substring($j+1)
    if($l.Length -lt 5 -or $l[0] -ne 't'){ continue }
    $id=$l.Substring(1,3)
    if($mine.ContainsKey($id)){ continue }        # our own echo
    $d=[Convert]::ToInt32($l.Substring(4,1),16)
    $data = if($l.Length -ge 5+$d*2){ $l.Substring(5,$d*2) } else { "" }
    if(-not $rx.ContainsKey($id)){
      $rx[$id]=0; $forms[$id]=@{}; $firstAt[$id]=$now
      Write-Output ("  t={0,6:F0}ms  PCM SENDS {1}  {2}" -f $now,$id,$data)
    }
    $rx[$id]++; $forms[$id][$data]=1
    if($LogFile){ Add-Content $LogFile ("{0:F1} {1} {2} {3}" -f $now,$id,$d,$data) }
  }
  Start-Sleep -Milliseconds 2
}
Cmd 'C'; $sp.Close()
Write-Output ""
Write-Output "$sent frames sent"
Write-Output ("=== heard back: {0} ids ===" -f $rx.Count)
foreach($id in ($rx.Keys | Sort-Object)){
  $f=@($forms[$id].Keys)
  Write-Output ("  {0}  n={1,-5} forms={2}  {3}" -f $id,$rx[$id],$f.Count,$f[0])
}
if($rx.Count -eq 0){ Write-Output "  NOTHING - the PCM is not transmitting" }
