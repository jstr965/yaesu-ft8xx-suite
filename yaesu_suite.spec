# -*- mode: python ; coding: utf-8 -*-
# Yaesu FT-8XX Suite by K3LH PyInstaller spec
# Builds a single-folder distribution for NSIS to wrap

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=[
        # PyQt6
        'PyQt6.QtWidgets',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtNetwork',
        # pyserial
        'serial',
        'serial.tools',
        'serial.tools.list_ports',
        'serial.tools.list_ports_common',
        'serial.tools.list_ports_posix',
        # sounddevice / numpy
        'sounddevice',
        'numpy',
        'numpy.core',
        'numpy.fft',
        'scipy',
        'scipy.signal',
        # stdlib
        'configparser',
        'json',
        'socket',
        'threading',
        'queue',
        'urllib',
        'urllib.request',
        'urllib.parse',
        'urllib.error',
        # app modules
        'ui.main_window',
        'ui.cat_panel',
        'ui.audio_panel',
        'ui.digital_modes_panel',
        'ui.wsjtx_panel',
        'ui.wsjtx_settings',
        'ui.log_panel',
        'ui.spotter_panel',
        'ui.waterfall_widget',
        'ui.help_window',
        'ui.theme',
        'core.cat817',
        'core.audio_engine',
        'core.logger',
        'core.spotters',
        'core.wsjtx_engine',
        'core.wsjtx_interface',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'matplotlib', 'PIL', 'cv2',
        'IPython', 'jupyter', 'notebook',
    ],
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
    name='YaesuFT8XXSuite',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # No console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',
    version_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='YaesuFT8XXSuite',
)
