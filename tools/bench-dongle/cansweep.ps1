# Listen at every standard bitrate in turn. Listen-only throughout: a node
# clocked to the wrong rate misreads valid traffic as errors and answers with
# error frames, which is a rude thing to do to a bus you are still identifying.
param([string]$Port="COM5", [int]$Each=6)
$rates = [ordered]@{ 1000='S8'; 800='S7'; 500='S6'; 250='S5'; 125='S4';
                     100='S3'; 50='S2'; 20='S1'; 10='S0' }
$sp = New-Object System.IO.Ports.SerialPort $Port,115200,'None',8,'One'
$sp.ReadTimeout = 200
$sp.Open()
function Cmd($c){ $sp.Write($c + "`r"); Start-Sleep -Milliseconds 150 }

$found = @()
foreach ($r in $rates.Keys) {
  Cmd 'C'; $sp.DiscardInBuffer(); Cmd $rates[$r]; Cmd 'L'
  $ids=@{}; $n=0; $buf=""
  $sw=[Diagnostics.Stopwatch]::StartNew()
  while($sw.Elapsed.TotalSeconds -lt $Each){
    try{ $c=$sp.ReadExisting() }catch{ $c="" }
    if($c){ $buf+=$c }
    while($buf.Contains("`r")){
      $i=$buf.IndexOf("`r"); $l=$buf.Substring(0,$i).Trim(); $buf=$buf.Substring($i+1)
      if($l.Length -ge 5 -and $l[0] -eq 't'){ $n++; $ids[$l.Substring(1,3)]=1 }
    }
    Start-Sleep -Milliseconds 20
  }
  Cmd 'C'
  $mark = if($n -gt 0){ "  <-- TRAFFIC" } else { "" }
  Write-Output ("{0,5}k : {1,6} frames  {2,3} ids{3}" -f $r, $n, $ids.Count, $mark)
  if($n -gt 0){ $found += "$r" + "k: " + (($ids.Keys | Sort-Object) -join ',') }
}
$sp.Close()
Write-Output ""
if($found.Count){ Write-Output "=== traffic found ==="; $found | ForEach-Object { "  $_" } }
else { Write-Output "=== silent at every bitrate ===" }
