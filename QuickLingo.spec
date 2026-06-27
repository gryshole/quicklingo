# -*- mode: python ; coding: utf-8 -*-
# Onedir build: faster startup (no TEMP extraction). Zip dist/QuickLingo/ for distribution.

from pathlib import Path

block_cipher = None

project_root = Path(SPECPATH)

datas = [
    (str(project_root / "assets"), "assets"),
    (str(project_root / "quicklingo" / "i18n" / "locales"), "quicklingo/i18n/locales"),
]

# Only modules QuickLingo imports. Avoid collect_all('PySide6') — it bundles Qt3D,
# WebEngine, QML, etc. and slows every launch when using --onefile.
hiddenimports = [
    "PySide6.QtCharts",
]

a = Analysis(
    ["main.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
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
    [],
    exclude_binaries=True,
    name="QuickLingo",
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
    icon=[str(project_root / "assets" / "quicklingo_icon.ico")],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="QuickLingo",
)
