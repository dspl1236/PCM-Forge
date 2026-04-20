# PCM-Forge + MMI3G-Toolkit Session Handoff — April 20, 2026 (Updated)

## MAJOR FINDINGS THIS SESSION

### Oil Service Reset — Firmware Analysis COMPLETE

**Porsche PCM 3.1 does NOT contain oil reset code.**
- Audi MMI3GApplication has 228 CarKombi refs, 11 InspectionReset functions, full SIA system
- Porsche PCM3Root has ZERO — no CarKombiPresCtrl, no InspectionReset, no SIA
- Porsche stripped it deliberately to force dealer visits ($25-$150 per reset)
- per3 0x0010001F toggle exists in GEM ESD but no code reads it
- RESETBC_ENCODER_BLOCK_ID in Porsche is trip computer only, not service interval

**BUT: Porsche has EngineeringCANPresCtrl (Porsche-ONLY, not in Audi)**
- Connected to SGCANConnectionClient — has live CAN send capability
- SPHEngineeringCAN service proxy
- The engineering CAN screen needs to be checked on the actual car
- If it can send raw CAN frames → service reset possible from PCM touchscreen

### Key Audi API Discovered
```
SPHCarKombi::RQST_InspectionReset      — request the reset
SPHCarKombiExt::RQST_InspectionReset   — extended version
ATST_SIAOilInspection                  — oil distance/time remaining
ATST_SIAServiceData                    — service data
[Car][SIA] OilDistance / OilTime        — CAN data from cluster
[Car][SIA] InspectionDistance / InspectionTime
processStatusSIAReset                  — reset confirmation
DEVICE_LIST_SERVICE_INTERVALL           — reads per3 0x0010001F
PROTOCOLL_SWITCH_SERVICE_INTERVALL      — reads per3 0x0014004E
```

### Porsche Flashdata Status
- No "Flashdaten_Porsche" equivalent exists publicly
- Porsche distributes via PDX containers inside PIWIS VMs only
- Andrew's PIWIS VMs don't have flash data built in
- Need older PIWIS version or extract from MEGA/MHH archives
- Touareg 7P cluster uses same EV_KombiUDSRBVW526 dataset
- Symbolic IDE channels known (IDE00342, IDE03351, IDE03352)
- Literal hex DIDs NOT published anywhere

### Viable Reset Approaches (ranked)
1. **CAN capture** — sniff traffic while Durametric/iCarScan resets (reveals DIDs + security)
2. **VCDS on Cayenne** — try module 17 adaptation read (may reveal DID names even if write fails)
3. **Parse Touareg 7P ODX** — extract EV_KombiUDSRBVW526.rod from ODIS/VW flashdaten
4. **EngineeringCAN screen** — check on car, may allow raw CAN sends
5. **ESP32 DID scanner** — brute-force ReadDataByIdentifier on cluster

## REPOS
- PCM-Forge: 79 commits (1 unpushed)
- MMI3G-Toolkit: 102 commits
- Token: NEEDS ROTATION

## Unpushed Commits
- d48f25c: Research: COMPLETE oil service reset firmware analysis — Audi vs Porsche

## Files on Container
- /home/claude/PCM-Forge/ — repo with new research
- /home/claude/MMI3G-Toolkit/ — repo
- /home/claude/pcm31_inflated/ — extracted Porsche IFS1 (PCM3Root 6.6MB)
- /home/claude/audi_ifs/ — extracted Audi IFS-root (MMI3GApplication 11MB + others)
- /home/claude/audi_efs/ — extracted Audi EFS (3645 files, all ESD screens)
- /home/claude/pcm_fw/ — Porsche PCM31RDW400 firmware (from RAR)
- /home/claude/audi_fw/ — Audi MU9411 firmware (from TAR)
- /home/claude/pcm31_ifs2_decomp.bin — decompressed Porsche IFS2 (33MB, hbcifs format)

## TODO for Next Session
- [ ] Push commit d48f25c (need fresh token)
- [ ] Check EngineeringCAN screen on Andrew's car
- [ ] Try VCDS module 17 on Cayenne
- [ ] Build ESP32 DID scanner or CAN capture tool
- [ ] Find older PIWIS with embedded ODX data
- [ ] Build hbcifs extractor for Porsche IFS2
- [ ] Rotate GitHub token (URGENT)
