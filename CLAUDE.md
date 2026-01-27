# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Piano MIDI Viewer is a PyQt6-based desktop application that displays a visual piano keyboard responding to MIDI input in real-time. It's designed for music education and online lessons via OBS.

**Single-file architecture**: The entire application is contained in `piano_viewer.py` (~2100 lines).

**Current Version: 6.3.5**

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
- **MIDI sustain pedal support**: Recognizes CC 64 messages to sustain notes
- **Mouse interaction**: Click keys to toggle them on/off, drag for glissando
- **Shift key as sustain**: Hold Shift to sustain notes clicked with mouse
- **Sustain button (S)**: Toggle sustain on/off with visual indicator
- **Smart glissando**: ON mode (paint notes) or OFF mode (erase notes) determined by initial click
- **Out-of-range sustain**: Notes sustained outside visible range stay highlighted when octave expanded
- **Error correction**: Click/play sustained notes again to toggle them off

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
- **Color sync fix**: S button and plus button glows now update immediately when highlight color changes

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
   - Maintains six note tracking sets:
     - `active_notes` - MIDI notes currently pressed (visible range)
     - `active_notes_left/right` - MIDI notes pressed outside visible range
     - `sustained_notes` - Notes held by sustain (visible range)
     - `sustained_notes_left/right` - Sustained notes outside visible range
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
   - Three sustain state booleans (`sustain_button_toggled`, `sustain_pedal_active`, `shift_key_active`)
   - Property `is_sustain_active` - unified check for any sustain source
   - Five note display settings (`show_octave_numbers`, `show_white_key_names`, `show_black_key_names`, `black_key_notation`, `show_names_when_pressed`)
   - Keyboard event handlers for Shift key press/release
   - Enforces window resize constraints in `resizeEvent()`
   - Three-column layout: S button/+/- (left) | piano (center) | ⚙️/+/- (right)

3. **`SettingsDialog` (QDialog)** - Configuration interface
   - MIDI device selection with refresh button
   - Highlight color picker (QColorDialog)
   - **NEW in 6.0:** Show Octave Numbers checkbox (default: ON)
   - **NEW in 6.0:** White Key Names checkbox (default: ON)
   - **NEW in 6.0:** Black Key Names checkbox (default: OFF)
   - **NEW in 6.0:** Black key notation dropdown (♭ Flats / ♯ Sharps / Both)
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
- Sustain pedal (CC 64 >= 64) moves released notes to sustained sets

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
- No external icon files needed
- Ensures identical appearance across Windows/Linux

**Button Typography**: All button labels (S, +, −) use JetBrains Mono for cross-platform consistency

## Code Organization

The file is organized in clearly marked sections with comment banners:

```
CONSTANTS         - Sizing, colors, MIDI ranges, window margins
APP ICONS         - SVG-based icons (create_piano_icon, create_settings_icon)
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
- `PianoMIDIViewer.is_sustain_active` - Property for unified sustain check
- `PianoMIDIViewer.keyPressEvent/ReleaseEvent()` - Shift key handling
- `PianoMIDIViewer.clear_all_sustained_notes()` - Clears all sustain sets
- `PianoMIDIViewer.update_sustain_button_visual()` - S button appearance

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

**Six note tracking sets:**
- `active_notes` - MIDI notes currently pressed (visible range)
- `active_notes_left/right` - Notes pressed outside visible range
- `sustained_notes` - Notes held by sustain (visible range)
- `sustained_notes_left/right` - Sustained notes outside visible range

**Sustain System:**
Three ways to activate sustain (OR logic):
- Click S button (sticky toggle)
- Hold MIDI sustain pedal (CC 64 >= 64)
- Hold Shift key

When sustain is active:
- Note Off events move notes to `sustained_notes` instead of clearing them
- Pressing a sustained note again toggles it off (error correction)
- Out-of-range sustained notes tracked invisibly
- Releasing sustain clears all sustained notes

**Takeover behavior:**
- Pressing pedal/Shift while S is toggled → S turns off, control transfers
- Clicking S while holding pedal/Shift → S toggles on (makes it sticky)

**Out-of-range indicators:**
- When notes are played outside the visible range, the corresponding + button glows
- Glow persists for sustained notes (even when key released)
- When octave expanded, sustained notes appear highlighted

### Mouse Interaction

**Click behavior:**
- Without sustain: Click highlights note, release clears it
- With sustain: Click toggles note on/off (stays highlighted until clicked again or sustain released)

**Glissando (drag) behavior:**
Determined by initial click:
- Start on **empty note** → ON glissando (drag paints notes)
- Start on **highlighted note** → OFF glissando (drag erases notes)

Mode is locked for entire drag:
- ON glissando: Only adds notes, ignores already-highlighted notes
- OFF glissando: Only removes notes, ignores already-empty notes
- Grey background gaps ignored (glissando continues across them)

**Hit detection (5.0.1 enhancement):**
- Black keys checked first (drawn on top, so take priority)
- White keys checked second
- If click lands on gap, snaps to closest key center (prevents missed clicks during lessons)
- Glissando still flows smoothly across gaps during drag

## Styling Conventions

- **Arch Blue** default highlight: `#5094d4` (QColor(80, 148, 212))
- **Button size**: Fixed 44px (BUTTON_SIZE constant)
- **Button icons**: Font size is 70% of button size (ICON_SIZE_RATIO = 0.7)
- **Layout margins**: Hardcoded at 5px (LAYOUT_MARGIN), don't scale with window
- **Key corner radius**: 8% of key width with 4px minimum (KEY_CORNER_RADIUS_RATIO = 0.08)
- **Keyboard canvas**: Grey background (120, 120, 120), 4px margin, 6px rounded corners
- **White keys**: Off-white (252, 252, 252) with shadow lines (170), borders normal (85) / highlighted (25)
- **Black keys**: Near-black (16, 16, 16) with black borders

## Future Features & Ideas

*No planned features at this time. Feature requests welcome via issue tracker.*

## Development Notes

- No test suite currently exists
- All UI strings are hardcoded (no i18n)
- MIDI device connection errors print to console
- Version number in docstring (currently 6.2.0)
- Extensive inline comments for educational purposes and code continuity
- Cross-platform: Linux (run from source) and Windows (standalone .exe)
