# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Piano MIDI Viewer is a PyQt6-based desktop application that displays a visual piano keyboard responding to MIDI input in real-time. It's designed for music education and online lessons via OBS.

**Single-file architecture**: The entire application is contained in `piano_viewer.py` (~2300 lines).

**Current Version: 8.2.2**

### Changes in 8.2.2
- **Restart fix for compiled builds**: `restart_app()` now handles PyInstaller frozen binaries correctly
- Detects `sys.frozen` to use the binary path directly instead of `sys.executable` + script args
- Clears `_MEIPASS2` and `_PYI_ARCHIVE_FILE` env vars so the child process extracts its own temp directory
- Sets `cwd` to the binary's directory for `--onedir` bundle compatibility

### Changes in 8.2.1
- **Settings dialog**: Removed all `scaled()` calls — Settings now renders at native size regardless of UI scale
- **Update button**: Fixed width to prevent layout blink when checking for updates
- **Restart button**: Moved inline to UI Scale row (between label and dropdown)
- **Version label**: Doubles as update result (shows "Up to date" temporarily, then reverts to version)

### Changes in 8.2.0
- **MIDI hot-plug detection**: Automatic device scanning every 3 seconds
- **Auto-reconnect**: Previously used device reconnects automatically when plugged back in
- **Graceful disconnect**: Keys go dark, sustain resets, button glows clear on device unplug
- **Toast notification**: Overlay on piano canvas shows connect/disconnect messages (auto-hides after 3s)
- **Hardened polling**: `poll_midi_messages()` triggers disconnect handling on exceptions
- **VERSION constant**: Single source of truth for version string (replaces hardcoded strings)
- **Version display**: Version number shown in Settings dialog
- **Check for Updates**: Button in Settings checks Codeberg API for newer releases
- **Restart button**: "Restart to apply" button for UI scale changes (replaces text hint)

### Changes in 8.1.3
- **VERSION constant**: Single source of truth for version (was added here, consolidated in 8.2.0)
- **Version label and update checker**: Added to Settings dialog
- **Restart button**: For applying UI scale changes without manual restart

### Changes in 8.1.2
- **UI scaling**: 25–200% scale with `scaled()` helper and `make_button_style()` consolidation
- **P keyboard shortcut**: Toggle pencil tool on/off (guarded by `not event.modifiers()`)
- **GitHub Actions CI**: Manual-only trigger (`workflow_dispatch`), no auto-build on push
- **Custom app icon**: `icon.svg` for Windows (.ico) and macOS (.icns) builds
- **macOS build fix**: Switched from `--onefile` to `--onedir` for proper universal2 lipo support

### Changes in 8.1.1
- **S button**: Removed hover/pressed visual feedback — now a true non-interactive indicator
- Removed `button_style` from sustain button setup; `update_sustain_button_visual()` called at `init_ui()` end to apply non-interactive stylesheet on startup

### Changes in 8.1.0
- **Note highlight behavior**: Notes only highlight while physically pressed — sustain pedal no longer keeps notes lit
- **S button**: Now a pure indicator — lights up when MIDI sustain pedal (CC 64) is held, not clickable
- **Removed**: `sustained_notes`, `sustained_notes_left`, `sustained_notes_right` sets
- **Removed**: `sustain_button_toggled`, `shift_key_active`, `is_sustain_active`, `toggle_sustain_button()`, `clear_all_sustained_notes()`
- **Removed**: Shift key as sustain source, `keyReleaseEvent()`
- **Removed**: Sustain note migration in octave add/remove methods
- **Pencil + octave range**: Shrinking range now glows the + button if drawn notes fall outside; expanding clears it; deactivating pencil clears glows
- **Import cleanup**: `QFontMetrics` moved to top-level import (was re-imported on every text render)
- **Code cleanup**: Removed 100-line version changelog from module docstring, fixed stale comments

