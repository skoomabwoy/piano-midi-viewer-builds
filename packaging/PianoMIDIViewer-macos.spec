# -*- mode: python ; coding: utf-8 -*-
"""
Optimized PyInstaller spec file for Piano MIDI Viewer (macOS)

Produces a .app bundle (--onedir --windowed mode) suitable for lipo
combining into a universal2 build.

Optimizations applied:
1. Exclude unnecessary Qt modules (PDF, WebEngine, Quick, QML, etc.)
2. Exclude unnecessary Qt plugins and native libraries
3. Strip debug symbols
4. Remove non-English translations
"""

import os
from PyInstaller.utils.hooks import collect_all

# Project root is one directory up from this spec file
PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))

# Collect rtmidi with all its dependencies
rtmidi_datas, rtmidi_binaries, rtmidi_hiddenimports = collect_all('rtmidi')

a = Analysis(
    [os.path.join(PROJECT_ROOT, 'piano_viewer.py')],
    pathex=[],
    binaries=rtmidi_binaries,
    datas=[
        (os.path.join(PROJECT_ROOT, 'assets', 'JetBrainsMono-Regular.ttf'), '.'),
    ] + rtmidi_datas,
    hiddenimports=rtmidi_hiddenimports,
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

# Filter out unnecessary binaries (macOS naming conventions)
def filter_binaries(binaries):
    """Remove unnecessary Qt components and libraries."""
    exclude_patterns = [
        # Unnecessary Qt native libraries (macOS framework names)
        'QtPdf',
        'QtNetwork',       # Qt networking not used (Python urllib handles updates)
        'QtQuick',
        'QtQml',
        'QtDesigner',
        'QtHelp',
        'QtMultimedia',
        'QtWebEngine',
        'QtShaderTools',
        'QtQuick3D',
        'QtOpenGL',
    ]

    # Patterns that must NOT be excluded (protect needed libraries)
    keep_patterns = [
        'QtCore',
        'QtGui',
        'QtWidgets',
        'QtSvg',
        'QtDBus',
    ]

    filtered = []
    for item in binaries:
        name = item[0] if isinstance(item, tuple) else item
        # Check if this matches an exclude pattern
        excluded = False
        for pattern in exclude_patterns:
            if pattern in name:
                # Make sure it's not a false positive on a needed library
                if not any(keep in name and keep != pattern for keep in keep_patterns):
                    excluded = True
                    break
        if excluded:
            print(f"  [EXCLUDED] {name}")
        else:
            filtered.append(item)

    return filtered

# Filter out unnecessary Qt plugins
def filter_qt_plugins(binaries):
    """Remove Qt plugins we don't need."""
    exclude_plugin_patterns = [
        # PDF image format plugin
        'libqpdf',
        # Offscreen/minimal platforms - not needed for desktop app
        'libqoffscreen',
        'libqminimal',
        # Touch input plugin - not needed
        'libqtuiotouchplugin',
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

# Remove non-English translation files to save space
def filter_translations(datas):
    """Keep only English translations."""
    filtered = []
    removed_count = 0
    for item in datas:
        name = item[0] if isinstance(item, tuple) else item
        if '/translations/' not in name or '_en' in name or '_en.' in name:
            filtered.append(item)
        else:
            removed_count += 1
    print(f"  [EXCLUDED] {removed_count} non-English translation files")
    return filtered

a.datas = filter_translations(a.datas)
print("=" * 60 + "\n")

pyz = PYZ(a.pure)

# macOS: bootloader executable only (libraries go in COLLECT)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PianoMIDIViewer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=False,  # UPX not reliable on macOS
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# Collect all files into a directory
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=True,
    upx=False,
    upx_exclude=[],
    name='PianoMIDIViewer',
)

# Wrap in a macOS .app bundle
app = BUNDLE(
    coll,
    name='PianoMIDIViewer.app',
    icon=os.path.join(PROJECT_ROOT, 'icon.icns'),
    bundle_identifier='com.skoomabwoy.pianomidiviewer',
)
