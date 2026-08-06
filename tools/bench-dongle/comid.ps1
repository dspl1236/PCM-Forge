<#
.SYNOPSIS
    Work out which serial port is which, without guessing from device IDs.

.DESCRIPTION
    The Cerberus enumerates as a Teensy dual-serial device, so it claims two
    COM ports off one USB interface: one takes "TX:RX:REQUEST" commands, the
    other is a pure sniffer that only streams received frames. The USB
    interface number does not reliably say which is which, so ask them.

    For each port: listen passively first (a sniffer talks unprompted, a
    command port does not), then try PING with both line endings.

    Opens and closes each port cleanly. Nothing is transmitted onto CAN.
#>
param(
    [string[]]$Ports = @("COM5", "COM6", "COM7"),
    [int]$Baud = 115200,
    [int]$ListenMs = 2500
)

foreach ($name in $Ports) {
    Write-Host "=== $name ==="
    $sp = New-Object System.IO.Ports.SerialPort $name, $Baud, "None", 8, "One"
    $sp.ReadTimeout = 1000
    $sp.WriteTimeout = 1000
    try {
        $sp.Open()
        Start-Sleep -Milliseconds 1200      # let the device settle
        $sp.DiscardInBuffer()

        # 1. passive listen -- does it stream on its own?
        $spew = ""
        $end = (Get-Date).AddMilliseconds($ListenMs)
        while ((Get-Date) -lt $end) {
            if ($sp.BytesToRead -gt 0) { $spew += $sp.ReadExisting() }
            Start-Sleep -Milliseconds 100
        }
        if ($spew.Trim()) {
            $lines = @($spew -split "`r?`n" | Where-Object { $_.Trim() })
            Write-Host ("  unprompted: {0} lines in {1} ms" -f $lines.Count, $ListenMs)
            foreach ($l in $lines[0..([Math]::Min(3, $lines.Count - 1))]) {
                Write-Host "     | $l"
            }
        }
        else {
            Write-Host "  unprompted: silent"
        }

        # 2. does it answer a command?
        foreach ($pair in @(@("LF", "`n"), @("CRLF", "`r`n"))) {
            $sp.DiscardInBuffer()
            $sp.Write("PING" + $pair[1])
            Start-Sleep -Milliseconds 600
            $r = ""
            if ($sp.BytesToRead -gt 0) { $r = $sp.ReadExisting().Trim() }
            $shown = $r
            if (-not $shown) { $shown = "(nothing)" }
            if ($shown.Length -gt 60) { $shown = $shown.Substring(0, 60) + "..." }
            Write-Host ("  PING {0,-4} -> {1}" -f $pair[0], $shown)
        }

        # 3. slcan version query.
        #
        # NOT a bare "V". Cerberus's is_slcan_cmd() treats a single-character
        # O/C/L/V/F/N as an SLCAN command and silently latches the board into
        # Lawicel mode, which its firmware only leaves on a hardware reset --
        # so the obvious probe bricks the command protocol until someone walks
        # over and replugs it. "INFO" identifies a Cerberus safely, and a real
        # CANable answers V to the same line because it ignores the rest.
        $sp.DiscardInBuffer()
        $sp.Write("INFO`r`n")
        Start-Sleep -Milliseconds 500
        $v = ""
        if ($sp.BytesToRead -gt 0) { $v = $sp.ReadExisting().Trim() }
        if ($v) { Write-Host "  INFO      -> $v" } else { Write-Host "  INFO      -> (nothing)" }
    }
    catch {
        Write-Host "  cannot open: $($_.Exception.Message)"
    }
    finally {
        if ($sp -and $sp.IsOpen) { $sp.Close() }
        $sp.Dispose()
    }
    Write-Host ""
}
