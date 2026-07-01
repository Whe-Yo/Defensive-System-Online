# PyInstaller spec — single-file `dso` binary (Linux) / `dso.exe` (Windows).
# Build:  pyinstaller build/dso.spec
# Produces dist/dso (or dist/dso.exe). --cards/textual is intentionally excluded.
import sys

block_cipher = None

a = Analysis(
    ["../dso.py"],
    pathex=["."],
    binaries=[],
    datas=[],
    hiddenimports=[],
    excludes=["textual", "rich", "dso_cards"],
    hookspath=[],
    runtime_hooks=[],
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="dso",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,          # a terminal app — keep the console
    disable_windowed_traceback=False,
)
