# Targeted UDS probe. TesterPresent is acknowledged but unanswered, so try the
# requests a real tool uses: a session start, and a direct ReadDataByIdentifier
# for part number and ODX name -- which is what Cerberus does on a C7 without
# opening a session at all.
#
# A part number is longer than 7 bytes, so a positive answer arrives as an
# ISO-TP FIRST FRAME (0x10 ...). We do not send flow control, so we will see
# only that first frame -- which is all we need to prove the module replies.
param([string]$Port="COM8", [int]$Rate=500, [int]$WaitMs=250)
$idx=@{100=0;250=2;500=3}
$sp = New-Object System.IO.Ports.SerialPort $Port,115200,'None',8,'One'
$sp.ReadTimeout=120; $sp.NewLine="`n"
$sp.Open(); Start-Sleep -Seconds 2; $sp.DiscardInBuffer()
function Say($c,$w=200){ $sp.Write($c+"`n"); Start-Sleep -Milliseconds $w }
Say "x 8"; Say ("b " + $idx[$Rate]); Say "l 0"; Say "o" 700; Say "e 1"
$sp.DiscardInBuffer()

$targets = @('710','714','716','746','7E0','7E1','700','701','70A','712','713')
$reqs = @(
  @{n='SessionDefault ';h='021001'},
  @{n='SessionExtended';h='021003'},
  @{n='PartNo  22F187 ';h='0322F187'},
  @{n='ODXName 22F19E ';h='0322F19E'}
)
foreach($t in $targets){
  foreach($r in $reqs){
    $pad = ($r.h + ('55' * 8)).Substring(0,16)
    $sp.DiscardInBuffer()
    $sp.Write("t$t" + "8" + $pad + "`n")
    Start-Sleep -Milliseconds $WaitMs
    $got = $sp.ReadExisting()
    foreach($l in ($got -split "`n")){
      if($l -match '^R\s'){
        $p = $l -split '\s+'
        if($p.Count -ge 4 -and $p[2] -ne $t){
          $d = if($p.Count -ge 5){ ($p[4..($p.Count-1)] -join ' ') } else { '' }
          Write-Output ("  {0} -> {1}  [{2}]  {3}" -f $t,$p[2],$r.n.Trim(),$d)
        }
      }
    }
  }
}
Say "q"; $sp.Close()
Write-Output "done"
