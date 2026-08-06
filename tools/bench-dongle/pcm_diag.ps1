<#
.SYNOPSIS
    Talk KWP2000 to the PCM over the diagnostic bus, through Cerberus.

.DESCRIPTION
    Replays what the Autel was observed doing on 2026-08-04, one step at a
    time, so we can see which step -- if any -- actually brings the screen up.
    The capture could not settle that on its own: the PCM was already answering
    diagnostics before the tool ever addressed it, and it rebooted several
    times during sustained tester activity without any single frame lining up
    with the screen coming on.

    Everything here is read-only or session/routine control. No WriteDataBy*,
    no RequestDownload, no ClearDiagnosticInformation -- nothing that changes
    stored state, so a wrong guess costs a reboot at worst.

    Cerberus speaks one ASCII line per request, "TX:RX:REQUEST", and does the
    ISO-TP framing itself. Its line ending is not documented, so PING probes
    both and the rest of the run uses whichever answered.

.EXAMPLE
    .\pcm_diag.ps1 -Port COM6 -Step probe
    .\pcm_diag.ps1 -Port COM6 -Step session -Hold 30
#>
param(
    [string]$Port = "COM6",
    [int]$Baud = 115200,
    [ValidateSet("probe", "session", "ident", "routines", "all")]
    [string]$Step = "probe",
    [int]$Hold = 30
)

$PcmTx = "773"
$PcmRx = "7DD"

$Svc = @{
    0x10 = "StartDiagnosticSession"; 0x14 = "ClearDiagnosticInformation"
    0x18 = "ReadDTCByStatus";        0x1A = "ReadEcuIdentification"
    0x22 = "ReadDataByCommonId";     0x27 = "SecurityAccess"
    0x31 = "StartRoutineByLocalId";  0x32 = "StopRoutineByLocalId"
    0x33 = "RequestRoutineResults";  0x3E = "TesterPresent"
}
$Nrc = @{
    0x11 = "serviceNotSupported";    0x12 = "subFunctionNotSupported"
    0x22 = "conditionsNotCorrect";   0x23 = "routineNotComplete"
    0x31 = "requestOutOfRange";      0x33 = "securityAccessDenied"
    0x35 = "invalidKey";             0x78 = "responsePending"
    0x80 = "noActiveSession"
}

# The identity block the Autel read once it had unlocked. 9F answers without
# security; the rest came back only after a successful 27 01 / 27 02.
$Ident = @(
    @("90", "VIN field"), @("91", "part number"), @("95", "software version"),
    @("9F", "diagnostic status"), @("01", "Porsche part number"),
    @("94", "hardware"), @("83", "coding")
)

# Routines the Autel started, in order. 0B reads back a two-byte state rather
# than acting; 29 was rejected after 41 s of responsePending, so it is omitted.
$Routines = @(
    @("1701", "routine 17, param 01"),
    @("2E01", "routine 2E, param 01"),
    @("0B",   "routine 0B (returns state)")
)

$script:Term = "`n"

function Read-Reply($sp) {
    # Read whatever arrives rather than ReadLine, so an unknown terminator
    # cannot hang us.
    Start-Sleep -Milliseconds 350
    $out = ""
    $deadline = (Get-Date).AddMilliseconds(1500)
    while ((Get-Date) -lt $deadline) {
        if ($sp.BytesToRead -gt 0) {
            $out += $sp.ReadExisting()
            Start-Sleep -Milliseconds 120
        }
        elseif ($out.Length -gt 0) { break }
        else { Start-Sleep -Milliseconds 60 }
    }
    return $out.Trim()
}

function Send-Raw($sp, [string]$text) {
    $sp.DiscardInBuffer()
    $sp.Write($text + $script:Term)
    return (Read-Reply $sp)
}

