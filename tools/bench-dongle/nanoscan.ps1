# Diagnostic address scan on the gateway's diag pair, via the Nano/MCP2515.
#
#   nanoscan.ps1 -Port COM8 -From 0x600 -To 0x7FF
#
# Sends UDS TesterPresent (service 0x3E, sub 0x00) as an ISO-TP single frame
# to each address and listens for anything at all. TesterPresent is the safest
# request in UDS -- it keeps a session alive and changes nothing -- which makes
# it the right thing to spray at addresses whose owners are unknown.
#
#   02 3E 00 55 55 55 55 55
#   ^^ ISO-TP single frame, 2 payload bytes; 0x55 is conventional padding
#
# Responses are NOT assumed to be at request+8. That mapping holds for OBD
# (7E0 -> 7E8) but this is a manufacturer bus, so every received frame is
# recorded against whatever request was outstanding.
param([string]$Port="COM8", [int]$Rate=500,
      [int]$From=0x600, [int]$To=0x7FF, [int]$GapMs=25)

$idx = @{ 100=0; 125=1; 250=2; 500=3; 1000=4; 50=5; 83=6; 33=7 }
$sp = New-Object System.IO.Ports.SerialPort $Port,115200,'None',8,'One'
$sp.ReadTimeout=100; $sp.WriteTimeout=500; $sp.NewLine="`n"
$sp.Open(); Start-Sleep -Seconds 2; $sp.DiscardInBuffer()
function Say($c){ $sp.Write($c + "`n"); Start-Sleep -Milliseconds 200 }
Say "x 8"; Say ("b " + $idx[$Rate]); Say "l 0"; Say "o"
Start-Sleep -Milliseconds 600; Say "e 1"; $sp.DiscardInBuffer()

Write-Output ("scanning 0x{0:X3}..0x{1:X3} at {2}k, TesterPresent" -f $From,$To,$Rate)
$responders = @{}
$buf = ""
for($id=$From; $id -le $To; $id++){
  $hex = "{0:X3}" -f $id
  $sp.Write("t$hex" + "8023E005555555555`n")
  $deadline = (Get-Date).AddMilliseconds($GapMs)
  while((Get-Date) -lt $deadline){
    try{ $c=$sp.ReadExisting() }catch{ $c="" }
    if($c){ $buf += $c }
    while($buf.Contains("`n")){
      $i=$buf.IndexOf("`n"); $l=$buf.Substring(0,$i).Trim(); $buf=$buf.Substring($i+1)
      if($l -match '^R\s'){
        $p = $l -split '\s+'
        if($p.Count -ge 4){
          $rid=$p[2]; $data = if($p.Count -ge 5){ ($p[4..($p.Count-1)] -join ' ') } else { "" }
          $key = "$hex -> $rid"
          if(-not $responders.ContainsKey($key)){
            $responders[$key]=$data
            Write-Output ("  REQ {0}  ANSWER from {1}  [{2}]" -f $hex,$rid,$data)
          }
        }
      }
    }
    Start-Sleep -Milliseconds 3
  }
}
Say "q"; $sp.Close()
Write-Output ""
if($responders.Count){
  Write-Output "=== $($responders.Count) responder(s) ==="
  foreach($k in ($responders.Keys | Sort-Object)){ Write-Output ("  {0}   {1}" -f $k,$responders[$k]) }
} else {
  Write-Output "=== nothing answered ==="
  Write-Output "Either the gateway does not serve diagnostics on this pair while"
  Write-Output "idle, the address is outside the scanned range, or it wants a"
  Write-Output "session opened first (0x10 0x01) before it will talk."
}
