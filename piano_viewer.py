#!/usr/bin/env python3
"""
Piano MIDI Viewer - A visual piano keyboard that displays MIDI input
Created for music education and online lessons via OBS

Version: 6.0.2
License: GPL-3.0

Changes in 6.0.1:
- Fixed text rendering: Font size now correctly calculated using proper
  pixel-to-point conversion (was treating pixels as points, causing overflow)
- Fixed text positioning: Now accounts for font descent, ensuring consistent
  gaps between key edge, note letter, and octave number
- Simplified text positioning code for all three display cases

Major Features in 6.0.0:
- Note names and octave numbers: Customizable display of musical notation
- Octave numbers on all C keys (replaces single Middle C dot)
- White key names (C, D, E, F, G, A, B) with dynamic positioning
- Black key names with flats, sharps, or both enharmonic equivalents
- Adaptive layout: Text stacks vertically on narrow keys
- Smart contrast: Text color adapts to highlight color brightness
- JetBrains Mono font embedded for consistent, readable typography

Major Features in 5.0.0:
- MIDI sustain pedal support (CC 64)
- Mouse click support with glissando (drag to paint/erase notes)
- Shift key acts as sustain pedal
- Sustain button (S) with sticky toggle and visual indicator
- Out-of-range sustained notes tracked invisibly
- Toggle sustained notes off by clicking/playing them again

Changes in 5.2.0:
- Info link: Added clickable link to project repository in settings dialog

Changes in 5.1.0:
- Settings persistence: All preferences now save automatically
- MIDI device selection remembered between sessions
- Highlight color preference saved
- Window size and position restored on startup
- Resize limits preference persisted

Changes in 5.0.1:
- Gap clicks now snap to closest key for easier chord clicking
- Highlighted white keys now have visible borders
- Darker background grey for better white key contrast
- S button and plus button glows update when highlight color changes
"""

import sys
import os
import configparser
from pathlib import Path
import rtmidi
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QComboBox, QPushButton, QLabel, QDialog,
    QColorDialog, QCheckBox
)
from PyQt6.QtCore import Qt, QRectF, QTimer, QByteArray, QUrl
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QIcon, QPixmap, QDesktopServices, QFontDatabase


# ============================================================================
# CONSTANTS - Single White Key Foundation
# ============================================================================

# DEFAULT HIGHLIGHT COLOR - Arch Blue!
DEFAULT_HIGHLIGHT_COLOR = QColor(80, 148, 212)  # #5094d4

# BACKGROUND COLOR
BACKGROUND_COLOR = QColor(150, 150, 150)

# MIDI NOTE RANGE
MIDI_NOTE_MIN = 21   # A0
MIDI_NOTE_MAX = 108  # C8

# STARTING CONFIGURATION - 3 octaves centered on Middle C
DEFAULT_START_NOTE = 48  # C3
DEFAULT_END_NOTE = 83    # B5

# SINGLE WHITE KEY - Foundation of all sizing
# Everything scales from white_key_width as the anchor
INITIAL_KEY_WIDTH = 25  # pixels (tweakable)

# HEIGHT RATIO LIMITS
# white_key_height = white_key_width × height_ratio
MIN_HEIGHT_RATIO = 3    # minimum: keys are 3× as tall as wide
MAX_HEIGHT_RATIO = 6    # maximum: keys are 6× as tall as wide

# INITIAL KEY HEIGHT - within allowed ratio range
INITIAL_KEY_HEIGHT = INITIAL_KEY_WIDTH * MAX_HEIGHT_RATIO  # = 150px

# PRACTICAL MINIMUM KEY WIDTH (for UI usability, used for min window size)
PRACTICAL_MIN_KEY_WIDTH = 15  # pixels

# VISUAL STYLING
KEY_GAP = 2
BLACK_KEY_HEIGHT_RATIO = 0.6    # black_key_height = white_key_height × 0.6
BLACK_KEY_WIDTH_RATIO = 0.8     # black_key_width = white_key_width × 0.8
KEY_CORNER_RADIUS_RATIO = 0.08
KEY_CORNER_RADIUS_MIN = 4
KEYBOARD_CANVAS_MARGIN = 4
KEYBOARD_CANVAS_RADIUS = 6

# BUTTON SIZING (hardcoded, don't scale with window)
BUTTON_SIZE = 44
ICON_SIZE_RATIO = 0.7
BUTTON_AREA_WIDTH = 50

# LAYOUT MARGINS (hardcoded)
LAYOUT_MARGIN = 5  # Main layout margins
TOTAL_HORIZONTAL_MARGIN = (LAYOUT_MARGIN * 2) + (BUTTON_AREA_WIDTH * 2)  # = 110
WINDOW_VERTICAL_MARGIN = 50  # Extra space for top/bottom window margins

# MIDI POLLING
MIDI_POLL_INTERVAL = 10

# NOTE NAMES AND TEXT RENDERING
NOTE_NAMES_WHITE = ['C', 'D', 'E', 'F', 'G', 'A', 'B']
NOTE_NAMES_BLACK_SHARPS = ['C♯', 'D♯', 'F♯', 'G♯', 'A♯']  # Using Unicode sharp symbol
NOTE_NAMES_BLACK_FLATS = ['D♭', 'E♭', 'G♭', 'A♭', 'B♭']  # Using Unicode flat symbol

# Text sizing - all derived from white_key_width
WHITE_TEXT_GAP_RATIO = 0.02         # white_text_gap = white_key_height × 0.02
BLACK_TEXT_GAP_RATIO = 0.05         # black_text_gap = white_key_height × 0.05
WHITE_KEY_TEXT_WIDTH_RATIO = 0.7    # 1 char must fit in white_key_width × 0.7
BLACK_KEY_TEXT_WIDTH_RATIO = 0.5    # 2 chars must fit in white_key_width × 0.5
WHITE_KEY_TEXT_AREA_RATIO = 0.4     # bottom 40% of white key is available for text
MIN_FONT_SIZE = 6                   # hide text if font size falls below this

# Global variable to store the loaded font family name
LOADED_FONT_FAMILY = None  # Will be set in main() after font loading


# ============================================================================
# APP ICON
# ============================================================================

def create_piano_icon():
    """Creates a simple piano icon as a QIcon."""
    svg_data = """
    <svg width="64" height="64" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
        <rect width="64" height="64" fill="#5094d4" rx="8"/>
        <rect x="8" y="16" width="48" height="36" fill="#f5f5f5" rx="2"/>
        <rect x="12" y="18" width="9" height="30" fill="#ffffff" stroke="#888" stroke-width="0.5"/>
        <rect x="22" y="18" width="9" height="30" fill="#ffffff" stroke="#888" stroke-width="0.5"/>
        <rect x="32" y="18" width="9" height="30" fill="#ffffff" stroke="#888" stroke-width="0.5"/>
        <rect x="42" y="18" width="9" height="30" fill="#ffffff" stroke="#888" stroke-width="0.5"/>
        <rect x="18" y="18" width="6" height="18" fill="#1a1a1a"/>
        <rect x="28" y="18" width="6" height="18" fill="#1a1a1a"/>
        <rect x="38" y="18" width="6" height="18" fill="#1a1a1a"/>
    </svg>
    """
    pixmap = QPixmap(64, 64)
    pixmap.loadFromData(svg_data.encode())
    return QIcon(pixmap)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_config_path():
    """
    Returns the path to the configuration file.

    On Linux: ~/.config/piano-midi-viewer/settings.ini
    On Windows: %APPDATA%/piano-midi-viewer/settings.ini
    On macOS: ~/Library/Application Support/piano-midi-viewer/settings.ini

    Creates the directory if it doesn't exist.

    Returns:
        Path: Path object pointing to the settings.ini file
    """
    if sys.platform == "win32":
        config_dir = Path(os.environ.get("APPDATA", "~")) / "piano-midi-viewer"
    elif sys.platform == "darwin":
        config_dir = Path.home() / "Library" / "Application Support" / "piano-midi-viewer"
    else:  # Linux and other Unix-like systems
        config_dir = Path.home() / ".config" / "piano-midi-viewer"

    # Create directory if it doesn't exist
    config_dir.mkdir(parents=True, exist_ok=True)

    return config_dir / "settings.ini"


def is_black_key(midi_note):
    """
    Determines if a MIDI note number corresponds to a black key.

    MIDI notes are numbered 0-127, with 60 = Middle C.
    Each octave has 12 semitones: C, C#, D, D#, E, F, F#, G, G#, A, A#, B
    Black keys are at positions: 1(C#), 3(D#), 6(F#), 8(G#), 10(A#)

    Args:
        midi_note: MIDI note number (0-127)

    Returns:
        bool: True if the note is a black key
    """
    note_in_octave = midi_note % 12
    return note_in_octave in [1, 3, 6, 8, 10]


def count_white_keys(start_note, end_note):
    """
    Counts how many white keys exist in a given MIDI note range.

    This is used to calculate window width, since the piano width
    is determined by the number of white keys (black keys overlap).

    Args:
        start_note: First MIDI note in range (inclusive)
        end_note: Last MIDI note in range (inclusive)

    Returns:
        int: Number of white keys in the range
    """
    count = 0
    for note in range(start_note, end_note + 1):
        if not is_black_key(note):
            count += 1
    return count


