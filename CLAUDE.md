# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Piano MIDI Viewer is a PyQt6-based desktop application that displays a visual piano keyboard responding to MIDI input in real-time. It's designed for music education and online lessons via OBS.

**Single-file architecture**: The entire application is contained in `piano_viewer.py` (~1600 lines).

**Current Version: 5.0.1**

### Major Features (5.0.0)
- **MIDI sustain pedal support**: Recognizes CC 64 messages to sustain notes
- **Mouse interaction**: Click keys to toggle them on/off, drag for glissando
- **Shift key as sustain**: Hold Shift to sustain notes clicked with mouse
- **Sustain button (S)**: Toggle sustain on/off with visual indicator
- **Smart glissando**: ON mode (paint notes) or OFF mode (erase notes) determined by initial click
- **Out-of-range sustain**: Notes sustained outside visible range stay highlighted when octave expanded
- **Error correction**: Click/play sustained notes again to toggle them off

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
- Minimum span: ~3 octaves (enforced by button state logic)
- Maximum span: 7 octaves

**Sizing:**
- Initial key dimensions: 25px width × 162.5px height (ratio 6.5:1)
- Absolute minimums: 15px width × 30px height (always enforced)
- Ratio limits (toggleable): width 0.1-0.7× height, height 3-10× width
- Black key size: 60% of white key width, 60% of keyboard height

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
   - Draws Middle C indicator dot
   - Helper method `_get_main_window()` to access parent window
   - Hit detection `_get_note_at_position()` for mouse clicks

2. **`PianoMIDIViewer` (QMainWindow)** - Main application window
   - Manages MIDI connection and polling via QTimer
   - Controls keyboard note range (start_note, end_note)
   - Handles octave addition/removal (+/- buttons)
   - Three sustain state booleans (`sustain_button_toggled`, `sustain_pedal_active`, `shift_key_active`)
   - Property `is_sustain_active` - unified check for any sustain source
   - Keyboard event handlers for Shift key press/release
   - Enforces window resize constraints in `resizeEvent()`
   - Three-column layout: S button/+/- (left) | piano (center) | ⚙️/+/- (right)

3. **`SettingsDialog` (QDialog)** - Configuration interface (piano_viewer.py:151-269)
   - MIDI device selection with refresh button
   - Highlight color picker (QColorDialog)
   - Resizing limits toggle checkbox

4. **Helper functions** - MIDI note calculations (piano_viewer.py:106-144)
   - `is_black_key()` - Determines if MIDI note is a black key
   - `count_white_keys()` - Counts white keys in a range
   - `get_white_key_index()` - Gets position index of a white key
   - `get_left_white_key()` - Finds white key left of a black key
   - `calculate_initial_window_size()` - Computes starting window dimensions

### Key Architectural Concepts

**Sizing System**: Everything is calculated from a single white key's dimensions
- Constants define initial key size (`INITIAL_KEY_WIDTH`, `INITIAL_KEY_HEIGHT`)
- Window size is derived from key count × key dimensions
- Ratio limits enforce aspect ratio constraints (toggleable)
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

**Icon Generation**: Window and taskbar icon created at runtime
- `create_piano_icon()` function (piano_viewer.py:82-99)
- Generates QIcon from embedded SVG data
- Shows piano keys in Arch Blue theme
- No external icon files needed

## Code Organization

The file is organized in clearly marked sections with comment banners:

```
CONSTANTS         - Sizing, colors, MIDI ranges, window margins
APP ICON          - SVG-based piano icon generation (create_piano_icon)
HELPER FUNCTIONS  - MIDI note utilities (is_black_key, count_white_keys, etc.)
SETTINGS DIALOG   - Configuration UI (SettingsDialog class)
PIANO KEYBOARD    - Custom rendering widget (PianoKeyboard class)
MAIN WINDOW       - Application controller (PianoMIDIViewer class)
ENTRY POINT       - main() function
```

Key additions in 5.0.0:
- `PianoKeyboard._get_main_window()` - Helper to access parent window
- `PianoKeyboard._get_note_at_position()` - Hit detection for mouse
- `PianoKeyboard.mousePressEvent/MoveEvent/ReleaseEvent()` - Mouse interaction
- `PianoMIDIViewer.is_sustain_active` - Property for unified sustain check
- `PianoMIDIViewer.keyPressEvent/ReleaseEvent()` - Shift key handling
- `PianoMIDIViewer.clear_all_sustained_notes()` - Clears all sustain sets
- `PianoMIDIViewer.update_sustain_button_visual()` - S button appearance

Key additions in 5.0.1:
- `PianoKeyboard._find_closest_note_to_position()` - Snaps gap clicks to nearest key
- `SettingsDialog.choose_color()` - Now updates all UI elements when color changes
- Enhanced white key borders with darker outlines when highlighted

## Important Implementation Details

### Resizing Behavior

The `resizeEvent()` method enforces constraints:
- **Always enforced**: Absolute minimums (10px width, 20px height per key)
- **When enabled**: Ratio limits (width 0.1-0.7× height, height 3-10× width)
- Window is automatically resized if user drags beyond limits
- `snap_to_valid_size()` called when re-enabling limits

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
- **Keyboard canvas**: Grey background (150, 150, 150), 4px margin, 6px rounded corners
- **White keys**: Off-white (245, 245, 245) with subtle shadow lines, dark borders when highlighted (60, 60, 60)
- **Black keys**: Near-black (26, 26, 26) with black borders
- **Middle C indicator**: Small grey dot (100, 100, 100) at bottom center of MIDI note 60

## Development Notes

- No test suite currently exists
- All UI strings are hardcoded (no i18n)
- MIDI device connection errors print to console
- Version number in docstring (currently 5.0.1)
- Extensive inline comments for educational purposes and code continuity
- Linux-focused (Windows build support removed)
