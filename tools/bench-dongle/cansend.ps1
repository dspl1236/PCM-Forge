# Periodic frame transmitter. Deliberately plain: parallel arrays and an index
# loop, because mutating hashtable fields inside a foreach was silently sending
# nothing and an empty catch hid it.
#
#   cansend.ps1 -Table rest.txt -Seconds 60
#   cansend.ps1 -Table rest.txt -Only 2C1 -Seconds 30
param([string]$Table, [string]$Port="COM5", [int]$Rate=500,
      [int]$Seconds=60, [string]$Only)

$ids=@(); $pers=@(); $datas=@()
foreach($line in (Get-Content $Table)){
  if($line -match '^\s*#' -or $line.Trim() -eq ''){ continue }
  $p = ($line.Trim() -split '\s+')
  if($p.Count -lt 3){ continue }
  if($Only -and (($Only -split ',') -notcontains $p[0])){ continue }
  $ids   += $p[0]
  $pers  += [int]$p[1]
  $datas += $p[2]
}
if($ids.Count -eq 0){ Write-Output "no frames selected"; exit 1 }

$rates=@{100='S3';250='S5';500='S6'}
$sp = New-Object System.IO.Ports.SerialPort $Port,115200,'None',8,'One'
$sp.WriteTimeout=1000
$sp.Open()
function Cmd($c){ $sp.Write($c+"`r"); Start-Sleep -Milliseconds 150 }
Cmd 'C'; Cmd $rates[$Rate]; Cmd 'O'

Write-Output ("sending {0} frames for {1}s at {2}k:" -f $ids.Count,$Seconds,$Rate)
for($i=0;$i -lt $ids.Count;$i++){ Write-Output ("   {0} every {1}ms  {2}" -f $ids[$i],$pers[$i],$datas[$i]) }

$next = New-Object double[] $ids.Count
$sent = 0
$sw=[Diagnostics.Stopwatch]::StartNew()
while($sw.Elapsed.TotalSeconds -lt $Seconds){
  $now = $sw.Elapsed.TotalMilliseconds
  for($i=0;$i -lt $ids.Count;$i++){
    if($now -ge $next[$i]){
      $dlc = [int]($datas[$i].Length/2)
      $frame = "t" + $ids[$i] + $dlc + $datas[$i]
      try { $sp.Write($frame + "`r"); $sent++ }
      catch { Write-Output ("TX FAILED: " + $_.Exception.Message); $sw.Stop(); break }
      $next[$i] = $now + $pers[$i]
    }
  }
  Start-Sleep -Milliseconds 2
}
Cmd 'C'; $sp.Close()
Write-Output "$sent frames sent"