def get_white_key_index(midi_note, start_note):
    """
    Gets the position index of a white key (0, 1, 2, 3...).

    This is used for rendering - white keys are positioned sequentially
    left to right, ignoring the gaps where black keys are.

    Args:
        midi_note: The white key MIDI note to locate
        start_note: The leftmost note in the visible range

    Returns:
        int: Zero-based index of the white key
    """
    index = 0
    for note in range(start_note, midi_note):
        if not is_black_key(note):
            index += 1
    return index


def get_left_white_key(black_midi_note, start_note):
    """
    For a black key, finds the white key immediately to its left.

    Black keys are positioned relative to their adjacent white keys.
    This function finds the white key to use as an anchor point.

    Args:
        black_midi_note: The black key MIDI note
        start_note: The leftmost note in the visible range

    Returns:
        int: MIDI note of the white key to the left
    """
    for note in range(black_midi_note - 1, start_note - 1, -1):
        if not is_black_key(note):
            return note
    return start_note


def calculate_initial_window_size():
    """
    Calculates starting window size from initial key dimensions.

    The window size is derived from the desired key size, ensuring
    the piano keyboard starts at a comfortable viewing size.

    Returns:
        tuple: (window_width, window_height) in pixels
    """
    num_white_keys = count_white_keys(DEFAULT_START_NOTE, DEFAULT_END_NOTE)
    piano_width = INITIAL_KEY_WIDTH * num_white_keys
    window_width = int(piano_width + TOTAL_HORIZONTAL_MARGIN)
    window_height = int(INITIAL_KEY_HEIGHT + WINDOW_VERTICAL_MARGIN)
    return window_width, window_height


def get_text_color_for_highlight(highlight_color):
    """
    Calculates optimal text color (black or white) for a given background color.

    Uses relative luminance calculation to determine if the background is
    light or dark, then returns contrasting text color for readability.

    Args:
        highlight_color: QColor of the background

    Returns:
        QColor: Black for light backgrounds, white for dark backgrounds
    """
    # Get RGB components
    r = highlight_color.red()
    g = highlight_color.green()
    b = highlight_color.blue()

    # Calculate relative luminance (perceived brightness)
    # Using standard sRGB luminance formula
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0

    # Return black text for bright backgrounds, white for dark
    if luminance > 0.5:
        return QColor(0, 0, 0)  # Black
    else:
        return QColor(255, 255, 255)  # White


def calculate_font_size_for_width(target_width, num_chars, font_family):
    """
    Calculates font size to fit a given number of characters in a target width.

    Uses font metrics to accurately measure character width at a reference size,
    then scales to fit the target width.

    Args:
        target_width: Available width in pixels to fit the text
        num_chars: Number of characters that must fit in the width
        font_family: Font family name to use for measurement

    Returns:
        int: Font size in points, or 0 if below MIN_FONT_SIZE
    """
    from PyQt6.QtGui import QFont, QFontMetrics

    # Measure character width at a reference size
    reference_size = 20  # Use 20pt as reference for better precision
    reference_font = QFont(font_family, reference_size)
    metrics = QFontMetrics(reference_font)

    # Measure width of a sample character (use 'M' as it's typically widest)
    char_width_at_reference = metrics.horizontalAdvance('M')

    if char_width_at_reference == 0:
        return 0

    # Calculate pixels per point
    pixels_per_point = char_width_at_reference / reference_size

    # Calculate font size that fits num_chars in target_width
    font_size = int(target_width / (num_chars * pixels_per_point))

    if font_size < MIN_FONT_SIZE:
        return 0  # Too small to render

    return font_size


def calculate_font_size_for_height(target_height, font_family):
    """
    Calculates font size to fit a character in a target height.

    Uses font metrics to accurately measure character height (ascent + descent)
    at a reference size, then scales to fit the target height.

    Args:
        target_height: Available height in pixels for one character
        font_family: Font family name to use for measurement

    Returns:
        int: Font size in points, or 0 if below MIN_FONT_SIZE
    """
    from PyQt6.QtGui import QFont, QFontMetrics

    # Measure full character height at a reference size
    reference_size = 20  # Use 20pt as reference for better precision
    reference_font = QFont(font_family, reference_size)
    metrics = QFontMetrics(reference_font)

    # Use ascent + descent as the character height (excludes leading)
    char_height_at_reference = metrics.ascent() + metrics.descent()

    if char_height_at_reference == 0:
        return 0

    # Calculate height pixels per point
    height_per_point = char_height_at_reference / reference_size

    # Calculate font size that fits in target_height
    font_size = int(target_height / height_per_point)

    if font_size < MIN_FONT_SIZE:
        return 0  # Too small to render

    return font_size


def get_note_name(midi_note):
    """
    Gets the note name (C, D, E, etc.) for a MIDI note number.

    Args:
        midi_note: MIDI note number (0-127)

    Returns:
        str: Note name ('C', 'D', 'E', 'F', 'G', 'A', or 'B')
    """
    note_in_octave = midi_note % 12
    # MIDI notes: C=0, C#=1, D=2, D#=3, E=4, F=5, F#=6, G=7, G#=8, A=9, A#=10, B=11
    note_map = {0: 'C', 2: 'D', 4: 'E', 5: 'F', 7: 'G', 9: 'A', 11: 'B'}
    return note_map.get(note_in_octave, '')


