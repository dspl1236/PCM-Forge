#!/bin/sh
# deploy_extras.sh — Copy QNX utility binaries to /tmp
# These are native QNX SH4 binaries from the MMI3G toolkit
USB="/fs/usb0"
TMPD=/tmp; [ -d /fs/tmpfs ] && TMPD=/fs/tmpfs

for tool in printf hd od dd; do
    if [ -f "$USB/bin/qnx-extras/$tool" ]; then
        cp "$USB/bin/qnx-extras/$tool" "$TMPD/" 2>/dev/null
        chmod +x "$TMPD/$tool" 2>/dev/null
    fi
done