### Changes in 8.0.0
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
- **Sustain always toggle**: Simple click to toggle, no hold-to-activate, no mode-dependent behavior
- **Sustain works in playing**: Sustain now moves released notes to sustained_notes (was restricted to Drawing mode)
- **Button layout**: Pencil + octaves (left), Settings + Sustain + octaves (right)
- **Button size**: Reduced from 44px to 36px to fit 4 buttons per column
- **Removed**: Mode switching, eventFilter, Drawing mode checkbox, [behavior] settings section
- **Removed**: QPainter-drawn cursors, QPolygonF/QPointF, ERASER_CURSOR_DELAY, _eraser_cursor_timer, _eraser_cursor_shown

### Changes in 7.0.0
- **Two modes**: Drawing mode (for teaching) and Playing mode (for performance)
- **Drawing mode (✎)**: Notes stay highlighted, click to toggle, drag to paint/erase
- **Playing mode (♪)**: Notes highlight only while pressed, like a real piano
- **Mode button**: Shows current mode icon, acts as sustain indicator, controls sustain
- **Mode button behavior**: Click to toggle (Drawing) or hold like pedal (Playing)
- **Quick mode switch**: Right-click mode button to toggle between modes
- **Detailed tooltips**: Hover over mode button for full explanation
- **Settings checkbox**: "Drawing mode" toggle in Settings dialog
- **Button text centering**: Fixed vertical alignment of button icons (baseline compensation)

### Changes in 6.3.5
- **macOS docs**: Added `xattr -cr` command to README for Gatekeeper quarantine fix

### Changes in 6.3.4
- **macOS support**: Standalone `.app` bundle now available via Releases
- **All major platforms**: Linux, Windows, and macOS standalone apps
- **Dynamic key gaps**: Scale proportionally with key width (3%, clamped 1-5px per side)
- **Shadow effects disabled at small sizes**: Improves text readability below 25px key width
- **Fixed button overlap**: Minimum window height now enforces button requirements (Windows/macOS fix)

### Changes in 6.3.3
- **Adaptive button text**: S, +, − button text now changes color based on highlight luminance
- **Consistent behavior**: Buttons now match note name behavior (black text on light backgrounds, white on dark)

### Changes in 6.3.2
- **Octave range persistence**: Keyboard range (start_note, end_note) now saved to settings file
- **Window geometry restoration**: Size and position properly restored on startup
- **OBS-friendly**: Perfect for video production - restart the app and it remembers your exact setup
- **Enhanced visual contrast**: Darker background (150→120), crisper borders (120→85), deeper black keys (26→16) for sharper OBS capture
- **Fixed minimum window size**: Now dynamically updates when octaves are added/removed, preventing UI overlap

### Changes in 6.3.1
- **Cross-platform UI consistency**: Buttons now render identically on Windows and Linux
- **SVG settings icon**: Replaced Unicode emoji cogwheel (⚙️) with embedded SVG gear
- **JetBrains Mono buttons**: S, +, − buttons now use the bundled font for consistent appearance
- **Better minus character**: Using proper minus sign (−) instead of hyphen for vertical centering

### Changes in 6.3.0
- **Linux standalone app**: No Python installation required, just download and run
- **Optimized build**: Reduced Linux binary size from 83 MB to 56 MB (excluded duplicate ICU libs, unused Qt modules)
- **Build configuration**: `PianoMIDIViewer.spec` added for reproducible PyInstaller builds

### Changes in 6.2.0
- **Windows support**: Standalone `.exe` available via Releases (built with PyInstaller)
- **Cross-platform**: Now runs on both Linux and Windows

### Changes in 6.1.0
- **Show names only when pressed**: New Settings toggle to display note names only on active keys
- **Educational focus**: Helps students focus on relevant note names without visual clutter
- **Octave numbers unaffected**: Always visible for navigation regardless of the new setting
- **Smart enable/disable**: Checkbox greyed out when both white and black key names are off

### Changes in 6.0.2
- **Documentation**: Updated README.md with new features and changelog
- **Screenshots**: Updated screenshots showcasing note names and accidentals

### Changes in 6.0.1
- **Text rendering fix**: Font size now correctly calculated using proper pixel-to-point conversion
- **Text positioning fix**: Now accounts for font descent, ensuring consistent gaps between key edge, note letter, and octave number
- **Code cleanup**: Simplified text positioning logic for all three display cases

