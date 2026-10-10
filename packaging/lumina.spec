# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path

block_cipher = None

ROOT = Path(SPECPATH).parent.resolve()
VLC_DIR = ROOT / "vendor" / "vlc"
RESOURCES_DIR = ROOT / "lumina" / "resources"

datas = [
    (str(RESOURCES_DIR), "lumina/resources"),
]

# Paket içine libVLC çalışma zamanını kopyala (vlc/ klasörüne)
# Böylece kullanıcının ayrıca VLC kurmasına gerek kalmaz!
if VLC_DIR.exists():
    datas.append((str(VLC_DIR), "vlc"))

binaries = []

hiddenimports = [
    "charset_normalizer",
    "pymediainfo",
    "av",
    "numpy",
    "PySide6.QtSvg",
    "PySide6.QtNetwork",
    "vlc",
]

a = Analysis(
    [str(ROOT / "lumina" / "__main__.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "scipy", "notebook"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LuminaPlayer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(RESOURCES_DIR / "app.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="LuminaPlayer",
)
