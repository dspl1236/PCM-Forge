# Capture from the Arduino/MCP2515 bench dongle (v2 sketch) over serial.
#
#   nanolisten.ps1 -Port COM8 -Rate 500 -Seconds 120 -LogFile C:\canwork\diag.log
#
# The sketch speaks lines: 'b <n>' bitrate index, 'x <8|16>' crystal,
# 'l <0|1|2>' normal/listen-only/loopback, 'o' (re)open, 'e 1' echo frames.
# Frames arrive as:  R <millis> <id> <dlc> <hex bytes...>
#
# Opened in NORMAL mode deliberately. The MCP2515's listen-only is a real
# hardware mode and does receive -- unlike the CANable's -- but it does not
# acknowledge, and a gateway alone on the diagnostic pair with nobody to ACK
# will climb TEC to 255 and stop transmitting. We need to be its partner.
param([string]$Port="COM8", [int]$Rate=500, [int]$Seconds=60,
      [string]$LogFile="", [int]$Crystal=8)

$idx = @{ 100=0; 125=1; 250=2; 500=3; 1000=4; 50=5; 83=6; 33=7 }
if (-not $idx.ContainsKey($Rate)) { Write-Output "rate $Rate not supported"; exit 1 }

$sp = New-Object System.IO.Ports.SerialPort $Port,115200,'None',8,'One'
$sp.ReadTimeout = 200; $sp.WriteTimeout = 500
$sp.NewLine = "`n"
try { $sp.Open() } catch { Write-Output "cannot open $Port : $_"; exit 1 }

# the Nano resets when the port is opened; wait for the bootloader and banner
Start-Sleep -Seconds 2
$sp.DiscardInBuffer()
function Say($c){ $sp.Write($c + "`n"); Start-Sleep -Milliseconds 250 }

Say "x $Crystal"
Say ("b " + $idx[$Rate])
Say "l 0"
Say "o"
Start-Sleep -Milliseconds 600
Say "z"
Say "e 1"
$sp.DiscardInBuffer()

Write-Output "nano on $Port at ${Rate}k, normal mode, ${Seconds}s"
$count=@{}; $vals=@{}; $firstAt=@{}; $lastAt=@{}; $total=0; $buf=""
$sw=[Diagnostics.Stopwatch]::StartNew()

while($sw.Elapsed.TotalSeconds -lt $Seconds){
  try{ $c=$sp.ReadExisting() }catch{ $c="" }
  if($c){ $buf+=$c }
  while($buf.Contains("`n")){
    $i=$buf.IndexOf("`n"); $l=$buf.Substring(0,$i).Trim(); $buf=$buf.Substring($i+1)
    if($l -notmatch '^R\s'){ continue }
    $p = $l -split '\s+'
    if($p.Count -lt 4){ continue }
    $id=$p[2]; $dlc=$p[3]
    $data = if($p.Count -ge 5){ ($p[4..($p.Count-1)] -join '') } else { "" }
    $t=$sw.Elapsed.TotalMilliseconds
    $total++
    if(-not $count.ContainsKey($id)){
      $count[$id]=0; $vals[$id]=@{}; $firstAt[$id]=$t
      Write-Output ("  t={0,7:F0}ms  NEW ID {1}  dlc={2}  {3}" -f $t,$id,$dlc,$data)
    }
    $count[$id]++; $vals[$id][$data]=1; $lastAt[$id]=$t
    if($LogFile){ Add-Content $LogFile ("{0:F1} {1} {2} {3}" -f $t,$id,$dlc,$data) }
  }
  Start-Sleep -Milliseconds 8
}
Say "q"; $sp.Close()

Write-Output ""
Write-Output "=== $total frames, $($count.Count) IDs ==="
Write-Output ("{0,-5} {1,7} {2,9} {3,7}  {4}" -f "ID","count","first ms","forms","payload (XX = varies)")
foreach($id in ($count.Keys | Sort-Object)){
  $forms=@($vals[$id].Keys); $n=[int]($forms[0].Length/2)
  $mask=@()
  for($b=0;$b -lt $n;$b++){
    $seen=@{}; foreach($f in $forms){ if($f.Length -ge $b*2+2){ $seen[$f.Substring($b*2,2)]=1 } }
    $mask += if($seen.Count -gt 1){ "XX" } else { @($seen.Keys)[0] }
  }
  Write-Output ("{0,-5} {1,7} {2,9:F0} {3,7}  {4}" -f $id,$count[$id],$firstAt[$id],$forms.Count,($mask -join ' '))
}
if($total -eq 0){ Write-Output "  (silence)" }
