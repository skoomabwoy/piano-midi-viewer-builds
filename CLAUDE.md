# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Piano MIDI Viewer is a PyQt6-based desktop application that displays a visual piano keyboard responding to MIDI input in real-time. It's designed for music education and online lessons via OBS.

**Single-file architecture**: The entire application is contained in `piano_viewer.py` (~3000 lines).

**Current Version: 8.6.2**

For full version history, see [CHANGELOG.md](CHANGELOG.md).

## Project Structure

```
piano_viewer.py          # Entire application (single-file architecture)
README.md                # User-facing documentation
CLAUDE.md                # Developer documentation (this file)
CHANGELOG.md             # Full version history
requirements.txt         # Python dependencies (loose)
requirements-lock.txt    # Pinned dependency versions (reproducible builds)
LICENSE                  # GPL-3.0

assets/                  # SVG icons and embedded font
  icon.svg               # App icon (used by CI for .ico/.icns generation)
  JetBrainsMono-Regular.ttf  # Bundled font for note labels
  pencil.svg             # Pencil cursor source SVG (CC0)
  eraser.svg             # Eraser cursor source SVG (CC0)
  camera.svg             # Camera/save icon source SVG (CC0)

packaging/               # PyInstaller build specs
  PianoMIDIViewer.spec         # Linux build spec
  PianoMIDIViewer-macos.spec   # macOS build spec

tests/                   # Test suite (pytest)

screenshots/             # README screenshots
.github/workflows/       # GitHub Actions CI (build.yml)
```

## Running the Application

```bash
# Using the Python virtual environment
source venv/bin/activate
python piano_viewer.py

# Or directly (has shebang)
./piano_viewer.py
```

## Dependencies

Core dependencies (installed in venv):
- PyQt6 - GUI framework
- python-rtmidi - MIDI input handling
- certifi - CA certificates for HTTPS in PyInstaller builds

The project uses a Python virtual environment in `venv/`.

## Key Constants and Constraints

**MIDI Range:**
- Full range: A0 to C8 (MIDI notes 21-108)
- Default display: C3 to B5 (MIDI notes 48-83, 3 octaves)
- Minimum span: 1 octave (12 notes), maximum: 7 octaves

**Sizing:**
- Initial key dimensions: 25px width x 150px height (ratio 6:1)
- Absolute minimums: 15px width x 30px height (always enforced)
- Ratio limits (always enforced): width 0.1-0.7x height, height 3-6x width
- Black key size: 80% of white key width, 60% of keyboard height

**Performance:**
- MIDI polling interval: 10ms (100Hz)
- Rendering: On-demand via Qt's update() mechanism

## Architecture

### Component Structure

The application follows a **single-file, class-based PyQt6 architecture** with four main components:

1. **`PianoKeyboard` (QWidget)** - Custom widget that renders the piano keyboard
   - Draws white and black keys using QPainter
   - Note tracking: `active_notes` (dict: note -> velocity), `drawn_notes` (set), `active_notes_left/right` (sets for out-of-range)
   - Mouse interaction tracking (`mouse_held_note`, `glissando_mode`)
   - Text rendering: `_draw_white_key_text()`, `_draw_black_key_text()`
   - Hit detection: `_get_note_at_position()`, `_find_closest_note_to_position()`

2. **`PianoMIDIViewer` (QMainWindow)** - Main application window
   - MIDI connection and polling via QTimer
   - Keyboard note range control (start_note, end_note, +/- buttons)
   - State: `sustain_pedal_active`, `pencil_active`, `show_velocity`, display settings
   - Three-column layout: pencil/+/- (left) | piano (center) | settings/S/+/- (right)

3. **`SettingsDialog` (QDialog)** - Configuration interface
   - MIDI device selection, highlight color, UI scale
   - Note display options (octave numbers, key names, accidentals, velocity)
   - Non-modal (`show()` not `exec()`) so MIDI keeps working while open

4. **Helper functions** - Pure logic, no GUI dependencies
   - MIDI note utilities: `is_black_key()`, `count_white_keys()`, `get_note_name()`, etc.
   - Text rendering: `get_text_color_for_highlight()`, `calculate_font_size_for_width/height()`
   - Config: `get_config_path()`, `migrate_settings()`

### Key Architectural Concepts

**Sizing System**: Everything derives from white key width. Constants define initial size, window size = key count x key dimensions. Ratio limits and absolute minimums always enforced.

**MIDI Handling**: Polling-based (not callback). QTimer at 10ms. Handles Note On (0x90), Note Off (0x80), Control Change (0xB0 for CC 64 sustain). Out-of-range notes trigger +button glow.

**Velocity**: `active_notes` is a dict (note -> velocity 1-127). `blend_colors()` interpolates between base and highlight color. Factor range 0.3-1.0 (soft notes always visible at 30%).

**Pencil Tool**: Independent drawing mode. Left click/drag draws to `drawn_notes` set, right click/drag erases. MIDI Note On toggles drawn_notes, Note Off ignored. Exiting clears all marks.

