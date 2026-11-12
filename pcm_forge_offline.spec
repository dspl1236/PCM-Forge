# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for PCM-Forge-Offline.exe:  pyinstaller pcm_forge_offline.spec
#
# generate_codes.py finds payloads/ and core/ next to itself (__file__); in a
# onefile build that is the unpack folder, so they are bundled at the same
# relative paths. Only what a stick needs goes in: the ksh payloads and the
# splash binary + its two frames.
a = Analysis(
    ['pcm_forge_offline.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('payloads/*.sh', 'payloads'),
        ('core/bin/forge_splash', 'core/bin'),
        ('core/lib/running.bin', 'core/lib'),
        ('core/lib/done.bin', 'core/lib'),
    ],
    hiddenimports=['_build'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='PCM-Forge-Offline',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
