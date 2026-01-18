"""
PyInstaller spec for Launchpad Mapper.
"""

from PyInstaller.utils.hooks import collect_all, collect_data_files
import sys
import os

# Collect all data files for Flask templates
block_cipher = None
datas = []

# Add templates directory
template_dir = os.path.join(os.getcwd(), 'templates')
if os.path.exists(template_dir):
    datas.append((template_dir, 'templates'))

# Add presets directory if it exists
presets_dir = os.path.join(os.getcwd(), 'presets')
if os.path.exists(presets_dir):
    datas.append((presets_dir, 'presets'))

# Collect Flask data files
try:
    flask_datas = collect_data_files('flask')
    datas.extend(flask_datas)
except Exception:
    pass

# Hidden imports for all dependencies
hiddenimports = [
    'mido',
    'mido.backends',
    'mido.backends.rtmidi',
    'rtmidi',
    '_rtmidi',
    'keyboard',
    'keyboard._keyboard_event',
    'keyboard._darwinkeyboard',
    'keyboard._winkeyboard',
    'keyboard._nixkeyboard',
    'keyboard._generic',
    'pynput',
    'pynput.keyboard',
    'pynput.mouse',
    'flask',
    'flask.json',
    'flask.templating',
    'flask_cors',
    'pygetwindow',
    'queue',
    'threading',
    'json',
    'time',
    'dataclasses',
    'functools',
    'itertools',
    'typing',
    'werkzeug',
    'jinja2',
    'click',
    'itsdangerous',
    'markupsafe',
]

a = Analysis(
    ["server.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="launchpad-mapper",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