function ConvertFrom-Kwp([string]$hex) {
    if ([string]::IsNullOrWhiteSpace($hex)) { return "" }
    $hex = ($hex -replace '[^0-9A-Fa-f]', '')
    if ($hex.Length -lt 2) { return "" }
    $b = New-Object byte[] ($hex.Length / 2)
    for ($i = 0; $i -lt $b.Length; $i++) {
        $b[$i] = [Convert]::ToByte($hex.Substring($i * 2, 2), 16)
    }
    if ($b[0] -eq 0x7F -and $b.Length -ge 3) {
        $s = $Svc[[int]$b[1]]; if (-not $s) { $s = "{0:X2}" -f $b[1] }
        $n = $Nrc[[int]$b[2]]; if (-not $n) { $n = "{0:X2}" -f $b[2] }
        return "NEG $s -> $n"
    }
    $name = $Svc[[int]($b[0] - 0x40)]
    if (-not $name) { $name = "svc{0:X2}" -f ($b[0] - 0x40) }
    $rest = ($b[1..($b.Length - 1)] | ForEach-Object { "{0:X2}" -f $_ }) -join ""
    $chars = $b[1..($b.Length - 1)] | ForEach-Object {
        if ($_ -ge 32 -and $_ -lt 127) { [char]$_ } else { "." }
    }
    $txt = -join $chars
    $printable = ($b[1..($b.Length - 1)] | Where-Object { $_ -ge 32 -and $_ -lt 127 }).Count
    if ($printable -ge [Math]::Max(1, ($b.Length - 1) * 0.6)) {
        return "$name  $rest  `"$txt`""
    }
    return "$name  $rest"
}

function Invoke-Pcm($sp, [string]$payload, [string]$note) {
    $raw = Send-Raw $sp "${PcmTx}:${PcmRx}:$payload"
    $dec = ""
    if ($raw -match 'OK:\s*([0-9A-Fa-f]+)') { $dec = ConvertFrom-Kwp $Matches[1] }
    if (-not $dec) { $dec = $raw }
    if (-not $dec) { $dec = "(no answer)" }
    "    -> {0,-10} {1,-46} {2}" -f $payload, $dec, $note
    return $raw
}

# --------------------------------------------------------------------------
$sp = New-Object System.IO.Ports.SerialPort $Port, $Baud, "None", 8, "One"
$sp.ReadTimeout = 2000
$sp.WriteTimeout = 2000
try {
    $sp.Open()
    Start-Sleep -Milliseconds 1500      # Teensy settles after enumeration
    $sp.DiscardInBuffer()

    $pong = Send-Raw $sp "PING"
    if ($pong -notmatch "PONG") {
        $script:Term = "`r`n"
        $pong = Send-Raw $sp "PING"
    }
    if ($pong -notmatch "PONG") {
        Write-Host "Cerberus did not answer PING on $Port (got: '$pong')"
        return
    }
    $t = "LF"; if ($script:Term -eq "`r`n") { $t = "CRLF" }
    Write-Host "Cerberus up on $Port (line ending $t)`n"

    if ($Step -eq "probe" -or $Step -eq "all") {
        Write-Host "[probe] is the PCM answering with no session open?"
        Invoke-Pcm $sp "3E"   "expect NEG -> noActiveSession if alive in standby" | Out-Null
        Invoke-Pcm $sp "1A9F" "diagnostic status, answers unlocked" | Out-Null
    }

    if ($Step -eq "session" -or $Step -eq "all") {
        Write-Host "`n[session] 10 89, then hold it -- does the screen come up?"
        Invoke-Pcm $sp "1089" "manufacturer session" | Out-Null
        $end = (Get-Date).AddSeconds($Hold)
        $n = 0
        while ((Get-Date) -lt $end) {
            Send-Raw $sp "${PcmTx}:${PcmRx}:3E" | Out-Null
            $n++
            Start-Sleep -Milliseconds 700
        }
        Write-Host "    held session $Hold s ($n TesterPresent)"
    }

    if ($Step -eq "ident" -or $Step -eq "all") {
        Write-Host "`n[ident] identity block (needs the unlock the Autel got)"
        Invoke-Pcm $sp "2701" "request seed" | Out-Null
        foreach ($e in $Ident) { Invoke-Pcm $sp ("1A" + $e[0]) $e[1] | Out-Null }
        Invoke-Pcm $sp "22F008" "config"     | Out-Null
        Invoke-Pcm $sp "22F009" "build date" | Out-Null
    }

    if ($Step -eq "routines" -or $Step -eq "all") {
        Write-Host "`n[routines] the ones the Autel started, one at a time"
        foreach ($r in $Routines) {
            Invoke-Pcm $sp ("31" + $r[0]) $r[1] | Out-Null
            Start-Sleep -Seconds 1
            Invoke-Pcm $sp ("33" + $r[0].Substring(0, 2)) "poll result" | Out-Null
        }
    }

    Write-Host "`ndone -- session lapses on its own once TesterPresent stops"
}
finally {
    # Always hand the port back; a held COM port is invisible until something
    # else fails to open it.
    if ($sp -and $sp.IsOpen) { $sp.Close() }
    $sp.Dispose()
}