### Major Features (6.0.0)
- **Note names and octave numbers**: Fully customizable display of musical notation on keys
- **Octave numbering**: Numbers displayed on all C keys (replaced single Middle C dot)
- **White key names**: Show natural note names (C, D, E, F, G, A, B) on white keys
- **Black key names**: Show accidentals with three options: Flats (♭), Sharps (♯), or Both
- **Adaptive text layout**: Text automatically stacks vertically on narrow keys for readability
- **Smart text contrast**: Text color dynamically adapts based on highlight color brightness (luminance-based)
- **Dynamic positioning**: When both note names and octave numbers enabled, numbers jump to top of C keys
- **Embedded typography**: JetBrains Mono font embedded for consistent, professional appearance across platforms
- **Settings persistence**: All display preferences saved to config file

### Major Features (5.0.0)
- **MIDI sustain pedal support**: Recognizes CC 64 messages (indicator only as of 8.1.0)
- **Mouse interaction**: Click keys to toggle them on/off, drag for glissando
- **Smart glissando**: ON mode (paint notes) or OFF mode (erase notes) determined by initial click

### Changes in 5.2.0
- **Info link**: Clickable link to project repository in settings dialog (https://codeberg.org/skoomabwoy/piano-midi-viewer)

### Changes in 5.1.0
- **Settings persistence**: All user preferences now save automatically to `~/.config/piano-midi-viewer/settings.ini`
- **MIDI device**: Last selected device reconnects on startup
- **Highlight color**: Color preference persisted between sessions
- **Window geometry**: Size and position restored on launch
- **Resize limits**: On/off preference saved

### Changes in 5.0.1
- **Gap click tolerance**: Clicking between keys now snaps to the closest key (easier chord clicking during lessons)
- **Highlighted key borders**: White keys now have visible dark borders when highlighted, matching black key appearance
- **Visual improvements**: Darker background grey (150, 150, 150) for better white key contrast
- **Color sync fix**: Mode button and plus button glows now update immediately when highlight color changes

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
- rtmidi - MIDI input handling

The project uses a Python virtual environment in `venv/`.

## Key Constants and Constraints

**MIDI Range:**
- Full range: A0 to C8 (MIDI notes 21-108)
- Default display: C3 to B5 (MIDI notes 48-83, 3 octaves)
- Minimum span: 1 octave (12 notes, enforced by button state logic)
- Maximum span: 7 octaves

**Sizing:**
- Initial key dimensions: 25px width × 150px height (ratio 6:1)
- Absolute minimums: 15px width × 30px height (always enforced)
- Ratio limits (always enforced): width 0.1-0.7× height, height 3-6× width
- Black key size: 80% of white key width, 60% of keyboard height

**Performance:**
- MIDI polling interval: 10ms (100Hz)
- Rendering: On-demand via Qt's update() mechanism

## Architecture

### Component Structure

The application follows a **single-file, class-based PyQt6 architecture** with four main components:

1. **`PianoKeyboard` (QWidget)** - Custom widget that renders the piano keyboard
   - Draws white and black keys using QPainter
   - Maintains four note tracking sets:
     - `active_notes` - MIDI notes currently pressed (visible range)
     - `active_notes_left/right` - MIDI notes pressed outside visible range
     - `drawn_notes` - Notes marked by pencil tool (visible range only)
   - Mouse interaction tracking (`mouse_held_note`, `glissando_mode`)
   - Handles visual styling (colors, dimensions, rounded corners)
   - Renders note names and octave numbers with adaptive layout
   - Helper method `_get_main_window()` to access parent window
   - Hit detection `_get_note_at_position()` for mouse clicks
   - Text rendering methods: `_draw_white_key_text()`, `_draw_black_key_text()`

2. **`PianoMIDIViewer` (QMainWindow)** - Main application window
   - Manages MIDI connection and polling via QTimer
   - Controls keyboard note range (start_note, end_note)
   - Handles octave addition/removal (+/- buttons)
   - `sustain_pedal_active` - tracks CC 64 pedal state for the S indicator
   - `pencil_active` - whether pencil drawing tool is active
   - Five note display settings (`show_octave_numbers`, `show_white_key_names`, `show_black_key_names`, `black_key_notation`, `show_names_when_pressed`)
   - Keyboard event handler for Esc key (exits pencil tool)
   - Enforces window resize constraints in `resizeEvent()`
   - Three-column layout: ✎/+/- (left) | piano (center) | ⚙️/S/+/- (right)

3. **`SettingsDialog` (QDialog)** - Configuration interface
   - MIDI device selection with refresh button
   - Highlight color picker (QColorDialog)
   - Show Octave Numbers checkbox (default: ON)
   - White Key Names checkbox (default: ON)
   - Black Key Names checkbox (default: OFF)
   - Black key notation dropdown (♭ Flats / ♯ Sharps / Both)
   - Project info link (opens browser to Codeberg repository)

4. **Helper functions** - MIDI note calculations and text rendering
   - `is_black_key()` - Determines if MIDI note is a black key
   - `count_white_keys()` - Counts white keys in a range
   - `get_white_key_index()` - Gets position index of a white key
   - `get_left_white_key()` - Finds white key left of a black key
   - `calculate_initial_window_size()` - Computes starting window dimensions
   - **NEW in 6.0:** `get_text_color_for_highlight()` - Calculates optimal text color (black/white) based on background luminance
   - **NEW in 6.0:** `calculate_font_size_for_width()` - Calculates font size to fit characters in a target width
   - **NEW in 6.0.1:** `calculate_font_size_for_height()` - Calculates font size to fit characters in a target height
   - **NEW in 6.0:** `get_note_name()` - Returns note name (C, D, E, etc.) for MIDI note
   - **NEW in 6.0:** `get_octave_number()` - Returns octave number for MIDI note
   - **NEW in 6.0:** `get_black_key_name()` - Returns sharp/flat/both names for black keys

### Key Architectural Concepts

**Sizing System**: Everything is calculated from a single white key's dimensions
- Constants define initial key size (`INITIAL_KEY_WIDTH`, `INITIAL_KEY_HEIGHT`)
- Window size is derived from key count × key dimensions
- Ratio limits enforce aspect ratio constraints (always enforced)
- Absolute minimums always enforced (`ABSOLUTE_MIN_KEY_WIDTH/HEIGHT`)

**MIDI Handling**: Polling-based (not callback)
- `QTimer` calls `poll_midi_messages()` every 10ms
- Processes three message types:
  - Note On (0x90 with velocity > 0)
  - Note Off (0x80 or 0x90 with velocity 0)
  - Control Change (0xB0) for sustain pedal (CC 64)
- Updates note sets and triggers repaints
- Out-of-range notes trigger button glow effects
- Sustain pedal (CC 64 >= 64) sets `sustain_pedal_active` and updates S indicator (no note migration)

**Dynamic Range**: Keyboard supports 3-7 octave display
- Default: 3 octaves (C3-B5, MIDI 48-83)
- Add/remove octaves via +/- buttons
- Range: A0-C8 (MIDI 21-108)
- Window resizes to maintain key proportions when range changes

**Rendering**: All drawing happens in `PianoKeyboard.paintEvent()`
- Grey rounded canvas background
- White keys drawn first, then black keys on top
- Active notes use highlight color
- Proportional sizing based on widget dimensions
- **NEW in 6.0:** Text rendered last (note names and octave numbers)

**Text Rendering** (NEW in 6.0): Adaptive typography system
- Font: JetBrains Mono (embedded), fallback to system monospace
- Font size scales with key WIDTH (white keys: width/2.0, black keys: width/1.8)
  - Ensures text grows when window stretched horizontally, not vertically
  - More intuitive scaling behavior
- Minimum readable size: 8pt (text hidden if smaller)
- Text color: Dynamic contrast based on key state
  - Normal white keys: Black text
  - Normal black keys: White text
  - Highlighted keys: Luminance-based (black on light, white on dark)
- White key positioning:
  - Note names at bottom center
  - Octave numbers at top center (for C keys only)
  - When both enabled: numbers jump to top, letters stay at bottom
- Black key positioning:
  - Text at top center
  - Adaptive layout: Horizontal when wide ("C#"), vertical when narrow ("C\n#")
  - Both mode: 2-line or 4-line stack depending on width
- Text margins: 4px minimum or 15% of black key width (whichever is larger)

**Icon Generation**: All icons created at runtime from embedded SVG
- `create_piano_icon()` - App icon (piano keys in Arch Blue)
- `create_settings_icon()` - Cogwheel gear for settings button (CC0 from SVG Repo)
- `create_pencil_cursor()` - SVG pencil cursor, white fill + colored outline, tip at bottom-left
- `create_eraser_cursor()` - SVG eraser cursor, white fill + colored outline, edge at bottom-left
- `create_pencil_icon()` - SVG pencil icon for button (transparent fill, color-aware outline)
- `_render_svg_to_pixmap()` - Shared SVG-to-QPixmap renderer (injects width/height, uses loadFromData)
- `PENCIL_SVG`, `ERASER_SVG` - Embedded SVG string constants (source files: `pencil.svg`, `eraser.svg`)
- Cursor SVGs use two-layer approach: white fill path (opaque interior) + black detail path on top
- Button icon strips white fill (`fill="none"`) for transparent background on button
- No external icon files needed at runtime (SVGs embedded as strings)
- Ensures identical appearance across all platforms

**Button Typography**: All button labels (S, +, −) use JetBrains Mono for cross-platform consistency

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

Key additions in 6.3.4:
- Constants: `KEY_GAP_RATIO`, `KEY_GAP_MIN`, `KEY_GAP_MAX`, `SHADOW_DISABLE_WIDTH`, `BUTTON_SPACING`, `MIN_BUTTON_AREA_HEIGHT`, `MIN_WINDOW_HEIGHT`
- Dynamic key gap calculation in `_draw_white_key()` and `_get_note_at_position()`
- Shadow rendering conditional on key width >= `SHADOW_DISABLE_WIDTH`
- Minimum window height now uses `max(key_based_height, MIN_WINDOW_HEIGHT)`
- `PianoMIDIViewer-macos.spec` - PyInstaller spec file for macOS builds

Key changes in 8.0.0:
- `PianoKeyboard.drawn_notes` - New set for pencil tool marks (visible range only)
- `PianoKeyboard` - `setContextMenuPolicy(PreventContextMenu)` to block right-click menu
- `PianoMIDIViewer.pencil_active` - Whether pencil tool is active
- `PianoMIDIViewer.toggle_pencil()` - Enters/exits pencil drawing tool
- `PianoMIDIViewer.update_pencil_button_visual()` - Updates pencil button icon color and lit/unlit state
- `PianoMIDIViewer.toggle_sustain_button()` - Simple sustain toggle (replaces complex eventFilter) — **removed in 8.1.0**
- `create_pencil_cursor()` - SVG-rendered pencil cursor (uses `PENCIL_SVG`, `CURSOR_OUTLINE_COLOR`, `CURSOR_FILL_COLOR`)
- `create_eraser_cursor()` - SVG-rendered eraser cursor (uses `ERASER_SVG`, `CURSOR_OUTLINE_COLOR`, `CURSOR_FILL_COLOR`)
- `create_pencil_icon()` - SVG pencil icon for button with color parameter (transparent fill, colored outline)
- `_render_svg_to_pixmap()` - Shared helper to render SVG string to QPixmap at given size
- `PENCIL_SVG` - Embedded pencil SVG constant (source: `pencil.svg` from SVG Repo)
- `ERASER_SVG` - Embedded eraser SVG constant (source: `eraser.svg` from SVG Repo)
- Constants: `CURSOR_SIZE` (24), `CURSOR_OUTLINE_COLOR` ('#707070'), `CURSOR_FILL_COLOR` ('#ffffff')
- Removed: `sticky_sustain`, `update_sustain_button_text()`, `eventFilter()`, `toggle_sticky_sustain()`
- Removed: `_eraser_cursor_shown`, `_eraser_cursor_timer`, `_show_eraser_cursor()`, `ERASER_CURSOR_DELAY`
- Removed: Drawing mode checkbox from SettingsDialog, `[behavior]` settings section
- Removed: `QPolygonF`, `QPointF` imports (QPainter-drawn cursors replaced by SVG)
- `BUTTON_SIZE` reduced from 44 to 36, `MIN_BUTTON_AREA_HEIGHT` now 4 buttons + 3 gaps
- Modified `handle_note_on()` - Pencil mode toggles drawn_notes, playing mode adds to active_notes
- Modified `handle_note_off()` - Pencil mode ignores Note Off, playing mode removes from active_notes
- Modified mouse events - Left click draws, right click erases (replaces detect-initial-target logic)
- Highlight check now includes `drawn_notes` in all rendering methods, guarded for erase mode
- Button layout: pencil icon (left top), sustain "S" (right under settings)

Key additions in 7.0.0 (superseded by 8.0.0):
- Mode system (Drawing/Playing) — removed in 8.0.0
- eventFilter for mode button — removed in 8.0.0

Key additions in 6.3.3:
- `update_sustain_button_visual()` - Now uses `get_text_color_for_highlight()` for adaptive text color
- `apply_button_glow()` - Now uses `get_text_color_for_highlight()` for adaptive text color

Key additions in 6.3.2:
- Extended `save_settings()` to save keyboard range (start_note, end_note) in new `[keyboard]` section
- Extended `load_settings()` to restore keyboard range before geometry restoration
- Keyboard range validated on load: must be within MIDI_NOTE_MIN/MAX and at least 1 octave
- `update_minimum_size()` - New method to recalculate minimum window size based on current octave range
- All octave add/remove methods now call `update_minimum_size()` after changing the range

Key additions in 6.1.0:
- `PianoMIDIViewer.show_names_when_pressed` - New setting to show note names only on active keys
- `SettingsDialog.names_when_pressed_checkbox` - New checkbox control below accidentals dropdown
- `SettingsDialog.toggle_names_when_pressed()` - Callback for the new checkbox
- Modified `toggle_white_key_names()` and `toggle_black_key_names()` to enable/disable the new checkbox
- Modified `_draw_white_key_text()` - Skips note names (not octave numbers) when key not active
- Modified `_draw_black_key_text()` - Skips names when key not active
- Extended `save_settings()` and `load_settings()` for the new setting

Key additions in 6.0.1:
- `calculate_font_size_for_height()` - Properly converts pixel height to font point size using font metrics
- Fixed `_draw_white_key_text()` - Uses descent for accurate text positioning with consistent gaps
- Fixed `_draw_black_key_text()` - Same height-based font sizing fix applied

Key additions in 6.0.0:
- Import of `QFontDatabase` from PyQt6 for font loading
- Constants: `NOTE_NAMES_WHITE`, `NOTE_NAMES_BLACK_SHARPS/FLATS`, font rendering ratios
- Helper functions: `get_text_color_for_highlight()`, `calculate_font_size_for_width()`, `get_note_name()`, `get_octave_number()`, `get_black_key_name()`
- `PianoKeyboard._draw_white_key_text()` - Renders note names and octave numbers on white keys
- `PianoKeyboard._draw_black_key_text()` - Renders accidental names on black keys with adaptive layout
- Removed: `PianoKeyboard._draw_middle_c_indicator()` (replaced by octave numbers on all C keys)
- `PianoMIDIViewer` members: `show_octave_numbers`, `show_white_key_names`, `show_black_key_names`, `black_key_notation`
- `SettingsDialog` controls: 3 checkboxes + 1 dropdown for note display options
- `SettingsDialog` callbacks: `toggle_octave_numbers()`, `toggle_white_key_names()`, `toggle_black_key_names()`, `notation_changed()`
- Extended `save_settings()` and `load_settings()` to persist note display preferences
- Font loading in `main()` - loads JetBrainsMono-Regular.ttf with fallback

Key additions in 5.0.0:
- `PianoKeyboard._get_main_window()` - Helper to access parent window
- `PianoKeyboard._get_note_at_position()` - Hit detection for mouse
- `PianoKeyboard.mousePressEvent/MoveEvent/ReleaseEvent()` - Mouse interaction
- `PianoMIDIViewer.update_sustain_button_visual()` - S button indicator appearance

Key additions in 5.2.0:
- Import of `QUrl` and `QDesktopServices` from PyQt6 for URL handling
- Info link in SettingsDialog using QLabel with rich text and `setOpenExternalLinks(True)`

Key additions in 5.1.0:
- `get_config_path()` - Returns platform-specific config file path (~/.config/piano-midi-viewer/settings.ini)
- `PianoMIDIViewer.load_settings()` - Loads all preferences from config file on startup
- `PianoMIDIViewer.save_settings()` - Saves all preferences to config file
- Settings auto-save on: MIDI device change, color change, note display options change, window close

Key additions in 5.0.1:
- `PianoKeyboard._find_closest_note_to_position()` - Snaps gap clicks to nearest key
- `SettingsDialog.choose_color()` - Now updates all UI elements when color changes
- Enhanced white key borders with darker outlines when highlighted

## Important Implementation Details

### Resizing Behavior

The `resizeEvent()` method enforces constraints using simple clamping:
- **Always enforced**: Absolute minimums (15px width, 30px height per key)
- **Always enforced**: Ratio limits (width 0.1-0.7× height, height 3-6× width)

**Logic**:
1. Get current window size
2. Enforce absolute minimums
3. Calculate key dimensions
4. If ratio too wide → reduce width
5. If ratio too narrow → reduce height
6. Apply the constrained size

Simple, predictable behavior without complex edge detection.

### Octave Management

When adding/removing octaves:
1. Calculate current key width
2. Update MIDI note range (±12 semitones)
3. Calculate new window width to maintain key width
4. Resize window
5. Update button states (disable if at min/max range)

### MIDI Message Processing

**Message types handled:**
- Note On: Status byte 0x90 with velocity > 0
- Note Off: Status byte 0x80, or 0x90 with velocity = 0
- Control Change: Status byte 0xB0 (for sustain pedal, CC 64)

**Four note tracking sets:**
- `active_notes` - MIDI notes currently pressed (visible range)
- `active_notes_left/right` - Notes pressed outside visible range
- `drawn_notes` - Notes marked by pencil tool (visible range only)

**Pencil Tool:**
The pencil button (left side, SVG icon) activates a drawing tool independent from playing:
- Click pencil button to enter/exit drawing mode
- Press Esc to exit drawing mode
- Cursor changes to pencil cursor when active
- Left click/drag draws notes, right click/drag erases notes
- Eraser cursor shown during right-click erase, restores to pencil on release
- Keys under cursor do NOT highlight during erase (guarded by `glissando_mode != 'off'`)
- MIDI Note On toggles notes in `drawn_notes` (visible range only)
- MIDI Note Off is ignored (marks persist)
- Exiting clears all drawn marks and playing state

**Sustain Indicator (S button):**
- S button is a read-only indicator — not clickable
- Lights up when MIDI sustain pedal (CC 64 >= 64) is held
- Does not affect note highlighting

**Playing Behavior (default, no pencil):**
- Notes highlight only while physically pressed, go dark immediately on release
- Mouse click highlights a key while held, clears on release

**Out-of-range indicators:**
- When notes are played outside the visible range, the corresponding + button glows
- In pencil mode: shrinking the range glows the + button if drawn notes fall outside; deactivating pencil clears the glow

### Mouse Interaction

**Click behavior (playing, no pencil):**
- Click highlights note while held, clears on release

**Click behavior (pencil active):**
- Left click: adds note to `drawn_notes`, sets `glissando_mode = 'on'`
- Right click: removes note from `drawn_notes`, sets `glissando_mode = 'off'`, shows eraser cursor
- Other mouse buttons ignored

**Glissando (drag) behavior (pencil tool):**
Determined by mouse button:
- **Left drag** → ON glissando (paints notes, pencil cursor stays)
- **Right drag** → OFF glissando (erases notes, eraser cursor shown)

Mode is locked for entire drag (determined by initial button press):
- ON glissando: Only adds notes to `drawn_notes`
- OFF glissando: Only removes notes from `drawn_notes`
- Grey background gaps ignored (glissando continues across them)
- In playing mode (no pencil): left drag moves active note to new key

**Eraser cursor behavior:**
- Right mouse button press: cursor immediately switches to eraser
- Right mouse button release: cursor restores to pencil
- No delay timer, no hold-to-show logic

**Hit detection (5.0.1 enhancement):**
- Black keys checked first (drawn on top, so take priority)
- White keys checked second
- If click lands on gap, snaps to closest key center (prevents missed clicks during lessons)
- Glissando still flows smoothly across gaps during drag

## Styling Conventions

- **Arch Blue** default highlight: `#5094d4` (QColor(80, 148, 212))
- **Button size**: Fixed 36px (BUTTON_SIZE constant, reduced from 44px in 8.0.0)
- **Button icons**: Font size is 90% of button size (ICON_SIZE_RATIO = 0.9); pencil button uses SVG icon at 70% of button size
- **Cursor outline**: `CURSOR_OUTLINE_COLOR` (`#707070`) — matches button border color
- **Cursor fill**: `CURSOR_FILL_COLOR` (`#ffffff`) — opaque white interior so cursors are visible on black keys
- **Layout margins**: Hardcoded at 5px (LAYOUT_MARGIN), don't scale with window
- **Key corner radius**: 8% of key width with 4px minimum (KEY_CORNER_RADIUS_RATIO = 0.08)
- **Keyboard canvas**: Grey background (120, 120, 120), 4px margin, 6px rounded corners
- **White keys**: Off-white (252, 252, 252) with shadow lines (170), borders normal (85) / highlighted (25)
- **Black keys**: Near-black (16, 16, 16) with black borders

## Future Features & Ideas

### Accessibility (next priority)
- **Keyboard shortcuts**: Add shortcuts for common actions (toggle pencil, open settings, add/remove octave)
- **High contrast mode**: Thicker key borders, bolder outlines on active keys for low vision users and OBS at low resolutions
- **Color blind safe presets**: Preset highlight colors optimized for protanopia, deuteranopia, tritanopia — dropdown alongside custom color picker
- **Screen reader labels**: Basic QAccessible labeling (e.g., "pencil tool button, toggle", "sustain indicator, active")
- **Minimum font size setting**: User-configurable floor for note name text size (currently hidden below 8pt)

### User-facing improvements
- **MIDI device hot-plug detection**: Periodic check (every 2-3 seconds) to auto-detect connections/disconnections with brief notification
- **Graceful disconnect handling**: Clean recovery when USB MIDI device is unplugged mid-session
- **Color themes/presets**: Built-in themes (classic, dark mode for OBS, pastel for kids) — each theme = highlight color + background + key colors
- **Export drawn notes as image**: "Save as PNG" for teachers using pencil tool to mark notes
- **Velocity visualization**: Show key press intensity via color opacity or brightness
- **Live UI scaling**: Apply scale changes without requiring app restart (currently requires restart due to cached widget sizes/stylesheets)

### Developer/maintenance
- **Logging**: Replace print() with Python logging module for user-reportable debug output
- **Settings migration**: Version field in settings file with migration logic for new settings across versions
- **Error reporting dialog**: User-facing "something went wrong" dialog with copy-to-clipboard instead of silent console errors

## Development Notes

- No test suite currently exists
- All UI strings are hardcoded (no i18n)
- MIDI device connection errors print to console
- Version number in docstring (currently 8.0.0)
- Extensive inline comments for educational purposes and code continuity
- Cross-platform: Linux (run from source) and Windows (standalone .exe)
