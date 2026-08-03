# Stir, listen, repeat. Distinguishes a node that has gone bus-off from one
# that is merely asleep: bus-off stays off until it is reset, standby answers
# every time it is prodded.
param([string]$Port="COM5", [int]$Rate=500, [int]$Cycles=5,
      [int]$Listen=4, [int]$StirFrames=30)
$rates = @{ 100='S3'; 250='S5'; 500='S6' }
$sp = New-Object System.IO.Ports.SerialPort $Port,115200,'None',8,'One'
$sp.ReadTimeout=200; $sp.WriteTimeout=500
$sp.Open()
function Cmd($c){ try{ $sp.Write($c+"`r"); Start-Sleep -Milliseconds 120 }catch{} }
Cmd 'C'; $sp.DiscardInBuffer(); Cmd $rates[$Rate]; Cmd 'O'

for($cyc=1; $cyc -le $Cycles; $cyc++){
  # stir
  for($i=0;$i -lt $StirFrames;$i++){ try{ $sp.Write("t7DF80000000000000000`r") }catch{}; Start-Sleep -Milliseconds 4 }
  Start-Sleep -Milliseconds 120
  $sp.DiscardInBuffer()
  # listen
  $n=0; $ids=@{}; $buf=""; $firstAt=$null
  $sw=[Diagnostics.Stopwatch]::StartNew()
  while($sw.Elapsed.TotalSeconds -lt $Listen){
    try{ $c=$sp.ReadExisting() }catch{ $c="" }
    if($c){ $buf+=$c }
    while($buf.Contains("`r")){
      $i2=$buf.IndexOf("`r"); $l=$buf.Substring(0,$i2).Trim(); $buf=$buf.Substring($i2+1)
      if($l.Length -ge 5 -and $l[0] -eq 't'){
        if($null -eq $firstAt){ $firstAt=$sw.Elapsed.TotalMilliseconds }
        $lastAt=$sw.Elapsed.TotalMilliseconds
        $n++; $ids[$l.Substring(1,3)]=1
      }
    }
    Start-Sleep -Milliseconds 10
  }
  $span = if($n -gt 0){ "{0:F0}..{1:F0}ms" -f $firstAt,$lastAt } else { "-" }
  Write-Output ("cycle {0}: {1,4} frames  {2,2} ids  window {3}" -f $cyc,$n,$ids.Count,$span)
  Start-Sleep -Seconds 2
}
Cmd 'C'; $sp.Close()
