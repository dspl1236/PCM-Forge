# PCM 3.1 Display Architecture — Research Notes

## Hardware
- **GPU**: Fujitsu Carmine (vid=0x10cf, did=0x202b)
- **Driver**: devg-carmine.so
- **Main display**: 800×480, ARGB1555, 60Hz
- **Secondary display**: 240×257, ARGB1555, 60Hz (cluster info?)
- **Display config**: /etc/system/config/display.conf
- **Carmine config**: /etc/system/config/carmine-pcm31-96xx-800x480_240x257_128mb.conf

## Software Stack
```
Application Layer:
  PCM3Root (main GUI)  ←→  showScreen (status PNG)
       │                        │
  layermanagerV2 (/dev/layermanager)
       │
  io-display (devg-carmine.so)
       │
  Fujitsu Carmine GPU
       │
  800×480 LCD + 240×257 cluster display
```

## showScreen Binary (53KB, SH4)
- **Usage**: `showScreen [-s] [-k] [-t N] <image.png>`
  - `-s` = steady/non-blocking (image stays, script continues)
  - `-k N` = wait for keycode N
  - `-t N` = show for N seconds
  - default = show until any keypress
- **Libraries**: libgf.so.1, libc.so.2
- **Connection**: opens /dev/layermanager via devctl()
- **API chain**: lmgrHMIConnect → lmgrRegisterDisplayable → lmgrGetVfb → img_load_file → gf_draw_blit2 → lmgrUpdateVfb
- **IPC**: also references /dev/ipc/ch8
- **Image loading**: dlopen() image codec from /etc/system/config/img.conf

## Error: lmgrHMIConnect failed
The `showscreen.log` always shows `lmgrHMIConnect failed` twice
(once for running.png, once for done.png).

### Possible Causes
1. **Timing**: copie_scr.sh runs before layermanagerV2 starts
2. **Exclusivity**: PCM3Root has exclusive HMI lock
3. **Missing device**: /dev/layermanager doesn't exist

### Investigation Needed (from PuTTY when car is on)
```sh
ls -la /dev/layermanager
pidin ar | grep -i "layer\|display\|PCM3Root"
cat /etc/system/config/img.conf
cat /etc/layermanagerV2*.cfg
```

## Alternative Display Approaches

### 1. Direct GF (bypass layer manager)
Use libgf directly: gf_dev_attach → gf_display_attach → gf_layer_attach.
Might fail if layers are locked by PCM3Root.

### 2. Secondary display (240×257)
The Carmine has TWO displays configured. PCM3Root might only use
the main 800×480. The secondary 240×257 might be available for
status images.

### 3. Timing trick
Run showScreen AFTER PCM3Root is fully initialized. The HMI
connection might be released at that point. Or use `waitfor`
before calling showScreen:
```sh
waitfor /dev/layermanager 10
showScreen -s image.png
```

### 4. Slay PCM3Root temporarily
Kill PCM3Root → display layer is freed → showScreen works →
restart PCM3Root. Risky but effective for a status flash.

### 5. Use PCM3Root's own screen mechanism
PCM3Root has boot screen support (CustomBootscreen_*.bin).
It might have a runtime status screen mechanism we can trigger.

### 6. Write to framebuffer directly
mmap() the Carmine GPU's framebuffer physical address and write
raw pixel data. Bypasses all software layers. Needs knowledge
of the Carmine register map.

### 7. Use /dev/pv/ (Process Video?)
The PCM has /dev/pv/ — this might be a video overlay device
that allows independent image display.

## Key Files to Examine
- /etc/layermanagerV2_nvidia.cfg (wait — this says nvidia but GPU is carmine?)
- /etc/system/config/display.conf (confirmed: carmine)
- /etc/system/config/img.conf (image codec config)
- /dev/layermanager (does it exist?)
- /dev/io-display/ (device entries)
- /dev/pv/ (process video?)