**Sustain Indicator**: S button is read-only — lights up when CC 64 >= 64, does not affect note highlighting.

**Settings**: Saved to `~/.config/piano-midi-viewer/settings.ini` via configparser. `SETTINGS_VERSION` constant + `migrate_settings()` for format changes. `[meta]` section tracks version.

**Logging**: Python `logging` module. Logger named `piano-midi-viewer`, levels: info (startup, connections), warning (fallbacks), error (failures).

**Icons**: All generated at runtime from embedded SVG strings (`PENCIL_SVG`, `ERASER_SVG`, etc.). `_render_svg_to_pixmap()` shared renderer. No external icon files needed at runtime.

**Text Rendering**: JetBrains Mono (embedded, fallback to system monospace). Font size scales with key width. Minimum 8pt (hidden if smaller). Dynamic contrast: black text on light, white on dark.

**UI Scaling**: `UI_SCALE_FACTOR` global, `scaled(px)` helper. 25-200% range. Requires restart to apply.

## Code Organization

The file is organized in clearly marked sections with comment banners:

```
CONSTANTS         - Sizing, colors, MIDI ranges, window margins, cursor sizing/colors
APP ICONS         - SVG-based icons and cursors (piano, settings, pencil, eraser)
HELPER FUNCTIONS  - MIDI note utilities (is_black_key, count_white_keys, etc.)
SETTINGS DIALOG   - Configuration UI (SettingsDialog class)
PIANO KEYBOARD    - Custom rendering widget (PianoKeyboard class)
MAIN WINDOW       - Application controller (PianoMIDIViewer class)
ENTRY POINT       - main() function
```

## Styling Conventions

- **Arch Blue** default highlight: `#5094d4` (QColor(80, 148, 212))
- **Button size**: Fixed 36px (BUTTON_SIZE constant)
- **Button icons**: Font size 90% of button size; pencil uses SVG at 70%
- **Cursor colors**: outline `#707070`, fill `#ffffff`
- **Layout margins**: 5px (LAYOUT_MARGIN), don't scale with window
- **Key corner radius**: 8% of key width, 4px minimum
- **Canvas**: Grey background (120, 120, 120), 4px margin, 6px rounded corners
- **White keys**: Off-white (252) with shadow (170), borders normal (85) / highlighted (25)
- **Black keys**: Near-black (16) with black borders
- **Button styling**: `make_button_style(bg_color, text_color, interactive)` function

## CI / Build

- Workflow: `.github/workflows/build.yml`, manual trigger only (`workflow_dispatch`)
- Builds: Linux (ubuntu-22.04), Windows (windows-latest), macOS ARM (macos-14) + Intel (macos-15-intel)
- macOS: `--onedir` (NOT `--onefile`) for proper universal2 lipo. ARM + Intel combined with lipo per Mach-O file
- Linux: `--onedir` + AppImage (appimagetool with static runtime, no FUSE dependency)
- Windows: `--onefile` with icon generated via ImageMagick
- App icon: `assets/icon.svg` -> .ico (Windows) / .icns (macOS via librsvg + iconutil) / .png (Linux)
- macOS DMG includes `README.txt` with xattr install instructions
- `create-release` job only runs on tag push

## Version Conventions

- **Patch** (x.x.1): Bug fixes, internal improvements, no new user-facing features
- **Minor** (x.1.0): New user-facing features
- **Major** (x.0.0): Breaking changes or major UX reworks

## Future Features & Ideas

### High priority
- ~~**Test suite**: Unit tests for helper functions~~ Done in 8.5.3 — 67 tests in `tests/`

### Accessibility
- **High contrast mode**: Thicker key borders, bolder outlines for low vision users and OBS at low resolutions
- **Color blind safe presets**: Preset highlight colors for protanopia, deuteranopia, tritanopia — needs verification method before implementing
- **Screen reader labels**: Basic QAccessible labeling
- **Keyboard shortcuts**: Low priority, may cancel — only P shortcut exists currently

### User-facing improvements
- ~~**Export drawn notes as image**: "Save as PNG" for teachers~~ Done in 8.6.0
- **Live UI scaling**: Apply scale changes without restart

### Website (landing page)
- Single-page static site (HTML/CSS/JS, no frameworks)
- Hosting: Codeberg Pages -> custom domain later
- Interactive piano demo, OS-detected downloads, scroll-triggered animations
- Strategy doc in memory file `website-strategy.md`

### Distribution
- **Flatpak packaging**: Investigate for broader Linux desktop integration

### Developer/maintenance
- ~~**Error reporting dialog**: User-facing "something went wrong" with copy-to-clipboard~~ Done in 8.6.0

## Development Notes

- Settings saved to `~/.config/piano-midi-viewer/settings.ini`
- All UI strings are hardcoded (no i18n)
- MIDI errors logged via `logging` module (replaced print() in 8.5.1)
- Cross-platform: Linux (AppImage), Windows (.exe), macOS (.dmg)
- Git hooks: post-commit auto-pushes to both remotes (Codeberg + GitHub)
