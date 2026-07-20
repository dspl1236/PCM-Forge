# bt-aux-fix — PCM 3.1 BT / AUX Boot Fix

> ## ⏸️ PAUSED — do not use to apply the fix
>
> On-car testing (ours and WillCoder's) showed this byte-flip is **inert at boot**. The byte it flips lives in the **LastMode persistence handler**, but the boot source decision is made in a different function (`CPOnOffPresCtrl`) that is never reached that way at startup — at boot Bluetooth isn't connected yet, so the unit correctly falls to FM, and **nothing re-evaluates the source when the phone connects a few seconds later**. That's why it reverts to FM / lands on silent AUX.
>
> **The fix has to ride the *connect* event, not patch the boot decision.** A brick-safe replacement — a user-space DSI client that re-selects the source once Bluetooth connects — is in development. Until then this module is greyed out in the web toolkit and offers **only "Revert to stock"**, so anyone who already applied the old fix can cleanly roll it back.

Stops a Porsche **PCM 3.1** defaulting to **FM radio** at startup and routes a connected phone to **Bluetooth (A2DP)** instead — no FM blast, no manual AUX→BT toggle.

It's a **single self-locating byte patch** to the *live* `PCM3Root` process (`/proc/<pid>/as`). No flashing, no IFS repack — a reboot fully reverts it, so it **cannot brick** the unit.

> Builds on [WillCoder/PCM_31_AUX-BT](https://github.com/WillCoder/PCM_31_AUX-BT), who found the fix and the `/proc/as` patch primitive. His route was an IFS reflash (which bricked two bench units); this module does the same fix as a safe, reversible, **universal** runtime patch.

## Why one tool works on every car

The FM-index store instruction is **byte-identical across every region/model/facelift build** that has the bug — only its *address* moves. So `bt_fix` finds it by a unique 6-byte signature and patches whatever address it's at:

```
signature :  05 1e 01 e1 15 1e      (SH4 LE: mov.l r?,@(5,Rn); mov #1,r1; mov.l r1,@(5,Rn))
patch     :  the 0x01 at +2  ->  0x07     (FM index -> A2DP index)
```

Verified across region (CHN / ARB / RDW-USA), model (991 / Cayenne / Macan) and version (v2.00–v4.00) — different addresses, one signature, one-byte flip. **v1.00** (2013 launch firmware) lacks this code entirely, so the patcher safely does nothing on it.

## Safety

- **Runtime patch** — writes live memory; a reboot restores the stock flash image. Flash is never touched.
- **Fail-safe** — patches **only** on exactly one signature match with the byte currently `0x01`. Zero or multiple matches → no write.
- **Reversible** — Runtime mode reverts on reboot; Persistent mode reverts via the **Revert to stock** option (or `scripts/bt_hook_uninstall.sh` over SSH).

## Usage (via the PCM-Forge toolkit)

The module is **paused**: the web toolkit shows it greyed and offers only **Revert to stock**. Pick **BT / AUX Fix**, build the USB, insert after the PCM has booted. Result is logged to `bt_fix.txt` on the stick.

- **Revert to stock** — strips the `/HBpersistence` boot hook, removes the staged files, and undoes the live patch (`07 → 01`), putting the unit fully back to stock in one run. Use this to cleanly roll back a previous Runtime or Persistent install.

The **Runtime** and **Persistent** apply-modes still exist in `bt_fix_run.sh` (`$2 = runtime|persist|revert`) for reference and manual use, but are no longer offered in the builder because they don't reliably fix the boot source (see the paused note above).

## Files

```
module.json                    manifest (mode: runtime | persist | revert)
scripts/bt_fix_run.sh          run_script — $1=USBROOT $2=mode
scripts/bt_boot.sh             boot-hook body (persist mode)
scripts/bt_hook_uninstall.sh   revert the persistent hook
bin/bt_fix                     the self-locating patcher (SH4/QNX ELF)
```

`bt_fix` source, build scripts, and the offline validator live in the repo module toolchain. It's a QNX SH4 binary built with the standard `sh4-linux-gnu` cross-toolchain + a SONAME stub libc (no QNX SDK needed).

## Disclaimer

For research and personal use on your own vehicle. Not affiliated with Porsche AG. Runtime patching only — no modified firmware is shipped.
