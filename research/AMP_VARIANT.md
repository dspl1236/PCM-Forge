# Amplifier variant — how the PCM decides what it is talking to

The goal that drove this: make a BOSE-equipped Cayenne present as **BURMESTER**.
The obstacle is that amplifier type is not primarily *coded* — it is **detected**,
and detection beats coding every time.

## Detection, not coding

The amplifier announces its own type over MOST via its device name. The PCM
believes what the amp says about itself, so changing a coding value does not
change the PCM's mind — the next detection cycle overwrites it.

**The fix that worked** (Part A, applied and verified on the car) was to stop
fighting the detector and feed it instead: put the Burmester content inside
`audiomixer_BOSE.txt`, so whichever file the PCM selects on a BOSE detection
already contains what we want. The variant the detector chooses no longer
matters, because both roads lead to the same configuration.

Part B — the Burmester **logo** on screen — still needs a delayed flag hook via
`debugTools.sh`, and is not done.

## The persistence side of detection

Found 2026-08-05 in `PCM3Reload` strings. Detection results are **cached as
marker files** in persistence:

```
/HBpersistence/audioAmpBOSE
/HBpersistence/audioAmpBURMESTER
```

with the code that maintains them:

```
storeAmplifierType: creating of '%s' failed/succeeded
storeAmplifierType: deleting of '%s' failed/succeeded
%s (isExtAmp=%s, isBOSE=%s)
%s cachedASK=%s cachedBOSE=%s cachedBURMESTER=%s
AudioAmplifier.HBMOSTDevice
AudioAmplifier.SGCANConnectionClient
AudioAmplifierThread
```

So the state machine is: detect over MOST -> `storeAmplifierType()` creates or
deletes a marker file -> later boots read the cached flags
(`cachedASK` / `cachedBOSE` / `cachedBURMESTER`).

**Why this matters:** the cache is an ordinary file in the writable partition.
No SecurityAccess, no PIWIS, no USB — the same access path already used for
`audiomixer_*.txt`. It is a second, more direct lever on the same decision than
rewriting mixer content.

**Untested.** Whether the cache is authoritative on a cold boot or merely a hint
that re-detection overwrites is unknown, and that distinction decides whether
this is useful at all. The obvious experiment is to create
`audioAmpBURMESTER`, delete `audioAmpBOSE`, and see which survives a boot with a
BOSE amp physically attached. Worth doing on the bench before the car.

## Related: which amp is it?

`22 F024` on the bench unit returns a 4-slot table, three empty, one holding:

```
7PP035753
```

Coded data retained from the donor car (as is the VIN in `1A 9D`) — neither
firmware binary contains any `7xx 035 xxx` string, so the PCM does not know this
number, it merely stores it. `035` is the infotainment group; the specific
component is **unidentified**.

**Settled 2026-08-05, and it is not the amplifier.** `22 F024` was read on the
991 unit and returns **the same `7PP035753`** as the Cayenne. Two different
vehicle lines, different audio systems, identical value — so the slot is
platform-wide, not equipment. Whatever it identifies, it is common to both cars
and cannot be the amp.

The identifier that *does* report fitted components is **`22 F022`**, which on
the 991 returns `7PP035593B` and `7PP919193DE` — both matching that unit's
printed label. That is where to look for equipment, not `F024`.

See `PCM_IDENTIFIERS.md` for the full readable-identifier map.
