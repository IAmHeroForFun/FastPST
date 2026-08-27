# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['/mnt/data/projects/FastPST/main.py'],
    pathex=[],
    binaries=[],
    datas=[('fastpst', 'fastpst')],
    hiddenimports=['sqlite3', 'pypff', 'libpff', 'email', 'tkinter', 'PySide6', 'PySide6.QtWidgets', 'PySide6.QtCore', 'PySide6.QtGui'],
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
    name='FastPST',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
