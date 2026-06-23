# PCM4 / MIB2 - Feature Coding Map

Consolidated "what to write to unlock X", extracted from the factory GEM
engineering scripts. Run from a root shell (see handoff/UNLOCK_PLAYBOOK.md).
Partition `3221356628` = 0xC0040114 (coding block); `3221356656` = 0xC0040130 (cluster).

## A. RCC variant coding

`on -f rcc /ffs/extbin/apps/bin/VIPCmd ee vc <FEATURE> <0|1>`

| Feature | value in coding script |
|---------|------------------------|
| `Apple_DIO` | 1 |
| `Google_GAL` | 1 |
| `Gracenote_Local_Coverarts` | 0 |
| `Gracenote_Local_Other` | 0 |
| `Gracenote_Online_Coverarts` | 0 |
| `Gracenote_Online_Other` | 0 |
| `LGI` | 1 |
| `LTE_Modul` | 1 |
| `MyAUDI` | 1 |
| `Online_Dictation` | 1 |
| `Online_Media` | 1 |
| `Online_Navi__Google_Earth` | 1 |
| `Online_POI` | 1 |
| `Online_POI_Voice` | 1 |
| `Online_portal__Browser_Dienste` | 1 |
| `PSD_Protocol_Version` | 0 |
| `PhoneModule_OperationMode` | 0 |
| `Picture_Navi` | 1 |
| `ProbeCar_LGI` | 1 |
| `ProbeCar_VZO` | 1 |
| `RVC_Video_Input` | 1 |
| `Remote_HMI` | 1 |
| `SIMcardModeSwitch` | 0 |
| `Station_Logo_DB_Mode` | 0 |
| `Support_of_threeway_calling` | 1 |
| `Support_second_phone` | 0 |
| `UPnP` | 1 |
| `Update_Over_The_Air__UOTA` | 1 |
| `VZAPro` | 1 |
| `VZO` | 1 |
| `WIFI_Hotspot` | 1 |
| `WLAN_Client_mode` | 1 |

## B. Persistence coding bits

`/eso/bin/dumb_persistence_writer <args>`

```
-P -L 1 -O 15 0 3221356628 00
-P -L 1 -O 16 0 3221356628 00
-P -L 1 -O 28 0 3221356628 80
-P -L 1 -O 59 0 3221356628 00
-P -L 1 -O 70 0 3221356628 00
-P -L 1 -O 70 0 3221356628 80
-P -O 48 0 3221356628 00
-P -f 0 3221356656 00
-P -f 0 3221356656 02
-P -f 0 3221356656 03
-P -f 0 3221356656 04
-P 0 3221356628 0000000000
-P 0 3221356674 01
```

## C. File-flag toggles (touch = enable, rm = disable; nav layer)

| Flag file | ops seen |
|-----------|----------|
| `/etc/mcd.writable` | touch |
| `/etc/ooc.allow.reset` | rm/touch |
| `/mnt/app/navigation/ACTIVATE_VZO` | touch |
| `/mnt/app/navigation/KombiDEBUGMostInMainMap` | touch |
| `/mnt/app/navigation/TRAILER_ALWAYS` | touch |
| `/mnt/app/navigation/TRAILER_NEVER` | touch |
| `/mnt/ota/app/.pers/` | rm |
| `/mnt/ota/system/core/EBNavFreezeLog.` | touch |
| `/navigation/BT_EV` | touch |
| `/navigation/DISABLE_ETLLOC_ACTIVATION` | touch |
| `/navigation/DISABLE_OPENLR_ACTIVATION` | touch |
| `/navigation/DISABLE_TMCLOC_ACTIVATION` | touch |
| `/navigation/DUMP_LOC_REF` | touch |
| `/navigation/FORCE_EXTERNAL_GYRO` | touch |
| `/navigation/FORCE_LOS_UNKNOWN_DISPLAY` | touch |
| `/navigation/FSID_Navi_Disabled` | rm/touch |
| `/navigation/FSID_Navi_Enabled` | rm/touch |
| `/navigation/LoadStylesFromSDCard` | rm/touch |
| `/navigation/NO_FEC_SIG` | touch |
| `/navigation/USE_FEC` | touch |
| `/navigation/USE_FEC_SIG` | touch |
| `/navigation/VZOLGI_ENABLED` | touch |

_Auto-extracted from feature_scripts.txt (factory GEM scripts). Values are the
defaults seen in the coding scripts; set the feature byte to 1 to enable._