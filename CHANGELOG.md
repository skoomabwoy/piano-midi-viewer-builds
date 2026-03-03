# Changelog

Full release history for Piano MIDI Viewer. For download links, see [Releases](https://codeberg.org/skoomabwoy/piano-midi-viewer/releases).

## 8.6.3
- **Font fix**: JetBrains Mono font now bundles correctly on all platforms (was missing since 8.6.1 due to spec file path mismatch after project reorganization)
- **macOS button styling**: Restart and refresh buttons in Settings now use native macOS styling (previously had square corners and cropped text)
- **AppImage restart**: Restart button now works correctly inside AppImage (uses `$APPIMAGE` env var instead of internal squashfs path)
- **AppImage portability**: Bundled `libxcb-cursor.so.0` and `libEGL.so.1` for distros that don't ship them (fixes crash on Linux Mint and similar)
- **CI smoke test**: Linux builds now include an automated smoke test and library verification step
- **Wording**: Updated tagline to "Made for music teachers, students, and content creators"

## 8.6.2
- **Fix links in AppImage**: Clickable links in Settings (update check, project info) now open the browser correctly inside AppImage — falls back to Python's `webbrowser` module when Qt's `QDesktopServices` can't reach the system browser

## 8.6.1
- **Fixed crash on corrupted settings**: Garbage in `settings.ini` no longer crashes the app — shows an error dialog with a "Reset Settings" button instead
- **Per-value settings recovery**: Individual bad values (e.g. `start_note = banana`) are reset to defaults while keeping all other settings intact — a toast shows which values were reset
- **Highlight color validation**: Invalid color values are now detected and reset to default (previously silently turned black)
- **Reset Settings button**: Error dialogs for settings errors now offer a "Reset Settings" button that deletes the config file
- **Camera icon**: Save button now shows the camera icon from `assets/camera.svg` (was blank)
- **Quick save subfolder**: Screenshots quick-save to `~/Pictures/PianoMIDIViewer/` instead of `~/Pictures/`

## 8.6.0
- **Save as PNG**: New camera button on the left column captures the piano keyboard as an image. Left-click opens a file dialog to choose filename and location. Right-click quick-saves to `~/Pictures/` with a timestamp filename
- **Error reporting dialog**: Auto-popup `ErrorDialog` when settings or MIDI scan errors occur, with error details (version, timestamp) and a "Copy to Clipboard" button for easy bug reporting
- **Startup error capture**: Errors during settings migration (before the window exists) are collected and shown once the app is ready

## 8.5.3
- **Test suite**: Added pytest with 67 tests covering all pure-logic helper functions — MIDI note classification, white key counting/indexing, note naming, octave numbers, black key accidentals, color contrast/blending, and settings migration

## 8.5.2
- **CLAUDE.md debloat**: Moved full version history to CHANGELOG.md, kept only architecture and conventions (~660 lines -> ~160 lines)
- **CHANGELOG.md**: New file with full version history from 5.0.0 to present
- **Pinned dependencies**: Added `requirements-lock.txt` with exact versions for reproducible builds
- **Committed SVG assets**: `pencil.svg`, `eraser.svg`, `new-icon.svg` now tracked in `assets/` (were untracked local files)
- **Git hook**: Post-commit hook auto-pushes to both remotes (Codeberg + GitHub)
- **Version conventions**: Documented patch/minor/major bumping rules in CLAUDE.md

## 8.5.1
- **Logging**: Replaced all `print()` calls with Python's `logging` module — `log.info()`, `log.warning()`, `log.error()` for user-reportable debug output
- **Settings migration framework**: Added `SETTINGS_VERSION` constant and `migrate_settings()` function — versioned `[meta]` section in settings.ini with sequential migration steps for future format changes
- **Expanded comments**: Comprehensive review of all comments across the entire file — beginner-friendly explanations, section headers, class docstrings, and inline notes for educational clarity (~300 lines added)
- **Project reorganization**: Moved `icon.svg` and `JetBrainsMono-Regular.ttf` into `assets/`, moved `.spec` files into `packaging/` — updated all references in piano_viewer.py, spec files, and CI workflow
- **`.gitignore` cleanup**: Added AppImage build artifact patterns

## 8.5.0
- **New app icon**: Replaced hand-drawn piano icon with CC0 icon from SVG Repo (white keys on Arch Blue background)
- **macOS update check fix**: Added `certifi` dependency for CA certificates — PyInstaller bundles don't include system CA certs, so `urlopen` over HTTPS failed silently. Now creates explicit `ssl.create_default_context(cafile=certifi.where())` for the update check
- **macOS spec**: Stopped excluding `libcrypto`/`libssl` — Python's `ssl` module needs them
- **Linux AppImage**: Linux builds now produce `.AppImage` instead of a bare binary — works out-of-the-box on Ubuntu, Mint, Fedora, Arch without extra dependencies (uses static runtime, no FUSE2/FUSE3 issues)
- **Linux spec**: Changed from `--onefile` to `--onedir` PyInstaller build to support AppImage packaging
- **macOS DMG README**: Added `README.txt` inside the DMG with step-by-step install instructions including the `xattr -cr` command with absolute path to `/Applications/PianoMIDIViewer.app`
- **Update button layout fix**: Version label now takes stretch space (stretch factor 1), button stays fixed — no more shifting when label text changes
- **Shorter error text**: "Check failed" instead of "Could not check for updates" to fit the version label area

## 8.4.0
- **Velocity visualization**: Key brightness reflects how hard each key is pressed (off by default)
- **`active_notes` dict**: Changed from `set()` to `dict()` mapping `note_number → velocity (1-127)` — `note in dict` checks keys, so all existing membership checks work unchanged
- **`blend_colors()` helper**: Linear interpolation between two QColors for velocity-aware rendering
- **Velocity factor**: Maps velocity 1-127 to 0.3-1.0 range — even soft notes are always visible (minimum 30% blend)
- **Settings checkbox**: "Show velocity brightness" in Settings dialog under note display section
- **Velocity-aware text contrast**: Note names and octave numbers adapt to blended fill color when velocity is active
- **Mouse clicks**: Always use velocity 127 (full highlight intensity)
- **Out-of-range indicators**: Plus button glow always at 100% highlight — intentionally NOT velocity-sensitive

## 8.3.0
- **Persistent MIDI scanner**: Single `rtmidi.MidiIn()` instance reused for all port listing — eliminates ALSA sequencer handle leaks
- **ALSA leak fix**: Removed all temporary `rtmidi.MidiIn()` creation from `scan_midi_devices()`, `get_midi_devices()`, `setup_device_scanning()`
- **Connect-before-disconnect**: `connect_midi_device()` verifies new device exists before closing old connection — failed connections no longer leave the app disconnected
- **Return value**: `connect_midi_device()` returns `True`/`False` for callers to react to failures
- **Dropdown auto-refresh**: Failed connection triggers `populate_midi_devices()` to remove stale entries
- **Dropdown revert**: On failed connection, dropdown reverts to the currently working device
- **MIDI status in Settings**: "Device not found" shown in red next to "MIDI Input Device:" label (auto-clears after 3s)
- **Non-modal Settings**: Changed from `dialog.exec()` to `dialog.show()` — MIDI input keeps working while Settings is open
- **Settings singleton**: Prevents opening multiple Settings windows (raises existing if visible)
- **Signal blocking**: `populate_midi_devices()` uses `blockSignals()` to prevent unwanted reconnection during list rebuild

## 8.2.2
- **Restart fix for compiled builds**: `restart_app()` now handles PyInstaller frozen binaries correctly
- Detects `sys.frozen` to use the binary path directly instead of `sys.executable` + script args
- Clears `_MEIPASS2` and `_PYI_ARCHIVE_FILE` env vars so the child process extracts its own temp directory
- Sets `cwd` to the binary's directory for `--onedir` bundle compatibility

## 8.2.1
- **Settings dialog**: Removed all `scaled()` calls — Settings now renders at native size regardless of UI scale
- **Update button**: Fixed width to prevent layout blink when checking for updates
- **Restart button**: Moved inline to UI Scale row (between label and dropdown)
- **Version label**: Doubles as update result (shows "Up to date" temporarily, then reverts to version)

## 8.2.0
- **MIDI hot-plug detection**: Automatic device scanning every 3 seconds
- **Auto-reconnect**: Previously used device reconnects automatically when plugged back in
- **Graceful disconnect**: Keys go dark, sustain resets, button glows clear on device unplug
- **Toast notification**: Overlay on piano canvas shows connect/disconnect messages (auto-hides after 3s)
- **Hardened polling**: `poll_midi_messages()` triggers disconnect handling on exceptions
- **VERSION constant**: Single source of truth for version string (replaces hardcoded strings)
- **Version display**: Version number shown in Settings dialog
- **Check for Updates**: Button in Settings checks Codeberg API for newer releases
- **Restart button**: "Restart to apply" button for UI scale changes (replaces text hint)

## 8.1.3
- **VERSION constant**: Single source of truth for version (was added here, consolidated in 8.2.0)
- **Version label and update checker**: Added to Settings dialog
- **Restart button**: For applying UI scale changes without manual restart

## 8.1.2
- **UI scaling**: 25–200% scale with `scaled()` helper and `make_button_style()` consolidation
- **P keyboard shortcut**: Toggle pencil tool on/off (guarded by `not event.modifiers()`)
- **GitHub Actions CI**: Manual-only trigger (`workflow_dispatch`), no auto-build on push
- **Custom app icon**: `icon.svg` for Windows (.ico) and macOS (.icns) builds
- **macOS build fix**: Switched from `--onefile` to `--onedir` for proper universal2 lipo support

## 8.1.1
- **S button**: Removed hover/pressed visual feedback — now a true non-interactive indicator
- Removed `button_style` from sustain button setup; `update_sustain_button_visual()` called at `init_ui()` end to apply non-interactive stylesheet on startup

## 8.1.0
- **Note highlight behavior**: Notes only highlight while physically pressed — sustain pedal no longer keeps notes lit
- **S button**: Now a pure indicator — lights up when MIDI sustain pedal (CC 64) is held, not clickable
- **Removed**: `sustained_notes`, `sustained_notes_left`, `sustained_notes_right` sets
- **Removed**: `sustain_button_toggled`, `shift_key_active`, `is_sustain_active`, `toggle_sustain_button()`, `clear_all_sustained_notes()`
- **Removed**: Shift key as sustain source, `keyReleaseEvent()`
- **Removed**: Sustain note migration in octave add/remove methods
- **Pencil + octave range**: Shrinking range now glows the + button if drawn notes fall outside; expanding clears it; deactivating pencil clears glows
- **Import cleanup**: `QFontMetrics` moved to top-level import (was re-imported on every text render)
- **Code cleanup**: Removed 100-line version changelog from module docstring, fixed stale comments

## 8.0.0
- **UX rework**: Eliminated confusing mode system (Drawing/Playing) entirely
- **Default behavior**: Keys highlight while pressed, sustain works independently
- **Pencil tool**: Separate drawing tool with dedicated button on the left side
- **Pencil button**: SVG icon (not text glyph), click to enter/exit drawing, Esc to exit, marks cleared on exit
- **Custom cursors**: SVG-based pencil and eraser cursors rendered via `_render_svg_to_pixmap()`
- **Cursor colors**: Configurable via `CURSOR_OUTLINE_COLOR` and `CURSOR_FILL_COLOR` constants
- **Left/right click**: Left click draws (pencil cursor), right click erases (eraser cursor)
- **Erase mode**: Keys under cursor do not highlight during erase (guarded by `glissando_mode != 'off'`)
- **Drawn notes**: Separate `drawn_notes` set in PianoKeyboard, independent from playing
- **Sustain moved**: Sustain button "S" now on right side under settings
- **Button layout**: Pencil + octaves (left), Settings + Sustain + octaves (right)
- **Button size**: Reduced from 44px to 36px to fit 4 buttons per column
- **Removed**: Mode switching, eventFilter, Drawing mode checkbox, [behavior] settings section
- **Removed**: QPainter-drawn cursors, QPolygonF/QPointF, ERASER_CURSOR_DELAY, _eraser_cursor_timer, _eraser_cursor_shown

## 7.0.0
- **Two modes**: Drawing mode (for teaching) and Playing mode (for performance)
- **Drawing mode (✎)**: Notes stay highlighted, click to toggle, drag to paint/erase
- **Playing mode (♪)**: Notes highlight only while pressed, like a real piano
- **Mode button**: Shows current mode icon, acts as sustain indicator, controls sustain
- **Quick mode switch**: Right-click mode button to toggle between modes
- **Settings checkbox**: "Drawing mode" toggle in Settings dialog

## 6.3.5
- **macOS docs**: Added `xattr -cr` command to README for Gatekeeper quarantine fix

## 6.3.4
- **macOS support**: Standalone `.app` bundle now available via Releases
- **Dynamic key gaps**: Scale proportionally with key width (3%, clamped 1-5px per side)
- **Shadow effects disabled at small sizes**: Improves text readability below 25px key width
- **Fixed button overlap**: Minimum window height now enforces button requirements

## 6.3.3
- **Adaptive button text**: S, +, - button text now changes color based on highlight luminance

## 6.3.2
- **Octave range persistence**: Keyboard range now saved to settings file
- **Window geometry restoration**: Size and position properly restored on startup
- **Enhanced visual contrast**: Darker background, crisper borders, deeper black keys for OBS capture
- **Fixed minimum window size**: Dynamically updates when octaves are added/removed

## 6.3.1
- **Cross-platform UI consistency**: Buttons render identically on Windows and Linux
- **SVG settings icon**: Replaced Unicode cogwheel with embedded SVG gear
- **JetBrains Mono buttons**: S, +, - buttons use bundled font

## 6.3.0
- **Linux standalone app**: No Python installation required, just download and run
- **Optimized build**: Reduced Linux binary from 83 MB to 56 MB
- **Build configuration**: `PianoMIDIViewer.spec` added for reproducible PyInstaller builds

## 6.2.0
- **Windows support**: Standalone `.exe` available via Releases

## 6.1.0
- **Show names only when pressed**: New Settings toggle for active-key-only labels

## 6.0.0
- **Note names and octave numbers**: Fully customizable display of musical notation on keys
- **Octave numbering**: Numbers on all C keys (replaced Middle C dot)
- **White/black key names**: Configurable sharps, flats, or both
- **Adaptive text layout**: Stacks vertically on narrow keys
- **Smart text contrast**: Dynamic black/white text based on highlight luminance
- **JetBrains Mono font**: Embedded for cross-platform consistency
- **Settings persistence**: All display preferences saved to config file

## 5.2.0
- **Info link**: Clickable link to project repository in settings dialog

## 5.1.0
- **Settings persistence**: All user preferences save to `~/.config/piano-midi-viewer/settings.ini`
- **MIDI device**: Last selected device reconnects on startup
- **Window geometry**: Size and position restored on launch

## 5.0.1
- **Gap click tolerance**: Clicking between keys snaps to closest key
- **Highlighted key borders**: White keys have dark borders when highlighted

## 5.0.0
- **MIDI sustain pedal support**: Recognizes CC 64 messages
- **Mouse interaction**: Click keys to toggle, drag for glissando
- **Smart glissando**: ON/OFF mode determined by initial click
