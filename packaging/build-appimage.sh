#!/bin/bash
# Build a local Linux AppImage for testing.
#
# Mirrors the .github/workflows/build.yml Linux job, but for your own machine.
# NOTE: a locally-built AppImage leans on your host libraries and is less
# portable than the CI artifact — use it for testing, ship the CI build.
#
# Usage:  ./packaging/build-appimage.sh
# Requires: an activated venv with deps + pyinstaller, ImageMagick (magick),
#           curl.  appimagetool is downloaded on first run and cached at repo root.

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "==> PyInstaller build"
pyinstaller --noconfirm packaging/linux.spec

echo "==> Generate icon"
magick piano_viewer/resources/images/icon.png -resize 256x256 piano-midi-viewer.png

echo "==> Assemble AppDir"
rm -rf PianoMIDIViewer.AppDir
mkdir -p PianoMIDIViewer.AppDir/usr/bin
cp -a dist/PianoMIDIViewer/* PianoMIDIViewer.AppDir/usr/bin/
cp piano-midi-viewer.png PianoMIDIViewer.AppDir/piano-midi-viewer.png

cat > PianoMIDIViewer.AppDir/AppRun << 'APPRUN'
#!/bin/bash
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/PianoMIDIViewer" "$@"
APPRUN
chmod +x PianoMIDIViewer.AppDir/AppRun

cat > PianoMIDIViewer.AppDir/piano-midi-viewer.desktop << 'DESKTOP'
[Desktop Entry]
Name=Piano MIDI Viewer
Exec=PianoMIDIViewer
Icon=piano-midi-viewer
Type=Application
Categories=AudioVideo;Audio;Music;Education;
DESKTOP

if [ ! -x appimagetool ]; then
    echo "==> Fetch appimagetool (cached after first run)"
    curl -sL https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage -o appimagetool
    chmod +x appimagetool
fi

echo "==> Build AppImage"
ARCH=x86_64 ./appimagetool PianoMIDIViewer.AppDir PianoMIDIViewer-x86_64.AppImage

echo "==> Clean intermediates"
rm -rf PianoMIDIViewer.AppDir piano-midi-viewer.png

echo "==> Done"
ls -lh PianoMIDIViewer-x86_64.AppImage