def get_octave_number(midi_note):
    """
    Gets the octave number for a MIDI note.

    MIDI note 60 is Middle C (C4 in scientific pitch notation).
    Octave numbers start at -1 for MIDI notes 0-11.

    Args:
        midi_note: MIDI note number (0-127)

    Returns:
        int: Octave number
    """
    return (midi_note // 12) - 1


def get_black_key_name(midi_note, notation_type):
    """
    Gets the name(s) for a black key based on notation type.

    Args:
        midi_note: MIDI note number (must be a black key)
        notation_type: "Flats", "Sharps", or "Both"

    Returns:
        tuple: (sharp_name, flat_name) or (name, None) for single notation
               Returns (None, None) if not a black key
    """
    if not is_black_key(midi_note):
        return (None, None)

    note_in_octave = midi_note % 12
    # Map MIDI note positions to indices in the sharp/flat arrays
    # C#/Db=1, D#/Eb=3, F#/Gb=6, G#/Ab=8, A#/Bb=10
    black_key_index_map = {1: 0, 3: 1, 6: 2, 8: 3, 10: 4}

    index = black_key_index_map.get(note_in_octave)
    if index is None:
        return (None, None)

    sharp_name = NOTE_NAMES_BLACK_SHARPS[index]
    flat_name = NOTE_NAMES_BLACK_FLATS[index]

    if notation_type == "Sharps":
        return (sharp_name, None)
    elif notation_type == "Flats":
        return (flat_name, None)
    else:  # "Both"
        return (sharp_name, flat_name)


# ============================================================================
# SETTINGS DIALOG
# ============================================================================

class SettingsDialog(QDialog):
    """Dialog window for app configuration."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.setMinimumWidth(300)
        self.main_window = parent
        self.init_ui()

    def init_ui(self):
        """Creates all the controls in the settings dialog."""
        layout = QVBoxLayout()
        layout.setSpacing(15)

        # MIDI INPUT
        midi_label = QLabel("MIDI Input Device:")
        midi_layout = QHBoxLayout()

        self.midi_dropdown = QComboBox()
        self.populate_midi_devices()
        self.midi_dropdown.currentIndexChanged.connect(self.midi_device_changed)

        refresh_btn = QPushButton("🔄")
        refresh_btn.setToolTip("Refresh MIDI device list")
        refresh_btn.setFixedSize(30, 30)
        refresh_btn.clicked.connect(self.refresh_midi_devices)

        midi_layout.addWidget(self.midi_dropdown, 1)
        midi_layout.addWidget(refresh_btn)

        layout.addWidget(midi_label)
        layout.addLayout(midi_layout)

        # HIGHLIGHT COLOR
        color_layout = QHBoxLayout()
        color_label = QLabel("Highlight Color")

        self.color_preview = QPushButton()
        self.color_preview.setFixedSize(30, 30)
        self.color_preview.clicked.connect(self.choose_color)
        self.update_color_preview(self.main_window.piano.highlight_color)

        color_layout.addWidget(color_label)
        color_layout.addStretch()
        color_layout.addWidget(self.color_preview)

        layout.addLayout(color_layout)

        # SEPARATOR
        layout.addSpacing(10)

        # SHOW OCTAVE NUMBERS CHECKBOX
        self.octave_numbers_checkbox = QCheckBox("Show Octave Numbers")
        self.octave_numbers_checkbox.setChecked(self.main_window.show_octave_numbers)
        self.octave_numbers_checkbox.stateChanged.connect(self.toggle_octave_numbers)

        layout.addWidget(self.octave_numbers_checkbox)

        # WHITE KEY NAMES CHECKBOX
        self.white_key_names_checkbox = QCheckBox("White Key Names")
        self.white_key_names_checkbox.setChecked(self.main_window.show_white_key_names)
        self.white_key_names_checkbox.stateChanged.connect(self.toggle_white_key_names)

        layout.addWidget(self.white_key_names_checkbox)

        # BLACK KEY NAMES CHECKBOX
        self.black_key_names_checkbox = QCheckBox("Black Key Names")
        self.black_key_names_checkbox.setChecked(self.main_window.show_black_key_names)
        self.black_key_names_checkbox.stateChanged.connect(self.toggle_black_key_names)

        layout.addWidget(self.black_key_names_checkbox)

        # BLACK KEY NOTATION DROPDOWN
        notation_layout = QHBoxLayout()
        notation_layout.setContentsMargins(20, 0, 0, 0)  # Indent to show it's related to black keys

        self.black_key_notation_dropdown = QComboBox()
        self.black_key_notation_dropdown.addItem("♭ Flats", "Flats")
        self.black_key_notation_dropdown.addItem("♯ Sharps", "Sharps")
        self.black_key_notation_dropdown.addItem("Both", "Both")

        # Set current value
        current_notation = self.main_window.black_key_notation
        index = self.black_key_notation_dropdown.findData(current_notation)
        if index >= 0:
            self.black_key_notation_dropdown.setCurrentIndex(index)

        self.black_key_notation_dropdown.currentIndexChanged.connect(self.notation_changed)

        # Enable/disable based on black key names checkbox
        self.black_key_notation_dropdown.setEnabled(self.main_window.show_black_key_names)

        notation_layout.addWidget(self.black_key_notation_dropdown)
        layout.addLayout(notation_layout)

        # INFO LINK
        layout.addStretch()
        info_label = QLabel()
        info_label.setText('<a href="https://codeberg.org/skoomabwoy/piano-midi-viewer" style="color: #5094d4;">Project Info & Source Code</a>')
        info_label.setOpenExternalLinks(True)
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setTextFormat(Qt.TextFormat.RichText)
        info_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        layout.addWidget(info_label)

        # CLOSE BUTTON
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)

        layout.addWidget(close_button)
        self.setLayout(layout)

        # Make dialog fixed size (non-resizable) - Qt calculates optimal size
        self.adjustSize()
        self.setFixedSize(self.size())

    def populate_midi_devices(self):
        """Scans for available MIDI input devices."""
        self.midi_dropdown.clear()
        devices = self.main_window.get_midi_devices()

        if not devices:
            self.midi_dropdown.addItem("No MIDI devices found")
        else:
            for device_name in devices:
                self.midi_dropdown.addItem(device_name)

        if self.main_window.current_midi_device:
            index = self.midi_dropdown.findText(self.main_window.current_midi_device)
            if index >= 0:
                self.midi_dropdown.setCurrentIndex(index)

    def refresh_midi_devices(self):
        """Rescans for MIDI devices."""
        self.populate_midi_devices()

    def midi_device_changed(self, index):
        """Called when user selects a different MIDI device."""
        device_name = self.midi_dropdown.currentText()
        if device_name != "No MIDI devices found":
            self.main_window.connect_midi_device(device_name)

    def choose_color(self):
        """Opens color picker dialog."""
        color = QColorDialog.getColor(
            self.main_window.piano.highlight_color,
            self,
            "Choose Highlight Color"
        )

        if color.isValid():
            self.main_window.piano.highlight_color = color
            self.update_color_preview(color)
            self.main_window.piano.update()

            # Update sustain button visual if it's currently active
            self.main_window.update_sustain_button_visual()

            # Update any glowing plus buttons with new color
            if self.main_window.piano.glow_left_plus:
                self.main_window.apply_button_glow(self.main_window.left_plus_btn, True)
            if self.main_window.piano.glow_right_plus:
                self.main_window.apply_button_glow(self.main_window.right_plus_btn, True)

            # Save color preference
            self.main_window.save_settings()

    def update_color_preview(self, color):
        """Updates the color preview button."""
        self.color_preview.setStyleSheet(
            f"background-color: {color.name()}; border: 1px solid #999; border-radius: 15px;"
        )

    def toggle_octave_numbers(self, state):
        """Toggles octave number display."""
        self.main_window.show_octave_numbers = (state == Qt.CheckState.Checked.value)
        self.main_window.piano.update()
        self.main_window.save_settings()

    def toggle_white_key_names(self, state):
        """Toggles white key name display."""
        self.main_window.show_white_key_names = (state == Qt.CheckState.Checked.value)
        self.main_window.piano.update()
        self.main_window.save_settings()

    def toggle_black_key_names(self, state):
        """Toggles black key name display."""
        self.main_window.show_black_key_names = (state == Qt.CheckState.Checked.value)

        # Enable/disable the notation dropdown
        self.black_key_notation_dropdown.setEnabled(self.main_window.show_black_key_names)

        self.main_window.piano.update()
        self.main_window.save_settings()

    def notation_changed(self, index):
        """Called when black key notation type changes."""
        notation = self.black_key_notation_dropdown.currentData()
        self.main_window.black_key_notation = notation
        self.main_window.piano.update()
        self.main_window.save_settings()


# ============================================================================
# PIANO KEYBOARD WIDGET
# ============================================================================

class PianoKeyboard(QWidget):
    """
    Custom widget that draws a piano keyboard.

    This widget handles:
    - Rendering white and black keys with visual styling
    - Tracking and highlighting active notes from multiple sources
    - Mouse interaction for clicking and dragging notes
    - Displaying Middle C indicator
    """

    def __init__(self):
        super().__init__()

        # MIDI note range - which notes are currently visible
        self.start_note = DEFAULT_START_NOTE
        self.end_note = DEFAULT_END_NOTE

        # Note tracking sets - which notes are currently highlighted
        self.active_notes = set()           # MIDI notes currently being pressed (visible range)
        self.active_notes_left = set()      # MIDI notes being pressed below visible range
        self.active_notes_right = set()     # MIDI notes being pressed above visible range
        self.sustained_notes = set()        # Notes held by sustain (visible range)
        self.sustained_notes_left = set()   # Notes sustained below visible range
        self.sustained_notes_right = set()  # Notes sustained above visible range

        # Mouse interaction state
        self.mouse_held_note = None   # Which note the mouse cursor is currently over (or None)
        self.glissando_mode = None    # 'on' or 'off' - determined at initial mouse press

        # Visual appearance
        self.highlight_color = DEFAULT_HIGHLIGHT_COLOR
        self.glow_left_plus = False   # Whether left + button should glow
        self.glow_right_plus = False  # Whether right + button should glow

    def paintEvent(self, event):
        """Draws the piano keyboard."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()

        # Draw grey rounded canvas
        painter.setBrush(QBrush(BACKGROUND_COLOR))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(
            QRectF(0, 0, width, height),
            KEYBOARD_CANVAS_RADIUS, KEYBOARD_CANVAS_RADIUS
        )

        # Calculate keyboard area
        keyboard_x = KEYBOARD_CANVAS_MARGIN
        keyboard_y = KEYBOARD_CANVAS_MARGIN
        keyboard_width = width - (KEYBOARD_CANVAS_MARGIN * 2)
        keyboard_height = height - (KEYBOARD_CANVAS_MARGIN * 2)

        num_white_keys = count_white_keys(self.start_note, self.end_note)

        if num_white_keys == 0:
            return

        white_key_width = keyboard_width / num_white_keys
        key_corner_radius = max(KEY_CORNER_RADIUS_MIN, white_key_width * KEY_CORNER_RADIUS_RATIO)

        # Draw white keys
        for note in range(self.start_note, self.end_note + 1):
            if not is_black_key(note):
                self._draw_white_key(
                    painter, note, white_key_width,
                    keyboard_x, keyboard_y, keyboard_height, key_corner_radius
                )

        # Draw black keys
        black_key_width = white_key_width * BLACK_KEY_WIDTH_RATIO
        black_key_height = keyboard_height * BLACK_KEY_HEIGHT_RATIO

        for note in range(self.start_note, self.end_note + 1):
            if is_black_key(note):
                self._draw_black_key(
                    painter, note, white_key_width,
                    black_key_width, keyboard_x, keyboard_y, black_key_height, key_corner_radius
                )

        # Draw note names and octave numbers (if enabled)
        main_window = self._get_main_window()
        if main_window:
            # Draw white key text (note names and/or octave numbers)
            if main_window.show_white_key_names or main_window.show_octave_numbers:
                self._draw_white_key_text(
                    painter, keyboard_x, keyboard_y, keyboard_height, white_key_width, main_window
                )

            # Draw black key text (accidental names)
            if main_window.show_black_key_names:
                self._draw_black_key_text(
                    painter, white_key_width, black_key_width, keyboard_x, keyboard_y, black_key_height, keyboard_height, main_window
                )

    def _draw_white_key(self, painter, midi_note, key_width, x_offset, y_offset, height, corner_radius):
        """Draws a single white key."""
        white_index = get_white_key_index(midi_note, self.start_note)
        x = x_offset + (white_index * key_width)

        rect_x = x + KEY_GAP
        rect_y = y_offset
        rect_width = key_width - KEY_GAP * 2
        rect_height = height

        # Highlight if note is active from any source
        is_highlighted = (midi_note in self.active_notes or
                         midi_note in self.sustained_notes or
                         midi_note == self.mouse_held_note)
        fill_color = self.highlight_color if is_highlighted else QColor(245, 245, 245)

        painter.setBrush(QBrush(fill_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(
            QRectF(rect_x, rect_y, rect_width, rect_height),
            corner_radius, corner_radius
        )

        # Draw shadow lines on non-highlighted keys
        if not is_highlighted:
            shadow_color = QColor(200, 200, 200)
            painter.setPen(QPen(shadow_color, 1))

            painter.drawLine(
                int(rect_x + corner_radius), int(rect_y + rect_height - 1),
                int(rect_x + rect_width - corner_radius), int(rect_y + rect_height - 1)
            )

            painter.drawLine(
                int(rect_x + rect_width - 1), int(rect_y + corner_radius),
                int(rect_x + rect_width - 1), int(rect_y + rect_height - corner_radius)
            )

        # Draw border - darker when highlighted for better visibility
        border_color = QColor(60, 60, 60) if is_highlighted else QColor(120, 120, 120)
        painter.setPen(QPen(border_color, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(
            QRectF(rect_x, rect_y, rect_width, rect_height),
            corner_radius, corner_radius
        )

    def _draw_black_key(self, painter, midi_note, white_key_width,
                        black_key_width, x_offset, y_offset, black_key_height, corner_radius):
        """Draws a single black key."""
        left_white_note = get_left_white_key(midi_note, self.start_note)
        white_index = get_white_key_index(left_white_note, self.start_note)

        x = x_offset + ((white_index + 1) * white_key_width - black_key_width / 2)

        rect_x = x
        rect_y = y_offset
        rect_width = black_key_width
        rect_height = black_key_height

        # Highlight if note is active from any source
        is_highlighted = (midi_note in self.active_notes or
                         midi_note in self.sustained_notes or
                         midi_note == self.mouse_held_note)
        fill_color = self.highlight_color if is_highlighted else QColor(26, 26, 26)

        painter.setBrush(QBrush(fill_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(
            QRectF(rect_x, rect_y, rect_width, rect_height),
            corner_radius, corner_radius
        )

        painter.setPen(QPen(QColor(0, 0, 0), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(
            QRectF(rect_x, rect_y, rect_width, rect_height),
            corner_radius, corner_radius
        )

    def _draw_white_key_text(self, painter, x_offset, y_offset, white_key_height, white_key_width, main_window):
        """
        Draws note names and octave numbers on white keys.

        All text is centered horizontally. Note letters at bottom of all white keys,
        octave numbers above the letter on C keys only.

        Font size is determined by:
        1. Width constraint: 1 char must fit in white_key_width × 0.7
        2. Height constraint: text must fit in bottom 40% of key with gaps
        Final size = min(width_based, height_based)
        """
        font_family = LOADED_FONT_FAMILY if LOADED_FONT_FAMILY else "monospace"

        # Calculate text_gap = white_key_height × 0.02
        text_gap = white_key_height * WHITE_TEXT_GAP_RATIO

        # Calculate width-based font size: 1 char in white_key_width × 0.7
        target_width = white_key_width * WHITE_KEY_TEXT_WIDTH_RATIO
        width_based_size = calculate_font_size_for_width(target_width, 1, font_family)

        # Calculate height-based font size (safety cap)
        available_height = white_key_height * WHITE_KEY_TEXT_AREA_RATIO
        both_enabled = main_window.show_white_key_names and main_window.show_octave_numbers

        if both_enabled:
            # Need: 3 gaps + 2 symbols
            # Calculate pixel height available per symbol, then convert to font size
            symbol_height = (available_height - (text_gap * 3)) / 2
            height_based_size = calculate_font_size_for_height(symbol_height, font_family)
        else:
            # Need: 2 gaps + 1 symbol
            symbol_height = available_height - (text_gap * 2)
            height_based_size = calculate_font_size_for_height(symbol_height, font_family)

        # Width constraint is primary - if text won't fit horizontally, don't render
        if width_based_size == 0:
            return

        # Final font size = min of both constraints
        font_size = min(width_based_size, height_based_size)

        if font_size < MIN_FONT_SIZE:
            return  # Too small to render

        # Set up font
        font = QFont(font_family, font_size)
        painter.setFont(font)
        font_metrics = painter.fontMetrics()

        # Iterate through white keys
        for note in range(self.start_note, self.end_note + 1):
            if is_black_key(note):
                continue

            white_index = get_white_key_index(note, self.start_note)
            key_x = x_offset + (white_index * white_key_width)
            key_center_x = key_x + white_key_width / 2

            # Check if key is highlighted
            is_highlighted = (note in self.active_notes or
                             note in self.sustained_notes or
                             note == self.mouse_held_note)

            # Determine text color based on highlight state
            if is_highlighted:
                text_color = get_text_color_for_highlight(self.highlight_color)
            else:
                text_color = QColor(0, 0, 0)  # Black for normal white keys

            painter.setPen(text_color)

            # Get note information
            note_name = get_note_name(note)
            octave_num = get_octave_number(note)
            is_c_note = (note % 12 == 0)

            # Font metrics for positioning
            # Note: descent is the space below baseline (even caps reserve this space)
            ascent = font_metrics.ascent()
            descent = font_metrics.descent()

            # Key positions
            key_bottom = y_offset + white_key_height

            # CASE 1: Both note names and octave numbers enabled
            if main_window.show_white_key_names and main_window.show_octave_numbers:
                # Layout from bottom: key_bottom -> gap -> letter -> gap -> number
                # Text bottom = baseline + descent, so baseline = bottom - descent
                letter_baseline_y = key_bottom - text_gap - descent
                # Number bottom should be at letter_top - gap
                # letter_top = letter_baseline - ascent
                # number_bottom = letter_top - gap = letter_baseline - ascent - gap
                # number_baseline = number_bottom - descent
                octave_baseline_y = key_bottom - (2 * text_gap) - (2 * descent) - ascent

                # Draw note name (all white keys)
                if note_name:
                    text_width = font_metrics.horizontalAdvance(note_name)
                    text_x = key_center_x - text_width / 2
                    painter.drawText(int(text_x), int(letter_baseline_y), note_name)

                # Draw octave number (C keys only)
                if is_c_note:
                    octave_text = str(octave_num)
                    text_width = font_metrics.horizontalAdvance(octave_text)
                    text_x = key_center_x - text_width / 2
                    painter.drawText(int(text_x), int(octave_baseline_y), octave_text)

            # CASE 2: Only note names enabled
            elif main_window.show_white_key_names:
                # Note letter at bottom with gap from edge
                letter_baseline_y = key_bottom - text_gap - descent

                if note_name:
                    text_width = font_metrics.horizontalAdvance(note_name)
                    text_x = key_center_x - text_width / 2
                    painter.drawText(int(text_x), int(letter_baseline_y), note_name)

            # CASE 3: Only octave numbers enabled
            elif main_window.show_octave_numbers:
                # Octave number at bottom with gap from edge (C keys only)
                octave_baseline_y = key_bottom - text_gap - descent

                if is_c_note:
                    octave_text = str(octave_num)
                    text_width = font_metrics.horizontalAdvance(octave_text)
                    text_x = key_center_x - text_width / 2
                    painter.drawText(int(text_x), int(octave_baseline_y), octave_text)

    def _draw_black_key_text(self, painter, white_key_width, black_key_width, x_offset, y_offset, black_key_height, white_key_height, main_window):
        """
        Draws accidental names on black keys.

        All text is centered horizontally. Sharps at top with gap from edge,
        flats below sharps with gap between (when Both mode enabled).

        Font size is determined by:
        1. Width constraint: 2 chars must fit in white_key_width × 0.5
        2. Height constraint: text must fit in black key height with gaps
        Final size = min(width_based, height_based)
        """
        font_family = LOADED_FONT_FAMILY if LOADED_FONT_FAMILY else "monospace"

        # Calculate text_gap = white_key_height × 0.05
        text_gap = white_key_height * BLACK_TEXT_GAP_RATIO

        # Calculate width-based font size: 2 chars in white_key_width × 0.5
        target_width = white_key_width * BLACK_KEY_TEXT_WIDTH_RATIO
        width_based_size = calculate_font_size_for_width(target_width, 2, font_family)

        # Calculate height-based font size (safety cap)
        both_enabled = (main_window.black_key_notation == "Both")

        if both_enabled:
            # Need: 3 gaps + 2 symbols
            # Calculate pixel height available per symbol, then convert to font size
            symbol_height = (black_key_height - (text_gap * 3)) / 2
            height_based_size = calculate_font_size_for_height(symbol_height, font_family)
        else:
            # Need: 2 gaps + 1 symbol
            symbol_height = black_key_height - (text_gap * 2)
            height_based_size = calculate_font_size_for_height(symbol_height, font_family)

        # Width constraint is primary - if text won't fit horizontally, don't render
        if width_based_size == 0:
            return

        # Final font size = min of both constraints
        font_size = min(width_based_size, height_based_size)

        if font_size < MIN_FONT_SIZE:
            return  # Too small to render

        # Set up font
        font = QFont(font_family, font_size)
        painter.setFont(font)
        font_metrics = painter.fontMetrics()

        # Iterate through black keys
        for note in range(self.start_note, self.end_note + 1):
            if not is_black_key(note):
                continue

            # Calculate black key position
            left_white_note = get_left_white_key(note, self.start_note)
            white_index = get_white_key_index(left_white_note, self.start_note)
            key_x = x_offset + ((white_index + 1) * white_key_width - black_key_width / 2)
            key_center_x = key_x + black_key_width / 2

            # Check if key is highlighted
            is_highlighted = (note in self.active_notes or
                             note in self.sustained_notes or
                             note == self.mouse_held_note)

            # Determine text color based on highlight state
            if is_highlighted:
                text_color = get_text_color_for_highlight(self.highlight_color)
            else:
                text_color = QColor(255, 255, 255)  # White for normal black keys

            painter.setPen(text_color)

            # Get black key name(s)
            sharp_name, flat_name = get_black_key_name(note, main_window.black_key_notation)

            if not sharp_name and not flat_name:
                continue

            # Text positioning uses font height and ascent
            # drawText(x, y) places BASELINE at y
            # baseline = top_of_text + ascent
            text_height = font_metrics.height()
            ascent = font_metrics.ascent()

            # Layout (top to bottom):
            # key_top -> gap -> sharp -> gap -> flat -> gap -> key_bottom
            key_top = y_offset

            # Sharp: top is at key_top + gap
            sharp_top = key_top + text_gap
            sharp_baseline_y = sharp_top + ascent

            if both_enabled:
                # Both sharp and flat - always vertical stack (2 lines)

                # Draw sharp name at top
                sharp_width = font_metrics.horizontalAdvance(sharp_name)
                sharp_x = key_center_x - sharp_width / 2
                painter.drawText(int(sharp_x), int(sharp_baseline_y), sharp_name)

                # Flat: top is at sharp_top + text_height + gap
                flat_top = sharp_top + text_height + text_gap
                flat_baseline_y = flat_top + ascent

                flat_width = font_metrics.horizontalAdvance(flat_name)
                flat_x = key_center_x - flat_width / 2
                painter.drawText(int(flat_x), int(flat_baseline_y), flat_name)

            else:
                # Single notation (Sharps or Flats) - just one line
                name = sharp_name if sharp_name else flat_name
                text_width = font_metrics.horizontalAdvance(name)
                text_x = key_center_x - text_width / 2
                painter.drawText(int(text_x), int(sharp_baseline_y), name)

    def _get_main_window(self):
        """
        Gets the parent PianoMIDIViewer instance.

        This helper method walks up the widget hierarchy to find the main window.
        Used by mouse event handlers to check sustain state.

        Returns:
            PianoMIDIViewer instance, or None if not found
        """
        parent = self.parent()
        while parent and not isinstance(parent, PianoMIDIViewer):
            parent = parent.parent()
        return parent

    def _find_closest_note_to_position(self, x, y):
        """
        Finds the closest MIDI note to the given position.

        This is used when the user clicks on a gap between keys - we snap
        to the nearest key instead of ignoring the click.

        Args:
            x: Mouse x coordinate in widget space
            y: Mouse y coordinate in widget space

        Returns:
            MIDI note number (21-108) of the closest key, or None if outside keyboard area
        """
        width = self.width()
        height = self.height()

        keyboard_x = KEYBOARD_CANVAS_MARGIN
        keyboard_y = KEYBOARD_CANVAS_MARGIN
        keyboard_width = width - (KEYBOARD_CANVAS_MARGIN * 2)
        keyboard_height = height - (KEYBOARD_CANVAS_MARGIN * 2)

        # Check if outside keyboard area
        if x < keyboard_x or x > keyboard_x + keyboard_width:
            return None
        if y < keyboard_y or y > keyboard_y + keyboard_height:
            return None

        num_white_keys = count_white_keys(self.start_note, self.end_note)
        if num_white_keys == 0:
            return None

        white_key_width = keyboard_width / num_white_keys
        black_key_width = white_key_width * BLACK_KEY_WIDTH_RATIO
        black_key_height = keyboard_height * BLACK_KEY_HEIGHT_RATIO

        closest_note = None
        min_distance = float('inf')

        # Check all keys and find the one with the closest center
        for note in range(self.start_note, self.end_note + 1):
            if is_black_key(note):
                # Black key center
                left_white_note = get_left_white_key(note, self.start_note)
                white_index = get_white_key_index(left_white_note, self.start_note)
                key_x = keyboard_x + ((white_index + 1) * white_key_width - black_key_width / 2)
                center_x = key_x + black_key_width / 2
                center_y = keyboard_y + black_key_height / 2
            else:
                # White key center
                white_index = get_white_key_index(note, self.start_note)
                key_x = keyboard_x + (white_index * white_key_width)
                center_x = key_x + white_key_width / 2
                center_y = keyboard_y + keyboard_height / 2

            # Calculate distance to this key's center
            distance = ((x - center_x) ** 2 + (y - center_y) ** 2) ** 0.5

            if distance < min_distance:
                min_distance = distance
                closest_note = note

        return closest_note

    def _get_note_at_position(self, x, y):
        """
        Returns the MIDI note number at the given mouse position, or None.

        This method performs hit detection for mouse clicks on piano keys.
        Black keys are checked first since they're rendered on top of white keys.

        Args:
            x: Mouse x coordinate in widget space
            y: Mouse y coordinate in widget space

        Returns:
            MIDI note number (21-108), or None if outside any key
        """
        width = self.width()
        height = self.height()

        keyboard_x = KEYBOARD_CANVAS_MARGIN
        keyboard_y = KEYBOARD_CANVAS_MARGIN
        keyboard_width = width - (KEYBOARD_CANVAS_MARGIN * 2)
        keyboard_height = height - (KEYBOARD_CANVAS_MARGIN * 2)

        # Check if outside keyboard area
        if x < keyboard_x or x > keyboard_x + keyboard_width:
            return None
        if y < keyboard_y or y > keyboard_y + keyboard_height:
            return None

        num_white_keys = count_white_keys(self.start_note, self.end_note)
        if num_white_keys == 0:
            return None

        white_key_width = keyboard_width / num_white_keys
        black_key_width = white_key_width * BLACK_KEY_WIDTH_RATIO
        black_key_height = keyboard_height * BLACK_KEY_HEIGHT_RATIO

        # Check black keys first (they're on top)
        for note in range(self.start_note, self.end_note + 1):
            if is_black_key(note):
                left_white_note = get_left_white_key(note, self.start_note)
                white_index = get_white_key_index(left_white_note, self.start_note)
                key_x = keyboard_x + ((white_index + 1) * white_key_width - black_key_width / 2)

                if (key_x <= x <= key_x + black_key_width and
                    keyboard_y <= y <= keyboard_y + black_key_height):
                    return note

        # Check white keys
        for note in range(self.start_note, self.end_note + 1):
            if not is_black_key(note):
                white_index = get_white_key_index(note, self.start_note)
                key_x = keyboard_x + (white_index * white_key_width)

                if key_x + KEY_GAP <= x <= key_x + white_key_width - KEY_GAP:
                    return note

        return None

    def mousePressEvent(self, event):
        """
        Handle mouse press on piano keys.

        Determines glissando mode based on whether the initial note
        is already highlighted (OFF mode) or empty (ON mode).

        If the user clicks on a gap between keys, we snap to the closest key.
        """
        note = self._get_note_at_position(event.position().x(), event.position().y())

        # If clicked on a gap, snap to the closest key
        if note is None:
            note = self._find_closest_note_to_position(event.position().x(), event.position().y())

        if note is not None:
            # Check if sustain is active
            main_window = self._get_main_window()
            sustain_active = main_window.is_sustain_active if main_window else False

            if sustain_active:
                # Determine glissando mode based on initial note state
                if note in self.sustained_notes:
                    # Starting on highlighted note -> OFF glissando
                    self.glissando_mode = 'off'
                    self.sustained_notes.discard(note)
                else:
                    # Starting on empty note -> ON glissando
                    self.glissando_mode = 'on'
                    self.sustained_notes.add(note)
                self.mouse_held_note = note
                self.update()
            else:
                # No sustain: normal single-note behavior
                self.glissando_mode = None
                self.mouse_held_note = note
                self.update()

    def mouseMoveEvent(self, event):
        """
        Handle mouse drag across piano keys (glissando).

        Glissando behavior depends on the mode set at initial mouse press:
        - ON mode: Dragging adds notes to sustained_notes (painting notes)
        - OFF mode: Dragging removes notes from sustained_notes (erasing notes)
        - No sustain: Just tracks the current note under cursor

        The mode doesn't change during a drag - if you start on an empty note,
        you can only add notes during that drag. Similarly, starting on a highlighted
        note means you can only remove notes.
        """
        if self.mouse_held_note is not None:
            note = self._get_note_at_position(event.position().x(), event.position().y())

            # Ignore None (grey background) to allow glissando across gaps between keys
            if note is None:
                return

            if note != self.mouse_held_note:
                # Mouse moved to a different key
                if self.glissando_mode == 'on':
                    # ON glissando: only turn notes ON (add to sustained if not already there)
                    if note not in self.sustained_notes:
                        self.sustained_notes.add(note)
                elif self.glissando_mode == 'off':
                    # OFF glissando: only turn notes OFF (remove from sustained if present)
                    if note in self.sustained_notes:
                        self.sustained_notes.discard(note)
                # else: no sustain active, just track current note (no accumulation)

                self.mouse_held_note = note
                self.update()

    def mouseReleaseEvent(self, event):
        """Handle mouse release."""
        if self.mouse_held_note is not None:
            # Note: with glissando mode, note is already in sustained_notes (or removed from it)
            # No need to do anything special here

            self.mouse_held_note = None
            self.glissando_mode = None
            self.update()


# ============================================================================
# MAIN WINDOW
# ============================================================================

class PianoMIDIViewer(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()

        self._in_resize_event = False  # Guard against recursion
        self.midi_in = None
        self.current_midi_device = None
        self.midi_timer = None

        # Sustain state
        self.sustain_button_toggled = False  # Sticky toggle via S button
        self.sustain_pedal_active = False    # MIDI pedal held
        self.shift_key_active = False        # Shift key held

        # Note name and octave number display settings
        self.show_octave_numbers = True   # Default: ON
        self.show_white_key_names = True  # Default: ON
        self.show_black_key_names = False # Default: OFF
        self.black_key_notation = "Flats"  # Default: Flats

        self.init_ui()
        self.setup_midi_polling()
        self.load_settings()  # Load saved settings after UI is initialized

    @property
    def is_sustain_active(self):
        """
        Returns True if sustain is currently active from any source.

        Sustain can be activated by:
        - Clicking the S button (sticky toggle)
        - Holding the MIDI sustain pedal (CC 64)
        - Holding the Shift key

        Returns:
            bool: True if any sustain mode is active
        """
        return (self.sustain_button_toggled or
                self.sustain_pedal_active or
                self.shift_key_active)

    def init_ui(self):
        """Sets up the user interface."""
        self.setWindowTitle("Piano MIDI Viewer")
        self.setWindowIcon(create_piano_icon())

        # Calculate initial window size from key dimensions
        initial_width, initial_height = calculate_initial_window_size()
        self.resize(initial_width, initial_height)

        # Set minimum size (for UI usability)
        num_white_keys = count_white_keys(DEFAULT_START_NOTE, DEFAULT_END_NOTE)
        min_key_width = PRACTICAL_MIN_KEY_WIDTH
        min_key_height = min_key_width * MIN_HEIGHT_RATIO  # Minimum height at ratio 3
        min_width = (min_key_width * num_white_keys) + TOTAL_HORIZONTAL_MARGIN
        min_height = min_key_height + (KEYBOARD_CANVAS_MARGIN * 2) + WINDOW_VERTICAL_MARGIN
        self.setMinimumSize(int(min_width), int(min_height))

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(LAYOUT_MARGIN, LAYOUT_MARGIN, LAYOUT_MARGIN, LAYOUT_MARGIN)

        # Button styling
        button_style = """
            QPushButton {
                background-color: #f5f5f5;
                border: 1px solid #b4b4b4;
                border-radius: 6px;
                padding: 0px;
                color: #2a2a2a;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
            QPushButton:disabled {
                background-color: #e0e0e0;
                color: #a0a0a0;
            }
        """

        icon_font = QFont()
        icon_font.setPixelSize(int(BUTTON_SIZE * ICON_SIZE_RATIO))

        # LEFT SIDE
        left_container = QWidget()
        left_container.setFixedWidth(BUTTON_AREA_WIDTH)
        left_layout = QVBoxLayout(left_container)
        left_layout.setSpacing(5)
        left_layout.setContentsMargins(0, 0, 3, 0)
        left_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.sustain_button = QPushButton("S")
        self.sustain_button.setToolTip("Sustain - Click to toggle, or hold Shift/Pedal")
        self.sustain_button.setFixedSize(BUTTON_SIZE, BUTTON_SIZE)
        self.sustain_button.setFont(icon_font)
        self.sustain_button.setStyleSheet(button_style)
        self.sustain_button.clicked.connect(self.toggle_sustain_button)

        left_layout.addWidget(self.sustain_button, alignment=Qt.AlignmentFlag.AlignCenter)
        left_layout.addStretch()

        self.left_plus_btn = QPushButton("+")
        self.left_plus_btn.setToolTip("Add octave on the left (lower notes)")
        self.left_plus_btn.setFixedSize(BUTTON_SIZE, BUTTON_SIZE)
        self.left_plus_btn.setFont(icon_font)
        self.left_plus_btn.setStyleSheet(button_style)
        self.left_plus_btn.clicked.connect(self.add_octave_left)

        self.left_minus_btn = QPushButton("-")
        self.left_minus_btn.setToolTip("Remove octave on the left")
        self.left_minus_btn.setFixedSize(BUTTON_SIZE, BUTTON_SIZE)
        self.left_minus_btn.setFont(icon_font)
        self.left_minus_btn.setStyleSheet(button_style)
        self.left_minus_btn.clicked.connect(self.remove_octave_left)

        left_layout.addWidget(self.left_plus_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(self.left_minus_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # CENTER
        self.piano = PianoKeyboard()

        # RIGHT SIDE
        right_container = QWidget()
        right_container.setFixedWidth(BUTTON_AREA_WIDTH)
        right_layout = QVBoxLayout(right_container)
        right_layout.setSpacing(5)
        right_layout.setContentsMargins(3, 0, 0, 0)
        right_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.settings_button = QPushButton("⚙️")
        self.settings_button.setToolTip("Open Settings")
        self.settings_button.setFixedSize(BUTTON_SIZE, BUTTON_SIZE)
        self.settings_button.setFont(icon_font)
        self.settings_button.setStyleSheet(button_style)
        self.settings_button.clicked.connect(self.open_settings)

        right_layout.addWidget(self.settings_button, alignment=Qt.AlignmentFlag.AlignCenter)
        right_layout.addStretch()

        self.right_plus_btn = QPushButton("+")
        self.right_plus_btn.setToolTip("Add octave on the right (higher notes)")
        self.right_plus_btn.setFixedSize(BUTTON_SIZE, BUTTON_SIZE)
        self.right_plus_btn.setFont(icon_font)
        self.right_plus_btn.setStyleSheet(button_style)
        self.right_plus_btn.clicked.connect(self.add_octave_right)

        self.right_minus_btn = QPushButton("-")
        self.right_minus_btn.setToolTip("Remove octave on the right")
        self.right_minus_btn.setFixedSize(BUTTON_SIZE, BUTTON_SIZE)
        self.right_minus_btn.setFont(icon_font)
        self.right_minus_btn.setStyleSheet(button_style)
        self.right_minus_btn.clicked.connect(self.remove_octave_right)

        right_layout.addWidget(self.right_plus_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(self.right_minus_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # ASSEMBLE
        main_layout.addWidget(left_container)
        main_layout.addWidget(self.piano, 1)
        main_layout.addWidget(right_container)

        self.update_button_states()

    def open_settings(self):
        """Opens the settings dialog."""
        dialog = SettingsDialog(self)
        dialog.exec()

    def load_settings(self):
        """
        Loads settings from the configuration file.

        Reads saved settings for:
        - MIDI device selection
        - Highlight color
        - Note name and octave number display options
        - Window size and position

        If the config file doesn't exist, default values are used.
        """
        config_path = get_config_path()
        config = configparser.ConfigParser()

        if not config_path.exists():
            return  # No saved settings yet, use defaults

        try:
            config.read(config_path)

            # Load MIDI device
            if config.has_option('midi', 'device'):
                device_name = config.get('midi', 'device')
                if device_name:  # Only connect if not empty
                    self.connect_midi_device(device_name)

            # Load highlight color
            if config.has_option('appearance', 'highlight_color'):
                color_hex = config.get('appearance', 'highlight_color')
                self.piano.highlight_color = QColor(color_hex)
                self.piano.update()

            # Load note name and octave number settings
            if config.has_option('appearance', 'show_octave_numbers'):
                self.show_octave_numbers = config.getboolean('appearance', 'show_octave_numbers')

            if config.has_option('appearance', 'show_white_key_names'):
                self.show_white_key_names = config.getboolean('appearance', 'show_white_key_names')

            if config.has_option('appearance', 'show_black_key_names'):
                self.show_black_key_names = config.getboolean('appearance', 'show_black_key_names')

            if config.has_option('appearance', 'black_key_notation'):
                notation = config.get('appearance', 'black_key_notation')
                # Validate the notation value
                if notation in ['Flats', 'Sharps', 'Both']:
                    self.black_key_notation = notation

            # Load window geometry (size and position)
            # Using Qt's saveGeometry/restoreGeometry handles window manager issues better
            if config.has_option('window', 'geometry'):
                geometry_string = config.get('window', 'geometry')
                geometry_bytes = QByteArray.fromBase64(geometry_string.encode())
                self.restoreGeometry(geometry_bytes)

        except Exception as e:
            print(f"Error loading settings: {e}")
            # Continue with defaults if loading fails

    def save_settings(self):
        """
        Saves current settings to the configuration file.

        Saves:
        - Current MIDI device
        - Highlight color
        - Note name and octave number display options
        - Window size and position
        """
        config_path = get_config_path()
        config = configparser.ConfigParser()

        # MIDI settings
        config['midi'] = {
            'device': self.current_midi_device or ''
        }

        # Appearance settings
        config['appearance'] = {
            'highlight_color': self.piano.highlight_color.name(),
            'show_octave_numbers': str(self.show_octave_numbers),
            'show_white_key_names': str(self.show_white_key_names),
            'show_black_key_names': str(self.show_black_key_names),
            'black_key_notation': self.black_key_notation
        }

        # Window settings
        # Use Qt's saveGeometry for better window manager compatibility
        geometry_bytes = self.saveGeometry()
        geometry_string = geometry_bytes.toBase64().data().decode()

        config['window'] = {
            'geometry': geometry_string
        }

        try:
            with open(config_path, 'w') as f:
                config.write(f)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def toggle_sustain_button(self):
        """Toggles the sustain button sticky state."""
        self.sustain_button_toggled = not self.sustain_button_toggled

        if not self.sustain_button_toggled:
            # Turning off - clear all sustained notes
            self.clear_all_sustained_notes()

        self.update_sustain_button_visual()

    def clear_all_sustained_notes(self):
        """
        Clears all sustained notes (visible and out-of-range) and updates glows.

        This is called when:
        - Sustain button is toggled off
        - MIDI sustain pedal is released
        - Shift key is released

        It clears all three sustained note sets and updates the plus button
        glows if there are no actively pressed notes remaining.
        """
        self.piano.sustained_notes.clear()
        self.piano.sustained_notes_left.clear()
        self.piano.sustained_notes_right.clear()

        # Update plus button glows (only clear if no active notes remain)
        if not self.piano.active_notes_left and self.piano.glow_left_plus:
            self.piano.glow_left_plus = False
            self.apply_button_glow(self.left_plus_btn, False)

        if not self.piano.active_notes_right and self.piano.glow_right_plus:
            self.piano.glow_right_plus = False
            self.apply_button_glow(self.right_plus_btn, False)

        self.piano.update()

    def update_sustain_button_visual(self):
        """
        Updates the sustain button appearance based on state.

        The S button lights up in the highlight color whenever sustain
        is active from any source (button click, MIDI pedal, or Shift key).
        """
        if self.is_sustain_active:
            color = self.piano.highlight_color.name()
            self.sustain_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    color: white;
                    font-weight: bold;
                    border: 1px solid #b4b4b4;
                    border-radius: 6px;
                }}
            """)
        else:
            self.sustain_button.setStyleSheet("""
                QPushButton {
                    background-color: #f5f5f5;
                    border: 1px solid #b4b4b4;
                    border-radius: 6px;
                    color: #2a2a2a;
                    font-weight: bold;
                }
            """)

    def get_current_key_dimensions(self):
        """Calculates current white key width and height."""
        num_white_keys = count_white_keys(self.piano.start_note, self.piano.end_note)
        if num_white_keys == 0:
            return None, None

        piano_width = self.piano.width()
        piano_height = self.piano.height()

        key_width = piano_width / num_white_keys
        key_height = piano_height - (KEYBOARD_CANVAS_MARGIN * 2)

        return key_width, key_height

    # MIDI FUNCTIONALITY

    def get_midi_devices(self):
        """Scans for available MIDI input devices."""
        try:
            midi_in = rtmidi.MidiIn()
            ports = midi_in.get_ports()
            del midi_in
            return ports
        except Exception as e:
            print(f"Error scanning MIDI devices: {e}")
            return []

    def connect_midi_device(self, device_name):
        """Connects to the specified MIDI input device."""
        if self.midi_in:
            try:
                self.midi_in.close_port()
            except Exception:
                # Ignore errors when closing old port (device may already be disconnected)
                pass
            del self.midi_in
            self.midi_in = None

        try:
            self.midi_in = rtmidi.MidiIn()
            ports = self.midi_in.get_ports()

            if device_name in ports:
                port_index = ports.index(device_name)
                self.midi_in.open_port(port_index)
                self.current_midi_device = device_name
                print(f"Connected to MIDI device: {device_name}")
                self.save_settings()  # Save MIDI device preference
            else:
                print(f"Device not found: {device_name}")
                del self.midi_in
                self.midi_in = None

        except Exception as e:
            print(f"Error connecting to MIDI device: {e}")
            if self.midi_in:
                del self.midi_in
            self.midi_in = None

    def setup_midi_polling(self):
        """Sets up a timer to poll for MIDI messages."""
        self.midi_timer = QTimer()
        self.midi_timer.timeout.connect(self.poll_midi_messages)
        self.midi_timer.start(MIDI_POLL_INTERVAL)

    def poll_midi_messages(self):
        """Checks for new MIDI messages and processes them."""
        if not self.midi_in:
            return

        try:
            while True:
                message = self.midi_in.get_message()

                if message is None:
                    break

                midi_data, delta_time = message
                self.process_midi_message(midi_data)

        except Exception as e:
            print(f"Error polling MIDI: {e}")

    def process_midi_message(self, midi_data):
        """
        Processes a MIDI message and updates the keyboard display.

        Handles three types of MIDI messages:
        1. Control Change (0xB0) - for sustain pedal (CC 64)
        2. Note On (0x90 with velocity > 0) - note pressed
        3. Note Off (0x80 or 0x90 with velocity 0) - note released

        Args:
            midi_data: List of bytes from MIDI message [status, data1, data2]
        """
        if len(midi_data) < 3:
            return

        status_byte = midi_data[0]
        data1 = midi_data[1]
        data2 = midi_data[2]

        # Extract message type (upper 4 bits of status byte)
        message_type = status_byte & 0xF0

        # Control Change messages (sustain pedal detection)
        if message_type == 0xB0:
            controller_number = data1
            controller_value = data2

            if controller_number == 64:  # Sustain pedal
                was_active = self.sustain_pedal_active
                self.sustain_pedal_active = (controller_value >= 64)

                if was_active and not self.sustain_pedal_active:
                    # Pedal released - clear all sustained notes
                    self.clear_all_sustained_notes()
                elif not was_active and self.sustain_pedal_active:
                    # Pedal pressed - takeover from sticky toggle if active
                    if self.sustain_button_toggled:
                        self.sustain_button_toggled = False

                self.update_sustain_button_visual()

        # Note On/Off messages
        elif message_type == 0x90 and data2 > 0:
            self.handle_note_on(data1)
        elif message_type == 0x80 or (message_type == 0x90 and data2 == 0):
            self.handle_note_off(data1)

    def handle_note_on(self, note_number):
        """
        Handles a Note On MIDI event.

        If the note is within visible range and already sustained,
        pressing it again toggles it off (allows error correction).
        Otherwise, the note is added to active_notes.
        """
        if self.piano.start_note <= note_number <= self.piano.end_note:
            # Note within visible range
            if self.is_sustain_active and note_number in self.piano.sustained_notes:
                # Toggle off: remove from sustained notes
                self.piano.sustained_notes.discard(note_number)
            else:
                # Normal behavior: add to active notes
                self.piano.active_notes.add(note_number)

            self.piano.update()
        elif note_number < self.piano.start_note:
            # Note below visible range
            self.piano.active_notes_left.add(note_number)
            if not self.piano.glow_left_plus:
                self.piano.glow_left_plus = True
                self.apply_button_glow(self.left_plus_btn, True)
        else:  # note_number > self.piano.end_note
            # Note above visible range
            self.piano.active_notes_right.add(note_number)
            if not self.piano.glow_right_plus:
                self.piano.glow_right_plus = True
                self.apply_button_glow(self.right_plus_btn, True)

    def handle_note_off(self, note_number):
        """
        Handles a Note Off MIDI event.

        When sustain is active, notes are moved to sustained_notes instead
        of being released immediately. This applies to both visible and
        out-of-range notes.
        """
        # Handle notes within visible range
        if note_number in self.piano.active_notes:
            self.piano.active_notes.discard(note_number)

            if self.is_sustain_active:
                # Move to sustained notes instead of releasing
                self.piano.sustained_notes.add(note_number)

            self.piano.update()

        # Handle notes outside visible range (left)
        if note_number in self.piano.active_notes_left:
            self.piano.active_notes_left.discard(note_number)

            if self.is_sustain_active:
                # Move to sustained notes instead of releasing
                self.piano.sustained_notes_left.add(note_number)
            else:
                # Only clear glow if no more left notes are held (active or sustained)
                if not self.piano.active_notes_left and not self.piano.sustained_notes_left and self.piano.glow_left_plus:
                    self.piano.glow_left_plus = False
                    self.apply_button_glow(self.left_plus_btn, False)

        # Handle notes outside visible range (right)
        if note_number in self.piano.active_notes_right:
            self.piano.active_notes_right.discard(note_number)

            if self.is_sustain_active:
                # Move to sustained notes instead of releasing
                self.piano.sustained_notes_right.add(note_number)
            else:
                # Only clear glow if no more right notes are held (active or sustained)
                if not self.piano.active_notes_right and not self.piano.sustained_notes_right and self.piano.glow_right_plus:
                    self.piano.glow_right_plus = False
                    self.apply_button_glow(self.right_plus_btn, False)

    def apply_button_glow(self, button, glow):
        """Applies or removes a glow effect on a button."""
        if glow:
            color = self.piano.highlight_color.name()
            button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    color: white;
                    font-weight: bold;
                    border: 1px solid #b4b4b4;
                    border-radius: 6px;
                }}
            """)
        else:
            button.setStyleSheet("""
                QPushButton {
                    background-color: #f5f5f5;
                    border: 1px solid #b4b4b4;
                    border-radius: 6px;
                    color: #2a2a2a;
                    font-weight: bold;
                }
            """)

    # OCTAVE MANAGEMENT

    def add_octave_left(self):
        """Adds an octave to the left (lower notes)."""
        new_start = self.piano.start_note - 12

        if new_start >= MIDI_NOTE_MIN:
            # Get current key width
            key_width, _ = self.get_current_key_dimensions()
            if key_width is None:
                return

            # Update range
            self.piano.start_note = new_start

            # Move sustained notes that are now in range
            notes_to_move = [n for n in self.piano.sustained_notes_left
                           if self.piano.start_note <= n <= self.piano.end_note]
            for note in notes_to_move:
                self.piano.sustained_notes_left.discard(note)
                self.piano.sustained_notes.add(note)

            # Update left glow if no more sustained notes left
            if not self.piano.active_notes_left and not self.piano.sustained_notes_left and self.piano.glow_left_plus:
                self.piano.glow_left_plus = False
                self.apply_button_glow(self.left_plus_btn, False)

            # Calculate new window width to maintain key size
            new_num_white = count_white_keys(self.piano.start_note, self.piano.end_note)
            new_piano_width = key_width * new_num_white
            new_window_width = round(new_piano_width + TOTAL_HORIZONTAL_MARGIN)

            # Resize window
            self.resize(new_window_width, self.height())

            self.piano.update()
            self.update_button_states()

    def remove_octave_left(self):
        """Removes an octave from the left."""
        new_start = self.piano.start_note + 12

        if new_start <= self.piano.end_note - 11:
            # Get current key width
            key_width, _ = self.get_current_key_dimensions()
            if key_width is None:
                return

            # Update range
            self.piano.start_note = new_start

            # Move sustained notes that are now out of range
            notes_to_move = [n for n in self.piano.sustained_notes
                           if n < self.piano.start_note]
            for note in notes_to_move:
                self.piano.sustained_notes.discard(note)
                self.piano.sustained_notes_left.add(note)

            # Turn on glow if we have sustained notes left
            if (self.piano.sustained_notes_left or self.piano.active_notes_left) and not self.piano.glow_left_plus:
                self.piano.glow_left_plus = True
                self.apply_button_glow(self.left_plus_btn, True)

            # Calculate new window width to maintain key size
            new_num_white = count_white_keys(self.piano.start_note, self.piano.end_note)
            new_piano_width = key_width * new_num_white
            new_window_width = round(new_piano_width + TOTAL_HORIZONTAL_MARGIN)

            # Resize window
            self.resize(new_window_width, self.height())

            self.piano.update()
            self.update_button_states()

    def add_octave_right(self):
        """Adds an octave to the right (higher notes)."""
        new_end = self.piano.end_note + 12

        if new_end <= MIDI_NOTE_MAX:
            # Get current key width
            key_width, _ = self.get_current_key_dimensions()
            if key_width is None:
                return

            # Update range
            self.piano.end_note = new_end

            # Move sustained notes that are now in range
            notes_to_move = [n for n in self.piano.sustained_notes_right
                           if self.piano.start_note <= n <= self.piano.end_note]
            for note in notes_to_move:
                self.piano.sustained_notes_right.discard(note)
                self.piano.sustained_notes.add(note)

            # Update right glow if no more sustained notes right
            if not self.piano.active_notes_right and not self.piano.sustained_notes_right and self.piano.glow_right_plus:
                self.piano.glow_right_plus = False
                self.apply_button_glow(self.right_plus_btn, False)

            # Calculate new window width to maintain key size
            new_num_white = count_white_keys(self.piano.start_note, self.piano.end_note)
            new_piano_width = key_width * new_num_white
            new_window_width = round(new_piano_width + TOTAL_HORIZONTAL_MARGIN)

            # Resize window
            self.resize(new_window_width, self.height())

            self.piano.update()
            self.update_button_states()

    def remove_octave_right(self):
        """Removes an octave from the right."""
        new_end = self.piano.end_note - 12

        if new_end >= self.piano.start_note + 11:
            # Get current key width
            key_width, _ = self.get_current_key_dimensions()
            if key_width is None:
                return

            # Update range
            self.piano.end_note = new_end

            # Move sustained notes that are now out of range
            notes_to_move = [n for n in self.piano.sustained_notes
                           if n > self.piano.end_note]
            for note in notes_to_move:
                self.piano.sustained_notes.discard(note)
                self.piano.sustained_notes_right.add(note)

            # Turn on glow if we have sustained notes right
            if (self.piano.sustained_notes_right or self.piano.active_notes_right) and not self.piano.glow_right_plus:
                self.piano.glow_right_plus = True
                self.apply_button_glow(self.right_plus_btn, True)

            # Calculate new window width to maintain key size
            new_num_white = count_white_keys(self.piano.start_note, self.piano.end_note)
            new_piano_width = key_width * new_num_white
            new_window_width = round(new_piano_width + TOTAL_HORIZONTAL_MARGIN)

            # Resize window
            self.resize(new_window_width, self.height())

            self.piano.update()
            self.update_button_states()

    def update_button_states(self):
        """Updates the enabled/disabled state of octave control buttons."""
        self.left_plus_btn.setEnabled(self.piano.start_note > MIDI_NOTE_MIN + 12)
        self.left_minus_btn.setEnabled(self.piano.end_note - self.piano.start_note > 11)
        self.right_plus_btn.setEnabled(self.piano.end_note < MIDI_NOTE_MAX - 12)
        self.right_minus_btn.setEnabled(self.piano.end_note - self.piano.start_note > 11)

    # WINDOW MANAGEMENT

    def resizeEvent(self, event):
        """
        Called when window is resized. Enforces height ratio limits.

        Height ratio = white_key_height / white_key_width
        Must stay within [MIN_HEIGHT_RATIO, MAX_HEIGHT_RATIO] (3 to 6).
        """
        # Prevent recursion
        if self._in_resize_event:
            super().resizeEvent(event)
            return

        self._in_resize_event = True
        try:
            super().resizeEvent(event)

            # Get current size
            w = self.width()
            h = self.height()

            # Calculate key dimensions
            num_white_keys = count_white_keys(self.piano.start_note, self.piano.end_note)
            if num_white_keys == 0:
                return

            piano_width = w - TOTAL_HORIZONTAL_MARGIN
            piano_height = h - WINDOW_VERTICAL_MARGIN
            white_key_width = piano_width / num_white_keys
            white_key_height = piano_height - (KEYBOARD_CANVAS_MARGIN * 2)

            # Calculate current height ratio
            if white_key_width > 0:
                height_ratio = white_key_height / white_key_width

                # Too tall (ratio > 6)? Reduce height
                if height_ratio > MAX_HEIGHT_RATIO:
                    white_key_height = white_key_width * MAX_HEIGHT_RATIO
                    h = round(white_key_height + (KEYBOARD_CANVAS_MARGIN * 2) + WINDOW_VERTICAL_MARGIN)

                # Too short (ratio < 3)? Reduce width
                elif height_ratio < MIN_HEIGHT_RATIO:
                    white_key_width = white_key_height / MIN_HEIGHT_RATIO
                    w = round(white_key_width * num_white_keys + TOTAL_HORIZONTAL_MARGIN)

            # Apply constrained size
            if w != self.width() or h != self.height():
                self.resize(w, h)

        finally:
            self._in_resize_event = False

    def keyPressEvent(self, event):
        """Handle keyboard key press events."""
        if event.key() == Qt.Key.Key_Shift and not event.isAutoRepeat():
            if not self.shift_key_active:
                # Shift key pressed
                if self.sustain_button_toggled:
                    # Takeover: turn off sticky toggle
                    self.sustain_button_toggled = False

                self.shift_key_active = True
                self.update_sustain_button_visual()

    def keyReleaseEvent(self, event):
        """Handle keyboard key release events."""
        if event.key() == Qt.Key.Key_Shift and not event.isAutoRepeat():
            if self.shift_key_active:
                self.shift_key_active = False
                # Clear all sustained notes when shift released
                self.clear_all_sustained_notes()
                self.update_sustain_button_visual()

    def closeEvent(self, event):
        """Called when the window is closed. Clean up MIDI resources."""
        # Save settings before closing
        self.save_settings()

        if self.midi_timer:
            self.midi_timer.stop()

        if self.midi_in:
            try:
                self.midi_in.close_port()
            except Exception:
                # Ignore errors when closing MIDI port on shutdown
                pass
            del self.midi_in

        event.accept()


# ============================================================================
# APPLICATION ENTRY POINT
# ============================================================================

def main():
    """Creates and runs the application."""
    print("Piano MIDI Viewer - Version 6.0.2")
    print("=" * 40)
    print(f"Initial key size: {INITIAL_KEY_WIDTH}px × {INITIAL_KEY_HEIGHT}px")
    print(f"Height ratio limits: {MIN_HEIGHT_RATIO}× to {MAX_HEIGHT_RATIO}× (height/width)")
    print("=" * 40)

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setWindowIcon(create_piano_icon())

    # Load JetBrains Mono font for note names and octave numbers
    global LOADED_FONT_FAMILY
    font_path = os.path.join(os.path.dirname(__file__), "JetBrainsMono-Regular.ttf")
    if os.path.exists(font_path):
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id != -1:
            font_families = QFontDatabase.applicationFontFamilies(font_id)
            if font_families:
                LOADED_FONT_FAMILY = font_families[0]
                print(f"✓ Loaded font: {LOADED_FONT_FAMILY}")
            else:
                print("⚠ Font loaded but no families found")
                LOADED_FONT_FAMILY = "monospace"  # Fallback
        else:
            print(f"⚠ Failed to load font from {font_path}")
            LOADED_FONT_FAMILY = "monospace"  # Fallback
    else:
        print(f"⚠ Font file not found: {font_path}")
        LOADED_FONT_FAMILY = "monospace"  # Fallback

    window = PianoMIDIViewer()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
