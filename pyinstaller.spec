"""
PyInstaller spec for Launchpad Mapper.
"""

from PyInstaller.utils.hooks import Tree


datas = [Tree("templates", prefix="templates")]

a = Analysis(
    ["server.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="launchpad-mapper",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)
