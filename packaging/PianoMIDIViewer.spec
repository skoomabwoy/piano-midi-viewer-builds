# -*- mode: python ; coding: utf-8 -*-
"""
Optimized PyInstaller spec file for Piano MIDI Viewer (Linux)

Optimizations applied:
1. Exclude duplicate system ICU libraries (PyQt6 bundles its own)
2. Exclude unnecessary Qt modules (PDF, WebEngine, Quick, QML, etc.)
3. Exclude unnecessary Qt plugins (VNC, EGL embedded, etc.)
4. Use UPX compression
5. Strip debug symbols
6. Remove non-English translations
"""

import os
from PyInstaller.utils.hooks import collect_all

# Project root is one directory up from this spec file
PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))

# Collect rtmidi with all its dependencies
rtmidi_datas, rtmidi_binaries, rtmidi_hiddenimports = collect_all('rtmidi')

# sounddevice is a single .py file (not a package), so collect_all() skips it.
# We need: sounddevice.py and _sounddevice.py (CFFI binding).
# libportaudio must NOT be bundled — it needs the host's PipeWire/PulseAudio stack.
sd_hiddenimports = ['sounddevice', '_sounddevice']

# PyInstaller treats some libraries as "system" and skips them, but they may be
# missing on minimal distros.  Bundle them explicitly for AppImage portability.
extra_libs = [
    '/usr/lib/x86_64-linux-gnu/libxcb-cursor.so.0',   # Qt 6.5+ xcb plugin
    '/usr/lib/x86_64-linux-gnu/libEGL.so.1',           # PyQt6 import-time dep
]
extra_binaries = [(p, '.') for p in extra_libs if os.path.exists(p)]

a = Analysis(
    [os.path.join(PROJECT_ROOT, 'piano_viewer.py')],
    pathex=[],
    binaries=rtmidi_binaries + extra_binaries,
    datas=[
        (os.path.join(PROJECT_ROOT, 'assets'), 'assets'),
        (os.path.join(PROJECT_ROOT, 'translations'), 'translations'),
    ] + rtmidi_datas,
    hiddenimports=rtmidi_hiddenimports + sd_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude heavy/unnecessary Qt modules
        'PyQt6.QtPdf',
        'PyQt6.QtPdfWidgets',
        'PyQt6.QtWebEngine',
        'PyQt6.QtWebEngineCore',
        'PyQt6.QtWebEngineWidgets',
        'PyQt6.QtWebChannel',
        'PyQt6.QtQuick',
        'PyQt6.QtQuick3D',
        'PyQt6.QtQml',
        'PyQt6.QtQmlModels',
        'PyQt6.QtDesigner',
        'PyQt6.QtHelp',
        'PyQt6.QtMultimedia',
        'PyQt6.QtMultimediaWidgets',
        'PyQt6.QtBluetooth',
        'PyQt6.QtNfc',
        'PyQt6.QtPositioning',
        'PyQt6.QtRemoteObjects',
        'PyQt6.QtSensors',
        'PyQt6.QtSerialPort',
        'PyQt6.QtSql',
        'PyQt6.QtTest',
        'PyQt6.QtXml',
        'PyQt6.Qt3DCore',
        'PyQt6.Qt3DRender',
        'PyQt6.Qt3DInput',
        'PyQt6.Qt3DLogic',
        'PyQt6.Qt3DAnimation',
        'PyQt6.Qt3DExtras',
        'PyQt6.QtCharts',
        'PyQt6.QtDataVisualization',
        'PyQt6.QtNetworkAuth',
        'PyQt6.QtOpenGL',
        'PyQt6.QtOpenGLWidgets',
        'PyQt6.QtSpatialAudio',
        'PyQt6.QtTextToSpeech',
        'PyQt6.QtSvgWidgets',
        # Standard library modules not needed
        'tkinter',
        'unittest',
        'pydoc',
        'doctest',
    ],
    noarchive=False,
    optimize=2,
)

# Filter out duplicate/unnecessary binaries
def filter_binaries(binaries):
    """Remove duplicate ICU libs and unnecessary Qt components."""
    exclude_patterns = [
        # System ICU - PyQt6 bundles its own (v73)
        'libicudata.so.78',
        'libicuuc.so.78',
        'libicui18n.so.78',
        # Unnecessary Qt libraries
        'libQt6Pdf',
        'libQt6Quick',
        'libQt6Qml',
        'libQt6Designer',
        'libQt6Help',
        'libQt6Multimedia',
        'libQt6WebEngine',
        'libQt6ShaderTools',
        'libQt6Quick3D',
        'libQt6QuickControls',
        'libQt6QuickDialogs',
        'libQt6QuickTemplates',
        'libQt6OpenGL',  # We use software rendering
        'libQt6EglFS',   # Embedded GL - not needed for desktop
        'libavcodec',    # FFmpeg codecs
        'libavformat',   # FFmpeg format
        'libavutil',     # FFmpeg util
        'libswresample', # FFmpeg audio
        'libswscale',    # FFmpeg video scaling
        # Audio backend — must use host libs for PipeWire/PulseAudio compatibility.
        # Bundling the CI's Ubuntu 22.04 versions breaks audio on modern desktops.
        'libportaudio',
        'libasound.so',
        'libjack',
    ]

    filtered = []
    for item in binaries:
        name = item[0] if isinstance(item, tuple) else item
        if not any(pattern in name for pattern in exclude_patterns):
            filtered.append(item)
        else:
            print(f"  [EXCLUDED] {name}")

    return filtered

# Filter out unnecessary Qt plugins
def filter_qt_plugins(binaries):
    """Remove Qt plugins we don't need."""
    exclude_plugin_patterns = [
        # VNC platform - not needed
        'libqvnc.so',
        # Vulkan display - not needed
        'libqvkkhrdisplay.so',
        # PDF image format plugin
        'libqpdf.so',
        # EGL device integrations for embedded systems
        'egldeviceintegrations/',
    ]

    filtered = []
    for item in binaries:
        name = item[0] if isinstance(item, tuple) else item
        if not any(pattern in name for pattern in exclude_plugin_patterns):
            filtered.append(item)
        else:
            print(f"  [EXCLUDED] {name}")

    return filtered

print("\n" + "=" * 60)
print("Filtering unnecessary binaries...")
print("=" * 60)
a.binaries = filter_binaries(a.binaries)
a.binaries = filter_qt_plugins(a.binaries)

# Remove non-English Qt translation files to save space.
# Our app's translations (translations/*.json) are kept.
def filter_translations(datas):
    """Remove Qt's built-in non-English .qm files, keep our JSON translations."""
    filtered = []
    removed_count = 0
    for item in datas:
        name = item[0] if isinstance(item, tuple) else item
        # Only filter Qt's .qm files, not our .json translations
        if name.endswith('.qm') and '/translations/' in name and '_en' not in name:
            removed_count += 1
        else:
            filtered.append(item)
    print(f"  [EXCLUDED] {removed_count} non-English Qt translation files")
    return filtered

a.datas = filter_translations(a.datas)
print("=" * 60 + "\n")

pyz = PYZ(a.pure)

# Linux: --onedir build for AppImage packaging
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PianoMIDIViewer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,  # Strip debug symbols from binaries
    upx=True,    # Use UPX compression
    upx_exclude=[
        # Don't compress these - can cause issues or slowdown
        'libpython*.so*',
    ],
    console=False,  # Windowed app, no console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=True,
    upx=True,
    upx_exclude=['libpython*.so*'],
    name='PianoMIDIViewer',
)
