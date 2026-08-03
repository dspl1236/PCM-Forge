# Hold the bus awake with periodic traffic while capturing.
#
# The PCM sleeps after ~1.2s of silence, so a passive capture only ever sees
# a wake burst. Sustained traffic is what a car provides and what the unit is
# waiting for -- this is the minimum restbus needed to keep it talking.
param([string]$Port="COM5", [int]$Rate=500, [int]$Seconds=30,
      [int]$KeepMs=50, [string]$LogFile="")
$rates = @{ 100='S3'; 250='S5'; 500='S6' }
$sp = New-Object System.IO.Ports.SerialPort $Port,115200,'None',8,'One'
$sp.ReadTimeout=100; $sp.WriteTimeout=500
$sp.Open()
function Cmd($c){ try{ $sp.Write($c+"`r"); Start-Sleep -Milliseconds 120 }catch{} }
Cmd 'C'; $sp.DiscardInBuffer(); Cmd $rates[$Rate]; Cmd 'O'
Write-Output "keeping bus awake every ${KeepMs}ms, capturing ${Seconds}s at ${Rate}k"

$count=@{}; $vals=@{}; $lastSeen=@{}; $total=0; $buf=""
$sw=[Diagnostics.Stopwatch]::StartNew()
$nextKeep=0.0
while($sw.Elapsed.TotalSeconds -lt $Seconds){
  if($sw.Elapsed.TotalMilliseconds -ge $nextKeep){
    try{ $sp.Write("t7DF80000000000000000`r") }catch{}
    $nextKeep = $sw.Elapsed.TotalMilliseconds + $KeepMs
  }
  try{ $c=$sp.ReadExisting() }catch{ $c="" }
  if($c){ $buf+=$c }
  while($buf.Contains("`r")){
    $i=$buf.IndexOf("`r"); $l=$buf.Substring(0,$i).Trim(); $buf=$buf.Substring($i+1)
    if($l.Length -lt 5 -or $l[0] -ne 't'){ continue }
    $id=$l.Substring(1,3)
    if($id -eq '7DF'){ continue }                 # our own keepalive
    $d=[Convert]::ToInt32($l.Substring(4,1),16)
    $data = if($l.Length -ge 5+$d*2){ $l.Substring(5,$d*2) } else { "" }
    $total++
    if(-not $count.ContainsKey($id)){ $count[$id]=0; $vals[$id]=@{} }
    $count[$id]++; $vals[$id][$data]=1
    $lastSeen[$id]=$sw.Elapsed.TotalSeconds
    if($LogFile){ Add-Content $LogFile ("{0:F1} {1} {2}" -f $sw.Elapsed.TotalMilliseconds,$id,$data) }
  }
  Start-Sleep -Milliseconds 4
}
Cmd 'C'; $sp.Close()

Write-Output ""
Write-Output "=== $total frames, $($count.Count) IDs over ${Seconds}s ==="
Write-Output ("{0,-5} {1,7} {2,9} {3,7}  {4}" -f "ID","count","rate/s","forms","payload  (XX = varies)")
foreach($id in ($count.Keys | Sort-Object)){
  $forms=@($vals[$id].Keys); $n=[int]($forms[0].Length/2)
  $mask=@()
  for($b=0;$b -lt $n;$b++){
    $seen=@{}; foreach($f in $forms){ if($f.Length -ge $b*2+2){ $seen[$f.Substring($b*2,2)]=1 } }
    $mask += if($seen.Count -gt 1){ "XX" } else { @($seen.Keys)[0] }
  }
  Write-Output ("{0,-5} {1,7} {2,9:F1} {3,7}  {4}" -f `
    $id,$count[$id],($count[$id]/$Seconds),$forms.Count,($mask -join ' '))
}
Write-Output ""
Write-Output "last seen (s): " + (($lastSeen.Keys | Sort-Object | ForEach-Object { "{0}={1:F0}" -f $_,$lastSeen[$_] }) -join '  ')
