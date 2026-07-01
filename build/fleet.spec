# PyInstaller spec — single-file `fleet` binary (Linux) / `fleet.exe` (Windows).
# Build:  pyinstaller build/fleet.spec
# Produces dist/fleet (or dist/fleet.exe). --cards/textual is intentionally excluded.
import sys

block_cipher = None

a = Analysis(
    ["../fleet.py"],
    pathex=["."],
    binaries=[],
    datas=[],
    hiddenimports=[],
    excludes=["textual", "rich", "fleet_cards"],
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
    name="fleet",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,          # a terminal app — keep the console
    disable_windowed_traceback=False,
)
