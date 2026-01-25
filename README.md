# Piano MIDI Viewer

A virtual piano keyboard that displays MIDI input in real-time or allows highlighting notes with mouse clicks. Perfect for music education, online lessons, and creating video content.

![Version](https://img.shields.io/badge/version-6.1.0-blue)
![License](https://img.shields.io/badge/license-GPL--3.0-green)
![Python](https://img.shields.io/badge/python-3.8+-blue)

## Features

- 🎹 **Real-time MIDI input tracking**
- 🖱️ **Mouse-based note highlighting**
- 🔤 **Note names on keys** - Show C, D, E, F, G, A, B on white keys
- 🔢 **Octave numbers** - Display octave numbers on all C keys
- 🎼 **Black key accidentals** - Show sharps (♯), flats (♭), or both
- 👁️ **Show names only when pressed** - Educational mode for focused learning
- 🎨 **Customizable highlight color** with smart text contrast
- ↔️ **Adjustable octave range (A0 to C8)**
- 🎵 **Flexible sustain mode** (button, pedal, or Shift key)
- 🪟 **Clean, minimal UI** with embedded JetBrains Mono font

## Screenshots

### Default Interface

![Default Interface](screenshots/default-interface.png)

*Default look with 3-octave keyboard*

*White keys name notes and octave numbers are on*

### Customizable Colors & Octave Range

![Blue Highlight - 2 Octaves](screenshots/sustained-blue-2-octaves.png)

*Arch Blue highlight (default) on 2-octave range*

![Red Highlight - 4 Octaves](screenshots/sustained-red-4-octaves.png)

*Red highlight on expanded 4-octave range*

*Octave numbers are off, flat accidentals names are on*

![Teal Highlight - Stretched](screenshots/sustained-teal-stretched.png)

*Teal highlight on 2-octave range*

*White keys note names are off, sharp accidentals names are on*

### Settings Dialog

![Settings Dialog](screenshots/settings-dialog.png)

*Settings dialog showing MIDI device selection, color picker, and resize options*

## Installation

### Prerequisites

- Python 3.8 or higher
- A MIDI input device (keyboard, controller, or virtual MIDI port)

### Quick Start

1. Clone this repository:
```bash
git clone https://codeberg.org/skoomabwoy/piano-midi-viewer.git
cd piano-midi-viewer
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Linux/Mac
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the application:
```bash
python piano_viewer.py
```

## Usage

### Basic Controls

- **Settings (⚙️)**: Configure MIDI device, highlight color, and resize limits
- **Sustain (S)**: Click to toggle sustain mode (sticky)
- **+/- buttons**: Add or remove octaves from either end of the keyboard
- **Mouse click**: Click keys to highlight them (toggle with sustain active)
- **Mouse drag**: Glissando effect - drag to paint or erase notes
- **Shift key**: Hold to activate sustain mode temporarily

### Sustain Modes

Sustain can be activated three ways:
- Click the **S button** (sticky toggle)
- Hold the **Shift key** (momentary)
- Press **MIDI sustain pedal** (CC 64, momentary)

When sustain is active:
- Released notes stay highlighted until sustain is released
- Click/play a sustained note again to toggle it off
- S button glows with your chosen highlight color

### Mouse Interaction

**Without sustain:**
- Click to briefly highlight a note

**With sustain:**
- Click to toggle notes on/off
- Drag across keys for glissando:
  - Start on empty note → Paint mode (adds notes)
  - Start on highlighted note → Erase mode (removes notes)

## Configuration

### Keyboard Shortcuts

- **Shift**: Temporary sustain activation
- **Mouse click**: Toggle notes (with sustain) or momentary highlight (without)
- **Mouse drag**: Glissando paint/erase

## Technical Details

- **Single-file architecture**: Entire app is in `piano_viewer.py` (~2100 lines)
- **Framework**: PyQt6 for GUI, python-rtmidi for MIDI input
- **Typography**: JetBrains Mono font embedded for consistent display
- **MIDI range**: A0 to C8 (MIDI notes 21-108)
- **Default display**: C3 to B5 (3 octaves)
- **Polling interval**: 10ms (100Hz MIDI polling)

## Requirements

- PyQt6 >= 6.6.0
- python-rtmidi >= 1.5.0

## Development

See [`CLAUDE.md`](CLAUDE.md) for detailed architecture documentation, code organization, and implementation notes.

## Changelog

### 6.1.0 (2026-01-25)
- **Show names only when pressed**: New toggle to display note names only on active keys
- Educational focus: Helps students see only relevant note names without clutter
- Octave numbers always visible for navigation (unaffected by this setting)
- Checkbox auto-disables when both white and black key names are off

### 6.0.2 (2026-01-25)
- Updated screenshots and documentation

### 6.0.1 (2026-01-25)
- **Text rendering fix**: Font size now correctly calculated using proper pixel-to-point conversion
- **Text positioning fix**: Accounts for font descent for consistent gaps between key edge, note letter, and octave number
- Code cleanup and simplified text positioning logic

### 6.0.0 (2026-01-25)
- **Note names on keys**: Show C, D, E, F, G, A, B on white keys (toggleable)
- **Octave numbers**: Display octave numbers on all C keys (replaces Middle C dot)
- **Black key accidentals**: Show sharps (♯), flats (♭), or both enharmonic names
- **Smart text contrast**: Text color automatically adapts based on highlight color brightness
- **Embedded font**: JetBrains Mono for consistent, professional typography across platforms
- **Adaptive layout**: Text automatically adjusts for different window sizes

### 5.2.0 (2026-01-04)
- **Info link**: Clickable link to project repository in settings dialog

### 5.1.0 (2026-01-04)
- **Settings persistence**: All preferences now save automatically
- MIDI device selection remembered between sessions
- Highlight color preference saved
- Window size and position restored on startup
- Resize limits preference persisted

### 5.0.1 (2026-01-04)
- Gap clicks now snap to closest key for easier chord clicking
- Highlighted white keys now have visible dark borders
- Darker background grey for better white key contrast
- S button and plus button glows update when highlight color changes

### 5.0.0
- MIDI sustain pedal support (CC 64)
- Mouse click and glissando support
- Shift key sustain activation
- Sustain button with visual indicator
- Out-of-range note tracking
- Error correction (toggle sustained notes off)

## License

GPL-3.0 - See [LICENSE](LICENSE) file for details.

## Contributing

Contributions, bug reports, and feature requests are welcome! Feel free to open an issue or submit a pull request.

## Author

Built for music education and online lessons.

---

**Note**: This project is Linux-focused. Support for other platforms may be added later.
