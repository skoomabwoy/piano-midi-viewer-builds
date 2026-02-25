#!/usr/bin/env python3
"""
Piano MIDI Viewer - A visual piano keyboard that displays MIDI input
Created for music education and online lessons via OBS

Version: see VERSION constant
License: GPL-3.0
"""

import sys
import os
import json
import configparser
from pathlib import Path
import subprocess
from urllib.request import urlopen, Request
from urllib.error import URLError
import rtmidi
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QComboBox, QPushButton, QLabel, QDialog,
    QColorDialog, QCheckBox
)
from PyQt6.QtCore import Qt, QRectF, QTimer, QByteArray, QThread, pyqtSignal, QUrl
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QFontMetrics, QIcon, QPixmap, QDesktopServices, QFontDatabase, QCursor


# ============================================================================
# CONSTANTS - Single White Key Foundation
# ============================================================================

# VERSION
VERSION = "8.5.0"

# DEFAULT HIGHLIGHT COLOR - Arch Blue!
DEFAULT_HIGHLIGHT_COLOR = QColor(80, 148, 212)  # #5094d4

# BACKGROUND COLOR
BACKGROUND_COLOR = QColor(120, 120, 120)  # Darker for better contrast with white keys

# MIDI NOTE RANGE
MIDI_NOTE_MIN = 21   # A0
MIDI_NOTE_MAX = 108  # C8

# STARTING CONFIGURATION - 3 octaves centered on Middle C
DEFAULT_START_NOTE = 48  # C3
DEFAULT_END_NOTE = 83    # B5

# SINGLE WHITE KEY - Foundation of all sizing
# Everything scales from white_key_width as the anchor
INITIAL_KEY_WIDTH = 32  # pixels (tweakable)

# HEIGHT RATIO LIMITS
# white_key_height = white_key_width × height_ratio
MIN_HEIGHT_RATIO = 3    # minimum: keys are 3× as tall as wide
MAX_HEIGHT_RATIO = 6    # maximum: keys are 6× as tall as wide

# INITIAL KEY HEIGHT - within allowed ratio range
INITIAL_KEY_HEIGHT = INITIAL_KEY_WIDTH * MAX_HEIGHT_RATIO  # = 150px

# PRACTICAL MINIMUM KEY WIDTH (for UI usability, used for min window size)
PRACTICAL_MIN_KEY_WIDTH = 15  # pixels

# VISUAL STYLING
KEY_GAP_RATIO = 0.03            # key_gap = white_key_width × 0.03
KEY_GAP_MIN = 1                 # minimum 1px gap
KEY_GAP_MAX = 5                 # maximum 5px per side (10px visible gap between keys)
SHADOW_DISABLE_WIDTH = 25       # disable shadow effects below this key width
BLACK_KEY_HEIGHT_RATIO = 0.6    # black_key_height = white_key_height × 0.6
BLACK_KEY_WIDTH_RATIO = 0.8     # black_key_width = white_key_width × 0.8
KEY_CORNER_RADIUS_RATIO = 0.08
KEY_CORNER_RADIUS_MIN = 4
KEYBOARD_CANVAS_MARGIN = 4
KEYBOARD_CANVAS_RADIUS = 6

# CURSOR SIZING AND COLORS (for pencil/eraser tool cursors)
CURSOR_SIZE = 24                # pixel size of custom cursor pixmap (try 24-40)
CURSOR_OUTLINE_COLOR = '#010101'  # outline color for both cursors (try #707070, #a0a0a0, #c0c0c0)
CURSOR_FILL_COLOR = '#ffffff'     # interior fill color for both cursors

# UI SCALE (loaded from settings before window creation)
UI_SCALE_FACTOR = 1.0  # Set in main() from saved settings

def scaled(px):
    """Scale a pixel value by the current UI scale factor."""
    return round(px * UI_SCALE_FACTOR)

# BUTTON SIZING (base values, scaled at runtime via scaled())
BUTTON_SIZE = 36
ICON_SIZE_RATIO = 0.9
BUTTON_AREA_WIDTH = 50
BUTTON_SPACING = 5              # Spacing between buttons in layout

# LAYOUT MARGINS (base values, scaled at runtime via scaled())
LAYOUT_MARGIN = 5  # Main layout margins
WINDOW_VERTICAL_MARGIN = 50  # Extra space for top/bottom window margins

# Derived layout values — must be functions because they depend on scaled()
def total_horizontal_margin():
    return scaled(LAYOUT_MARGIN) * 2 + scaled(BUTTON_AREA_WIDTH) * 2

def min_button_area_height():
    return scaled(BUTTON_SIZE) * 4 + scaled(BUTTON_SPACING) * 3

def min_window_height():
    return min_button_area_height() + scaled(LAYOUT_MARGIN) * 2

# MIDI POLLING
MIDI_POLL_INTERVAL = 10
MIDI_SCAN_INTERVAL = 3000     # milliseconds between device scans (hot-plug detection)
STATUS_MESSAGE_DURATION = 3000  # milliseconds before status message auto-hides

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
    """Creates a piano icon as a QIcon from embedded SVG."""
    svg_data = """
    <svg width="64" height="64" viewBox="-31.4 -31.4 376.84 376.84" xmlns="http://www.w3.org/2000/svg">
        <rect x="-31.4" y="-31.4" width="376.84" height="376.84" fill="#1793D1"/>
        <g fill="#ffffff">
            <path d="M89.859,314.043h60.092h14.142h60.092h14.142h74.233V0h-74.233h-14.142h-60.092h-14.142H89.859H75.717H1.484v314.043 h74.233H89.859z M296.652,298.136h-56.561v-91.021h18.559V15.907h38.002V298.136z M222.418,207.115v91.021h-56.561v-91.021h18.559 V15.907h17.673v191.208H222.418z M148.185,207.115v91.021H91.625v-91.021h18.559V15.907h17.673v191.208H148.185z M73.952,298.136 H17.391V15.907h36.231v191.208h20.33V298.136z"/>
        </g>
    </svg>
    """
    pixmap = QPixmap(64, 64)
    pixmap.loadFromData(svg_data.encode())
    return QIcon(pixmap)


def create_settings_icon(size=64, color="#000000"):
    """
    Creates a cogwheel/gear settings icon as a QIcon.

    Uses SVG for consistent rendering across all platforms (Windows, Linux, macOS).
    Based on Creative Commons icon from SVG Repo.

    Args:
        size: Icon size in pixels (default 64)
        color: Hex color for the gear (default black)

    Returns:
        QIcon: The settings gear icon
    """
    # SVG cogwheel - clean design with 6 teeth and center hole
    # Source: SVG Repo (Creative Commons)
    svg_data = f"""
    <svg width="{size}" height="{size}" viewBox="0 0 8.467 8.467" xmlns="http://www.w3.org/2000/svg">
        <g transform="translate(0,-288.533)" fill="{color}">
            <path d="m 3.704,288.798 a 0.265,0.265 0 0 0 -0.251,0.181 l -0.269,0.806 c -0.108,0.038 -0.215,0.082 -0.318,0.132 l -0.76,-0.38 a 0.265,0.265 0 0 0 -0.305,0.05 l -0.748,0.748 a 0.265,0.265 0 0 0 -0.05,0.305 l 0.379,0.759 c -0.05,0.104 -0.094,0.211 -0.132,0.32 l -0.805,0.269 a 0.265,0.265 0 0 0 -0.181,0.251 v 1.058 a 0.265,0.265 0 0 0 0.181,0.251 l 0.808,0.269 c 0.038,0.108 0.082,0.213 0.131,0.316 l -0.381,0.762 a 0.265,0.265 0 0 0 0.05,0.305 l 0.748,0.749 a 0.265,0.265 0 0 0 0.305,0.05 l 0.76,-0.38 c 0.104,0.05 0.209,0.093 0.318,0.131 l 0.269,0.807 a 0.265,0.265 0 0 0 0.251,0.181 h 1.058 a 0.265,0.265 0 0 0 0.251,-0.181 l 0.269,-0.809 c 0.108,-0.038 0.213,-0.082 0.316,-0.131 l 0.762,0.381 a 0.265,0.265 0 0 0 0.305,-0.05 l 0.748,-0.749 a 0.265,0.265 0 0 0 0.05,-0.305 l -0.38,-0.76 c 0.05,-0.104 0.094,-0.21 0.132,-0.319 l 0.806,-0.269 a 0.265,0.265 0 0 0 0.181,-0.251 v -1.058 a 0.265,0.265 0 0 0 -0.181,-0.251 l -0.807,-0.269 c -0.038,-0.108 -0.082,-0.214 -0.132,-0.318 l 0.38,-0.761 a 0.265,0.265 0 0 0 -0.05,-0.305 l -0.748,-0.748 a 0.265,0.265 0 0 0 -0.305,-0.05 l -0.758,0.379 c -0.105,-0.05 -0.212,-0.094 -0.321,-0.132 l -0.268,-0.805 a 0.265,0.265 0 0 0 -0.251,-0.181 z m 0.191,0.529 h 0.677 l 0.245,0.737 a 0.265,0.265 0 0 0 0.176,0.17 c 0.172,0.051 0.339,0.12 0.497,0.205 a 0.265,0.265 0 0 0 0.243,0.004 l 0.694,-0.347 0.479,0.479 -0.348,0.697 a 0.265,0.265 0 0 0 0.003,0.244 c 0.085,0.157 0.154,0.322 0.205,0.493 a 0.265,0.265 0 0 0 0.169,0.175 l 0.739,0.246 v 0.677 l -0.738,0.246 a 0.265,0.265 0 0 0 -0.169,0.175 c -0.051,0.171 -0.12,0.337 -0.205,0.495 a 0.265,0.265 0 0 0 -0.003,0.244 l 0.347,0.695 -0.479,0.479 -0.698,-0.349 a 0.265,0.265 0 0 0 -0.244,0.004 c -0.157,0.084 -0.321,0.153 -0.491,0.204 a 0.265,0.265 0 0 0 -0.175,0.17 l -0.247,0.74 H 3.895 l -0.247,-0.739 a 0.265,0.265 0 0 0 -0.175,-0.17 c -0.171,-0.051 -0.337,-0.119 -0.494,-0.204 a 0.265,0.265 0 0 0 -0.243,-0.004 l -0.696,0.348 -0.479,-0.479 0.349,-0.698 a 0.265,0.265 0 0 0 -0.004,-0.244 c -0.084,-0.157 -0.153,-0.322 -0.205,-0.492 a 0.265,0.265 0 0 0 -0.169,-0.175 l -0.739,-0.246 v -0.677 l 0.737,-0.246 a 0.265,0.265 0 0 0 0.17,-0.175 c 0.051,-0.172 0.12,-0.338 0.205,-0.496 a 0.265,0.265 0 0 0 0.004,-0.244 l -0.347,-0.694 0.479,-0.479 0.696,0.348 a 0.265,0.265 0 0 0 0.244,-0.004 c 0.157,-0.085 0.323,-0.154 0.494,-0.205 a 0.265,0.265 0 0 0 0.175,-0.17 z"/>
            <path d="m 4.232,290.914 c -1.02,0 -1.851,0.834 -1.851,1.854 0,1.019 0.831,1.851 1.851,1.851 1.02,0 1.854,-0.832 1.854,-1.851 0,-1.02 -0.834,-1.854 -1.854,-1.854 z m 0,0.53 c 0.734,0 1.324,0.59 1.324,1.324 0,0.734 -0.59,1.322 -1.324,1.322 -0.734,0 -1.322,-0.588 -1.322,-1.322 0,-0.734 0.588,-1.324 1.322,-1.324 z"/>
        </g>
    </svg>
    """
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    pixmap.loadFromData(svg_data.encode())
    return QIcon(pixmap)


# Embedded SVG for pencil cursor/icon (source: SVG Repo, www.svgrepo.com)
# Outer contour filled white (opaque interior), detail path filled black on top
PENCIL_SVG = """<svg viewBox="0 0 512 512" xmlns="http://www.w3.org/2000/svg">
<path fill="#ffffff" d="M497.209,88.393l-73.626-73.6c-19.721-19.712-51.656-19.729-71.376-0.017L304.473,62.51L71.218,295.816
c-9.671,9.662-17.066,21.341-21.695,34.193L2.238,461.6c-4.93,13.73-1.492,29.064,8.818,39.372
c10.318,10.317,25.659,13.739,39.39,8.801l131.565-47.286c12.851-4.628,24.539-12.032,34.201-21.694l220.801-220.817l0.017,0.017
l12.481-12.498l47.699-47.725l0.026-0.018C516.861,140.039,516.939,108.14,497.209,88.393z"/>
<path fill="#000000" d="M497.209,88.393l-73.626-73.6c-19.721-19.712-51.656-19.729-71.376-0.017L304.473,62.51L71.218,295.816
c-9.671,9.662-17.066,21.341-21.695,34.193L2.238,461.6c-4.93,13.73-1.492,29.064,8.818,39.372
c10.318,10.317,25.659,13.739,39.39,8.801l131.565-47.286c12.851-4.628,24.539-12.032,34.201-21.694l220.801-220.817l0.017,0.017
l12.481-12.498l47.699-47.725l0.026-0.018C516.861,140.039,516.939,108.14,497.209,88.393z M170.064,429.26l-83.822,30.133
l-33.606-33.607l30.116-83.831c0.224-0.604,0.517-1.19,0.758-1.792l88.339,88.339C171.245,428.752,170.676,429.036,170.064,429.26z
 M191.242,415.831c-1.19,1.19-2.457,2.284-3.741,3.362l-94.674-94.674c1.069-1.276,2.163-2.552,3.352-3.741L327.685,89.22
l95.079,95.08L191.242,415.831z M472.247,134.808l-35.235,35.244l-1.767,1.767l-95.08-95.079l37.003-37.003
c5.921-5.896,15.506-5.905,21.454,0.017l73.625,73.609c5.921,5.904,5.93,15.489-0.026,21.47L472.247,134.808z"/>
</svg>"""

# Embedded SVG for eraser cursor (source: SVG Repo, www.svgrepo.com)
# Outer contour filled white (opaque interior), detail path filled black on top
ERASER_SVG = """<svg viewBox="0 0 203.464 203.464" xmlns="http://www.w3.org/2000/svg">
<path fill="#ffffff" d="M186.023,12.626C186,5.665,180.305,0,173.329,0c-2.964,0-5.755,1.022-8.07,2.956L55.597,94.522c0,0,0,0,0,0
l-30.286,25.289c-5.323,4.444-8.253,10.969-8.039,17.901l1.655,53.477c0.213,6.883,5.785,12.274,12.686,12.275c0,0,0,0,0.001,0
c2.965,0,5.756-1.021,8.071-2.954l59.856-49.979l0.001,0l78.613-65.641c5.138-4.29,8.072-10.589,8.05-17.282L186.023,12.626z"/>
<path fill="#000000" d="M186.023,12.626C186,5.665,180.305,0,173.329,0c-2.964,0-5.755,1.022-8.07,2.956L55.597,94.522c0,0,0,0,0,0
l-30.286,25.289c-5.323,4.444-8.253,10.969-8.039,17.901l1.655,53.477c0.213,6.883,5.785,12.274,12.686,12.275c0,0,0,0,0.001,0
c2.965,0,5.756-1.021,8.071-2.954l59.856-49.979l0.001,0l78.613-65.641c5.138-4.29,8.072-10.589,8.05-17.282L186.023,12.626z
 M171.744,77.214l-73.112,61.047L65.844,98.993l105.824-88.362c0.501-0.419,1.061-0.631,1.661-0.631c1.115,0,2.688,0.825,2.693,2.66
l0.181,54.981C176.215,71.348,174.59,74.837,171.744,77.214z"/>
</svg>"""


def _render_svg_to_pixmap(svg_data, size):
    """Renders SVG data string to a QPixmap at the given size."""
    svg = svg_data.replace('viewBox=', f'width="{size}" height="{size}" viewBox=')
    pixmap = QPixmap()
    pixmap.loadFromData(svg.encode())
    return pixmap


def create_pencil_cursor():
    """
    Creates a pencil cursor from embedded SVG, tip pointing bottom-left.

    Returns:
        QCursor with hotspot at the pencil tip (bottom-left)
    """
    size = max(16, scaled(CURSOR_SIZE))
    svg = PENCIL_SVG.replace('#ffffff', CURSOR_FILL_COLOR).replace('#000000', CURSOR_OUTLINE_COLOR)
    pixmap = _render_svg_to_pixmap(svg, size)
    # Hotspot at the pencil tip — bottom-left of the SVG (approx 2/512, 462/512)
    return QCursor(pixmap, max(0, int(size * 0.004)), int(size * 0.90))


def create_eraser_cursor():
    """
    Creates an eraser cursor from embedded SVG, erasing edge at bottom-left.

    Returns:
        QCursor with hotspot at bottom-left erasing edge
    """
    size = max(16, scaled(CURSOR_SIZE))
    svg = ERASER_SVG.replace('#ffffff', CURSOR_FILL_COLOR).replace('#000000', CURSOR_OUTLINE_COLOR)
    pixmap = _render_svg_to_pixmap(svg, size)
    # Hotspot at the erasing edge — bottom-left area (approx 18/203, 191/203)
    return QCursor(pixmap, max(0, int(size * 0.09)), int(size * 0.94))


def create_pencil_icon(size=None, color="#000000"):
    """
    Creates a pencil QIcon from embedded SVG at the given size and color.

    Args:
        size: Icon size in pixels
        color: Hex color for the pencil fill

    Returns:
        QIcon: The pencil icon
    """
    if size is None:
        size = scaled(BUTTON_SIZE)
    # Icon uses transparent interior (no white fill), only the outline path
    svg = PENCIL_SVG.replace('fill="#ffffff"', 'fill="none"').replace('#000000', color)
    return QIcon(_render_svg_to_pixmap(svg, size))


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


def load_ui_scale():
    """Loads UI scale factor from settings file. Called before window creation."""
    config_path = get_config_path()
    if not config_path.exists():
        return 1.0
    config = configparser.ConfigParser()
    try:
        config.read(config_path)
        if config.has_option('appearance', 'ui_scale'):
            scale = config.getfloat('appearance', 'ui_scale')
            if 0.25 <= scale <= 2.0:
                return scale
    except Exception:
        pass
    return 1.0


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
    window_width = int(piano_width + total_horizontal_margin())
    window_height = int(INITIAL_KEY_HEIGHT + scaled(WINDOW_VERTICAL_MARGIN))
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


def blend_colors(base, target, factor):
    """
    Linearly interpolates between two QColors.

    Args:
        base: QColor to blend from (factor=0.0)
        target: QColor to blend to (factor=1.0)
        factor: Blend amount (0.0 to 1.0)

    Returns:
        QColor: The blended color
    """
    r = base.red() + (target.red() - base.red()) * factor
    g = base.green() + (target.green() - base.green()) * factor
    b = base.blue() + (target.blue() - base.blue()) * factor
    return QColor(int(r), int(g), int(b))


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


def make_button_style(bg_color="#f5f5f5", text_color="#2a2a2a", interactive=True):
    """
    Generates a QPushButton stylesheet with scaled dimensions.

    Args:
        bg_color: Background color hex string
        text_color: Text color hex string
        interactive: If True, includes hover/pressed/disabled states
    """
    border = scaled(2)
    radius = scaled(6)
    pad_bottom = scaled(1)

    style = f"""
        QPushButton {{
            background-color: {bg_color};
            color: {text_color};
            font-weight: bold;
            border: {border}px solid #707070;
            border-radius: {radius}px;
            padding: 0px 0px {pad_bottom}px 0px;
        }}
    """

    if interactive:
        style += """
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

    return style


# ============================================================================
# SETTINGS DIALOG
# ============================================================================

class UpdateChecker(QThread):
    """Background thread to check for new releases on GitHub."""
    result = pyqtSignal(str, str)  # (display_text, url_or_empty)

    def run(self):
        try:
            url = "https://codeberg.org/api/v1/repos/skoomabwoy/piano-midi-viewer/releases/latest"
            req = Request(url, headers={"User-Agent": "PianoMIDIViewer"})
            with urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            tag = data.get("tag_name", "")
            latest = tag.lstrip("v")
            if latest and self._is_newer(latest, VERSION):
                self.result.emit(
                    f"Version {latest} available",
                    "https://codeberg.org/skoomabwoy/piano-midi-viewer/releases"
                )
            else:
                self.result.emit("Up to date", "")
        except (URLError, OSError, ValueError, KeyError):
            self.result.emit("Could not check for updates", "")

    @staticmethod
    def _is_newer(remote, local):
        """Returns True if remote version is newer than local."""
        try:
            r = tuple(int(x) for x in remote.split("."))
            l = tuple(int(x) for x in local.split("."))
            return r > l
        except (ValueError, AttributeError):
            return False


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
        midi_header = QHBoxLayout()
        midi_label = QLabel("MIDI Input Device:")
        self.midi_status = QLabel("")
        self.midi_status.setStyleSheet("color: #cc3333;")
        midi_header.addWidget(midi_label)
        midi_header.addStretch()
        midi_header.addWidget(self.midi_status)

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

        layout.addLayout(midi_header)
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

        # UI SCALE
        scale_layout = QHBoxLayout()
        scale_label = QLabel("UI Scale")

        self.scale_dropdown = QComboBox()
        scale_values = [0.25, 0.50, 0.75, 1.0, 1.25, 1.50, 1.75, 2.0]
        for val in scale_values:
            self.scale_dropdown.addItem(f"{int(val * 100)}%", val)

        # Set current value
        index = self.scale_dropdown.findData(UI_SCALE_FACTOR)
        if index >= 0:
            self.scale_dropdown.setCurrentIndex(index)

        self.scale_dropdown.currentIndexChanged.connect(self.scale_changed)

        # Restart button (inserted between label and dropdown when scale changes)
        self.restart_button = QPushButton("Restart to apply")
        self.restart_button.setVisible(False)
        self.restart_button.clicked.connect(self.restart_app)

        scale_layout.addWidget(scale_label)
        scale_layout.addStretch()
        scale_layout.addWidget(self.restart_button)
        scale_layout.addWidget(self.scale_dropdown)
        layout.addLayout(scale_layout)

        # SEPARATOR
        layout.addSpacing(10)

        # SHOW OCTAVE NUMBERS CHECKBOX
        self.octave_numbers_checkbox = QCheckBox("Show Octave Numbers")
        self.octave_numbers_checkbox.setChecked(self.main_window.show_octave_numbers)
        self.octave_numbers_checkbox.stateChanged.connect(self.toggle_octave_numbers)

        layout.addWidget(self.octave_numbers_checkbox)

        # WHITE KEY NAMES CHECKBOX
        self.white_key_names_checkbox = QCheckBox("Show White Key Names")
        self.white_key_names_checkbox.setChecked(self.main_window.show_white_key_names)
        self.white_key_names_checkbox.stateChanged.connect(self.toggle_white_key_names)

        layout.addWidget(self.white_key_names_checkbox)

        # BLACK KEY NAMES CHECKBOX
        self.black_key_names_checkbox = QCheckBox("Show Black Key Names")
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

        # "Show only when pressed" checkbox
        self.names_when_pressed_checkbox = QCheckBox("Show note names only when pressed")
        self.names_when_pressed_checkbox.setChecked(self.main_window.show_names_when_pressed)
        self.names_when_pressed_checkbox.stateChanged.connect(self.toggle_names_when_pressed)
        # Enable only if at least one of white/black key names is on
        names_enabled = self.main_window.show_white_key_names or self.main_window.show_black_key_names
        self.names_when_pressed_checkbox.setEnabled(names_enabled)
        layout.addWidget(self.names_when_pressed_checkbox)

        # SEPARATOR
        layout.addSpacing(10)

        # SHOW VELOCITY CHECKBOX
        self.velocity_checkbox = QCheckBox("Show Velocity")
        self.velocity_checkbox.setChecked(self.main_window.show_velocity)
        self.velocity_checkbox.stateChanged.connect(self.toggle_velocity)
        layout.addWidget(self.velocity_checkbox)

        # VERSION + CHECK FOR UPDATES
        layout.addStretch()
        version_row = QHBoxLayout()
        self.version_label = QLabel(f"Version {VERSION}")
        self.version_label.setTextFormat(Qt.TextFormat.RichText)
        self.version_label.setOpenExternalLinks(True)
        self.version_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        version_row.addWidget(self.version_label)
        version_row.addStretch()
        self.update_button = QPushButton("Check for Updates")
        self.update_button.setFixedWidth(self.update_button.sizeHint().width())
        self.update_button.clicked.connect(self.check_for_updates)
        version_row.addWidget(self.update_button)
        layout.addLayout(version_row)

        # INFO LINK
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

        self.restart_button.setVisible(self.main_window.pending_ui_scale != UI_SCALE_FACTOR)
        self.adjustSize()
        self.setFixedSize(self.size())

    def populate_midi_devices(self):
        """Scans for available MIDI input devices."""
        self.midi_dropdown.blockSignals(True)
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
        self.midi_dropdown.blockSignals(False)

    def refresh_midi_devices(self):
        """Rescans for MIDI devices."""
        self.populate_midi_devices()

    def midi_device_changed(self, index):
        """Called when user selects a different MIDI device."""
        device_name = self.midi_dropdown.currentText()
        if device_name and device_name != "No MIDI devices found":
            if self.main_window.connect_midi_device(device_name):
                self.midi_status.setText("")
            else:
                # Connection failed — show status, revert dropdown, refresh list
                self.midi_status.setText("Device not found")
                QTimer.singleShot(3000, lambda: self.midi_status.setText(""))
                self.populate_midi_devices()

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

            # Update button visuals with new color
            self.main_window.update_sustain_button_visual()
            self.main_window.update_pencil_button_visual()

            # Update any glowing plus buttons with new color
            if self.main_window.piano.glow_left_plus:
                self.main_window.apply_button_glow(self.main_window.left_plus_btn, True)
            if self.main_window.piano.glow_right_plus:
                self.main_window.apply_button_glow(self.main_window.right_plus_btn, True)

            # Save color preference
            self.main_window.save_settings()

    def update_color_preview(self, color):
        """Updates the color preview button."""
        radius = 15
        self.color_preview.setStyleSheet(
            f"background-color: {color.name()}; border: 1px solid #999; border-radius: {radius}px;"
        )

    def scale_changed(self, index):
        """Called when user selects a different UI scale."""
        new_scale = self.scale_dropdown.currentData()
        self.restart_button.setVisible(new_scale != UI_SCALE_FACTOR)
        # Save immediately so it takes effect on next launch
        self.main_window.pending_ui_scale = new_scale
        self.main_window.save_settings()

    def restart_app(self):
        """Saves settings and restarts the application."""
        self.main_window.save_settings()
        kwargs = {"creationflags": subprocess.DETACHED_PROCESS} if sys.platform == "win32" else {"start_new_session": True}
        devnull = subprocess.DEVNULL
        if getattr(sys, "frozen", False):
            exe = os.path.abspath(sys.executable)
            cmd = [exe] + sys.argv[1:]
            kwargs["cwd"] = os.path.dirname(exe)
            # Clear PyInstaller env vars so the child process extracts
            # its own temp directory instead of reusing the parent's
            # (which gets cleaned up when the parent exits).
            env = os.environ.copy()
            env.pop("_MEIPASS2", None)
            env.pop("_PYI_ARCHIVE_FILE", None)
            kwargs["env"] = env
        else:
            cmd = [sys.executable] + sys.argv
        subprocess.Popen(cmd, stdin=devnull, stdout=devnull, stderr=devnull, **kwargs)
        QApplication.instance().quit()

    def toggle_octave_numbers(self, state):
        """Toggles octave number display."""
        self.main_window.show_octave_numbers = (state == Qt.CheckState.Checked.value)
        self.main_window.piano.update()
        self.main_window.save_settings()

    def toggle_white_key_names(self, state):
        """Toggles white key name display."""
        self.main_window.show_white_key_names = (state == Qt.CheckState.Checked.value)
        # Enable/disable "show only when pressed" based on whether any names are shown
        names_enabled = self.main_window.show_white_key_names or self.main_window.show_black_key_names
        self.names_when_pressed_checkbox.setEnabled(names_enabled)
        self.main_window.piano.update()
        self.main_window.save_settings()

    def toggle_black_key_names(self, state):
        """Toggles black key name display."""
        self.main_window.show_black_key_names = (state == Qt.CheckState.Checked.value)

        # Enable/disable the notation dropdown
        self.black_key_notation_dropdown.setEnabled(self.main_window.show_black_key_names)

        # Enable/disable "show only when pressed" based on whether any names are shown
        names_enabled = self.main_window.show_white_key_names or self.main_window.show_black_key_names
        self.names_when_pressed_checkbox.setEnabled(names_enabled)

        self.main_window.piano.update()
        self.main_window.save_settings()

    def notation_changed(self, index):
        """Called when black key notation type changes."""
        notation = self.black_key_notation_dropdown.currentData()
        self.main_window.black_key_notation = notation
        self.main_window.piano.update()
        self.main_window.save_settings()

    def toggle_names_when_pressed(self, state):
        """Toggles showing note names only when keys are pressed."""
        self.main_window.show_names_when_pressed = (state == Qt.CheckState.Checked.value)
        self.main_window.piano.update()
        self.main_window.save_settings()

    def toggle_velocity(self, state):
        """Toggles velocity visualization."""
        self.main_window.show_velocity = (state == Qt.CheckState.Checked.value)
        self.main_window.piano.update()
        self.main_window.save_settings()

    def check_for_updates(self):
        """Checks Codeberg for a newer release in a background thread."""
        self.update_button.setEnabled(False)
        self.update_button.setText("Checking...")
        self._update_checker = UpdateChecker()
        self._update_checker.result.connect(self._on_update_result)
        self._update_checker.start()

    def _on_update_result(self, text, url):
        """Handles the result from the update checker thread."""
        self.update_button.setEnabled(True)
        self.update_button.setText("Check for Updates")
        if url:
            self.version_label.setText(f'<a href="{url}" style="color: #5094d4;">{text}</a>')
        else:
            self.version_label.setText(text)
            # Revert to version number after a few seconds
            QTimer.singleShot(STATUS_MESSAGE_DURATION, self._restore_version_label)

    def _restore_version_label(self):
        """Restores the version label to show the version number."""
        self.version_label.setText(f"Version {VERSION}")


# ============================================================================
# PIANO KEYBOARD WIDGET
# ============================================================================

class PianoKeyboard(QWidget):
    """Custom widget that draws a piano keyboard."""

    def __init__(self):
        super().__init__()
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)

        # MIDI note range - which notes are currently visible
        self.start_note = DEFAULT_START_NOTE
        self.end_note = DEFAULT_END_NOTE

        # Note tracking - which notes are currently highlighted
        self.active_notes = {}               # MIDI notes currently pressed → velocity (visible range)
        self.active_notes_left = set()      # MIDI notes being pressed below visible range
        self.active_notes_right = set()     # MIDI notes being pressed above visible range

        # Drawn notes (pencil tool marks, separate from playing)
        self.drawn_notes = set()         # Notes marked by the pencil tool (visible range only)

        # Mouse interaction state
        self.mouse_held_note = None   # Which note the mouse cursor is currently over (or None)
        self._drag_button = None      # Which mouse button started the current drag
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

        # Get velocity visualization setting
        main_window = self._get_main_window()
        show_velocity = main_window.show_velocity if main_window else False

        # Draw white keys
        for note in range(self.start_note, self.end_note + 1):
            if not is_black_key(note):
                self._draw_white_key(
                    painter, note, white_key_width,
                    keyboard_x, keyboard_y, keyboard_height, key_corner_radius,
                    show_velocity
                )

        # Draw black keys
        black_key_width = white_key_width * BLACK_KEY_WIDTH_RATIO
        black_key_height = keyboard_height * BLACK_KEY_HEIGHT_RATIO

        for note in range(self.start_note, self.end_note + 1):
            if is_black_key(note):
                self._draw_black_key(
                    painter, note, white_key_width,
                    black_key_width, keyboard_x, keyboard_y, black_key_height, key_corner_radius,
                    show_velocity
                )

        # Draw note names and octave numbers (if enabled)
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

    def _draw_white_key(self, painter, midi_note, key_width, x_offset, y_offset, height, corner_radius, show_velocity=False):
        """Draws a single white key."""
        white_index = get_white_key_index(midi_note, self.start_note)
        x = x_offset + (white_index * key_width)

        # Calculate dynamic gap based on key width (3%, clamped 1-5px per side)
        key_gap = min(KEY_GAP_MAX, max(KEY_GAP_MIN, round(key_width * KEY_GAP_RATIO)))

        rect_x = x + key_gap
        rect_y = y_offset
        rect_width = key_width - key_gap * 2
        rect_height = height

        # Highlight if note is active (pressed, drawn, or mouse-held)
        is_highlighted = (midi_note in self.active_notes or
                         midi_note in self.drawn_notes or
                         (midi_note == self.mouse_held_note and self.glissando_mode != 'off'))

        base_color = QColor(252, 252, 252)
        if is_highlighted:
            if show_velocity and midi_note in self.active_notes:
                velocity = self.active_notes[midi_note]
                factor = 0.3 + 0.7 * (velocity / 127.0)
                fill_color = blend_colors(base_color, self.highlight_color, factor)
            else:
                fill_color = self.highlight_color
        else:
            fill_color = base_color

        painter.setBrush(QBrush(fill_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(
            QRectF(rect_x, rect_y, rect_width, rect_height),
            corner_radius, corner_radius
        )

        # Draw shadow lines on non-highlighted keys (disabled at small sizes for readability)
        if not is_highlighted and key_width >= SHADOW_DISABLE_WIDTH:
            shadow_color = QColor(170, 170, 170)
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
        border_color = QColor(25, 25, 25) if is_highlighted else QColor(85, 85, 85)
        painter.setPen(QPen(border_color, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(
            QRectF(rect_x, rect_y, rect_width, rect_height),
            corner_radius, corner_radius
        )

    def _draw_black_key(self, painter, midi_note, white_key_width,
                        black_key_width, x_offset, y_offset, black_key_height, corner_radius, show_velocity=False):
        """Draws a single black key."""
        left_white_note = get_left_white_key(midi_note, self.start_note)
        white_index = get_white_key_index(left_white_note, self.start_note)

        x = x_offset + ((white_index + 1) * white_key_width - black_key_width / 2)

        rect_x = x
        rect_y = y_offset
        rect_width = black_key_width
        rect_height = black_key_height

        # Highlight if note is active (pressed, drawn, or mouse-held)
        is_highlighted = (midi_note in self.active_notes or
                         midi_note in self.drawn_notes or
                         (midi_note == self.mouse_held_note and self.glissando_mode != 'off'))

        base_color = QColor(16, 16, 16)
        if is_highlighted:
            if show_velocity and midi_note in self.active_notes:
                velocity = self.active_notes[midi_note]
                factor = 0.3 + 0.7 * (velocity / 127.0)
                fill_color = blend_colors(base_color, self.highlight_color, factor)
            else:
                fill_color = self.highlight_color
        else:
            fill_color = base_color

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
                             note in self.drawn_notes or
                             (note == self.mouse_held_note and self.glissando_mode != 'off'))

            # Determine text color based on highlight state
            if is_highlighted:
                if main_window.show_velocity and note in self.active_notes:
                    velocity = self.active_notes[note]
                    factor = 0.3 + 0.7 * (velocity / 127.0)
                    fill_color = blend_colors(QColor(252, 252, 252), self.highlight_color, factor)
                    text_color = get_text_color_for_highlight(fill_color)
                else:
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
                # Skip note name (not octave number) if "show only when pressed" and key is not active
                show_name = not main_window.show_names_when_pressed or is_highlighted
                if note_name and show_name:
                    text_width = font_metrics.horizontalAdvance(note_name)
                    text_x = key_center_x - text_width / 2
                    painter.drawText(int(text_x), int(letter_baseline_y), note_name)

                # Draw octave number (C keys only) - always shown regardless of pressed state
                if is_c_note:
                    octave_text = str(octave_num)
                    text_width = font_metrics.horizontalAdvance(octave_text)
                    text_x = key_center_x - text_width / 2
                    painter.drawText(int(text_x), int(octave_baseline_y), octave_text)

            # CASE 2: Only note names enabled
            elif main_window.show_white_key_names:
                # Skip if "show only when pressed" is enabled and key is not active
                if main_window.show_names_when_pressed and not is_highlighted:
                    continue

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
                             note in self.drawn_notes or
                             (note == self.mouse_held_note and self.glissando_mode != 'off'))

            # Skip if "show only when pressed" is enabled and key is not active
            if main_window.show_names_when_pressed and not is_highlighted:
                continue

            # Determine text color based on highlight state
            if is_highlighted:
                if main_window.show_velocity and note in self.active_notes:
                    velocity = self.active_notes[note]
                    factor = 0.3 + 0.7 * (velocity / 127.0)
                    fill_color = blend_colors(QColor(16, 16, 16), self.highlight_color, factor)
                    text_color = get_text_color_for_highlight(fill_color)
                else:
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
        """Returns the parent PianoMIDIViewer instance, or None."""
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
        key_gap = min(KEY_GAP_MAX, max(KEY_GAP_MIN, round(white_key_width * KEY_GAP_RATIO)))

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

                if key_x + key_gap <= x <= key_x + white_key_width - key_gap:
                    return note

        return None

    def mousePressEvent(self, event):
        """
        Handle mouse press on piano keys.

        Pencil active: left click draws, right click erases.
        Playing: left click highlights the key while held.
        Gap clicks snap to the closest key.
        """
        note = self._get_note_at_position(event.position().x(), event.position().y())

        # If clicked on a gap, snap to the closest key
        if note is None:
            note = self._find_closest_note_to_position(event.position().x(), event.position().y())

        if note is not None:
            main_window = self._get_main_window()

            if main_window and main_window.pencil_active:
                # Ignore new button presses while another button is held (prevents state confusion)
                if self.mouse_held_note is not None:
                    return
                if event.button() == Qt.MouseButton.LeftButton:
                    # Left click: draw (add note)
                    self.glissando_mode = 'on'
                    self.drawn_notes.add(note)
                elif event.button() == Qt.MouseButton.RightButton:
                    # Right click: erase (remove note)
                    self.glissando_mode = 'off'
                    self.drawn_notes.discard(note)
                    self.setCursor(create_eraser_cursor())
                else:
                    return
                self._drag_button = event.button()
                self.mouse_held_note = note
                self.update()

            elif event.button() == Qt.MouseButton.LeftButton:
                # Playing mode (left click only): highlight the note while held
                self.active_notes[note] = 127  # Mouse clicks = full velocity
                self.mouse_held_note = note
                self.glissando_mode = None
                self.update()

    def mouseMoveEvent(self, event):
        """
        Handle mouse drag across piano keys (glissando).

        Behavior depends on pencil state:
        - Pencil active: Paint or erase drawn_notes based on glissando_mode
        - Playing: Track current note under cursor
        """
        if self.mouse_held_note is not None:
            note = self._get_note_at_position(event.position().x(), event.position().y())

            # Ignore None (grey background) to allow glissando across gaps between keys
            if note is None:
                return

            if note != self.mouse_held_note:
                main_window = self._get_main_window()

                if main_window and main_window.pencil_active:
                    # Pencil glissando: paint or erase drawn_notes
                    if self.glissando_mode == 'on':
                        self.drawn_notes.add(note)
                    elif self.glissando_mode == 'off':
                        self.drawn_notes.discard(note)
                else:
                    # Playing: move active note to new key
                    self.active_notes.pop(self.mouse_held_note, None)
                    self.active_notes[note] = 127

                self.mouse_held_note = note
                self.update()

    def mouseReleaseEvent(self, event):
        """Handle mouse release."""
        if self.mouse_held_note is not None:
            main_window = self._get_main_window()

            if main_window and main_window.pencil_active:
                # Only process release of the button that started the drag
                if event.button() != getattr(self, '_drag_button', None):
                    return
                self._drag_button = None
                # Restore pencil cursor if eraser was used (right click)
                if self.glissando_mode == 'off':
                    self.setCursor(create_pencil_cursor())

            else:
                # Playing: remove from active_notes
                if self.mouse_held_note in self.active_notes:
                    self.active_notes.pop(self.mouse_held_note, None)

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
        self.midi_scanner = None  # Persistent MidiIn for port listing (never opens a port)
        self.current_midi_device = None
        self.midi_timer = None
        self.known_midi_devices = []
        self.device_scan_timer = None
        self.status_hide_timer = None

        # Sustain state — tracked purely for the S indicator
        self.sustain_pedal_active = False    # MIDI sustain pedal held (CC 64)

        # Pencil tool state (drawing is independent from playing)
        self.pencil_active = False  # Whether pencil tool is currently active

        # Note name and octave number display settings
        self.show_octave_numbers = True   # Default: ON
        self.show_white_key_names = True  # Default: ON
        self.show_black_key_names = False # Default: OFF
        self.black_key_notation = "Flats"  # Default: Flats
        self.show_names_when_pressed = False  # Default: OFF (show names on all keys)
        self.show_velocity = False  # Default: OFF (all notes same brightness)

        # UI scale (pending value saved for next launch)
        self.pending_ui_scale = UI_SCALE_FACTOR

        self.init_ui()
        self.setup_midi_polling()
        self.setup_device_scanning()
        self.load_settings()  # Load saved settings after UI is initialized

    def init_ui(self):
        """Sets up the user interface."""
        self.setWindowTitle("Piano MIDI Viewer")
        self.setWindowIcon(create_piano_icon())

        # Calculate initial window size from key dimensions
        initial_width, initial_height = calculate_initial_window_size()
        self.resize(initial_width, initial_height)

        # Set minimum size (for UI usability) - uses defaults since piano not created yet
        num_white_keys = count_white_keys(DEFAULT_START_NOTE, DEFAULT_END_NOTE)
        min_key_width = PRACTICAL_MIN_KEY_WIDTH
        min_key_height = min_key_width * MIN_HEIGHT_RATIO
        min_width = (min_key_width * num_white_keys) + total_horizontal_margin()
        key_based_height = min_key_height + (KEYBOARD_CANVAS_MARGIN * 2) + scaled(WINDOW_VERTICAL_MARGIN)
        min_height = max(key_based_height, min_window_height())  # Ensure buttons fit
        self.setMinimumSize(int(min_width), int(min_height))

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(0)
        lm = scaled(LAYOUT_MARGIN)
        main_layout.setContentsMargins(lm, lm, lm, lm)

        # Button styling (consolidated via make_button_style for scaling support)
        button_style = make_button_style()
        btn_sz = scaled(BUTTON_SIZE)

        # Use JetBrains Mono for button labels (consistent across platforms)
        button_font_family = LOADED_FONT_FAMILY if LOADED_FONT_FAMILY else "monospace"
        button_font = QFont(button_font_family)
        button_font.setPixelSize(int(btn_sz * ICON_SIZE_RATIO))

        # LEFT SIDE (pencil button + octave controls)
        left_container = QWidget()
        left_container.setFixedWidth(scaled(BUTTON_AREA_WIDTH))
        left_layout = QVBoxLayout(left_container)
        left_layout.setSpacing(scaled(BUTTON_SPACING))
        left_layout.setContentsMargins(0, 0, scaled(3), 0)
        left_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Pencil button: click to enter/exit drawing tool
        self.pencil_button = QPushButton()
        self.pencil_button.setToolTip("Pencil tool — left click to mark, right click to erase\nPress Esc to exit")
        self.pencil_button.setFixedSize(btn_sz, btn_sz)
        self.pencil_button.setIcon(create_pencil_icon())
        self.pencil_button.setIconSize(self.pencil_button.size() * 0.7)
        self.pencil_button.setStyleSheet(button_style)
        self.pencil_button.clicked.connect(self.toggle_pencil)

        left_layout.addWidget(self.pencil_button, alignment=Qt.AlignmentFlag.AlignCenter)
        left_layout.addStretch()

        self.left_plus_btn = QPushButton("+")
        self.left_plus_btn.setToolTip("Add octave on the left (lower notes)")
        self.left_plus_btn.setFixedSize(btn_sz, btn_sz)
        self.left_plus_btn.setFont(button_font)
        self.left_plus_btn.setStyleSheet(button_style)
        self.left_plus_btn.clicked.connect(self.add_octave_left)

        # Use en-dash for minus (better vertical centering in JetBrains Mono)
        self.left_minus_btn = QPushButton("−")
        self.left_minus_btn.setToolTip("Remove octave on the left (lower notes)")
        self.left_minus_btn.setFixedSize(btn_sz, btn_sz)
        self.left_minus_btn.setFont(button_font)
        self.left_minus_btn.setStyleSheet(button_style)
        self.left_minus_btn.clicked.connect(self.remove_octave_left)

        left_layout.addWidget(self.left_plus_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(self.left_minus_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # CENTER
        self.piano = PianoKeyboard()

        # RIGHT SIDE (settings + sustain + octave controls)
        right_container = QWidget()
        right_container.setFixedWidth(scaled(BUTTON_AREA_WIDTH))
        right_layout = QVBoxLayout(right_container)
        right_layout.setSpacing(scaled(BUTTON_SPACING))
        right_layout.setContentsMargins(scaled(3), 0, 0, 0)
        right_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Settings button uses SVG icon for consistent cross-platform rendering
        self.settings_button = QPushButton()
        self.settings_button.setToolTip("Open Settings")
        self.settings_button.setFixedSize(btn_sz, btn_sz)
        self.settings_button.setIcon(create_settings_icon(btn_sz, "#000000"))
        self.settings_button.setIconSize(self.settings_button.size() * 0.7)
        self.settings_button.setStyleSheet(button_style)
        self.settings_button.clicked.connect(self.open_settings)

        # Sustain button: indicator only (lights up when sustain pedal is held)
        self.sustain_button = QPushButton("S")
        self.sustain_button.setToolTip("Sustain pedal indicator — lights up when your sustain pedal is held")
        self.sustain_button.setFixedSize(btn_sz, btn_sz)
        self.sustain_button.setFont(button_font)
        self.sustain_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        right_layout.addWidget(self.settings_button, alignment=Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(self.sustain_button, alignment=Qt.AlignmentFlag.AlignCenter)
        right_layout.addStretch()

        self.right_plus_btn = QPushButton("+")
        self.right_plus_btn.setToolTip("Add octave on the right (higher notes)")
        self.right_plus_btn.setFixedSize(btn_sz, btn_sz)
        self.right_plus_btn.setFont(button_font)
        self.right_plus_btn.setStyleSheet(button_style)
        self.right_plus_btn.clicked.connect(self.add_octave_right)

        # Use en-dash for minus (better vertical centering in JetBrains Mono)
        self.right_minus_btn = QPushButton("−")
        self.right_minus_btn.setToolTip("Remove octave on the right (higher notes)")
        self.right_minus_btn.setFixedSize(btn_sz, btn_sz)
        self.right_minus_btn.setFont(button_font)
        self.right_minus_btn.setStyleSheet(button_style)
        self.right_minus_btn.clicked.connect(self.remove_octave_right)

        right_layout.addWidget(self.right_plus_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(self.right_minus_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # Status overlay for MIDI connection notifications (parented to piano, floats on top)
        self.status_label = QLabel("", self.piano)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(
            "background-color: #404040; color: #ffffff;"
            "padding: 6px 16px; border-radius: 8px;"
        )
        self.status_label.setVisible(False)

        # ASSEMBLE
        main_layout.addWidget(left_container)
        main_layout.addWidget(self.piano, 1)
        main_layout.addWidget(right_container)

        self.update_button_states()
        self.update_sustain_button_visual()

    def open_settings(self):
        """Opens the settings dialog (non-modal so MIDI keeps working)."""
        if hasattr(self, '_settings_dialog') and self._settings_dialog.isVisible():
            self._settings_dialog.raise_()
            return
        self._settings_dialog = SettingsDialog(self)
        self._settings_dialog.show()

    def load_settings(self):
        """
        Loads settings from the configuration file.

        Reads saved settings for:
        - MIDI device selection
        - Highlight color
        - Note name and octave number display options
        - Keyboard range (start_note and end_note)
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

            if config.has_option('appearance', 'show_names_when_pressed'):
                self.show_names_when_pressed = config.getboolean('appearance', 'show_names_when_pressed')
            if config.has_option('appearance', 'show_velocity'):
                self.show_velocity = config.getboolean('appearance', 'show_velocity')

            # Load keyboard range (must be before geometry restoration)
            if config.has_option('keyboard', 'start_note') and config.has_option('keyboard', 'end_note'):
                start_note = config.getint('keyboard', 'start_note')
                end_note = config.getint('keyboard', 'end_note')
                # Validate the range
                if (MIDI_NOTE_MIN <= start_note <= MIDI_NOTE_MAX and
                    MIDI_NOTE_MIN <= end_note <= MIDI_NOTE_MAX and
                    end_note >= start_note + 11):  # At least 1 octave
                    self.piano.start_note = start_note
                    self.piano.end_note = end_note
                    self.update_button_states()
                    self.update_minimum_size()

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
        - Keyboard range (start_note and end_note)
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
            'black_key_notation': self.black_key_notation,
            'show_names_when_pressed': str(self.show_names_when_pressed),
            'show_velocity': str(self.show_velocity),
            'ui_scale': str(self.pending_ui_scale)
        }

        # Keyboard range settings
        config['keyboard'] = {
            'start_note': str(self.piano.start_note),
            'end_note': str(self.piano.end_note)
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

    def toggle_pencil(self):
        """
        Toggles the pencil drawing tool on/off.

        When activating: clears all playing highlights, sets pencil cursor.
        When deactivating: clears all drawn marks, restores normal cursor.
        """
        if self.pencil_active:
            # Deactivate pencil
            self.pencil_active = False
            self.piano.drawn_notes.clear()
            self.piano.setCursor(Qt.CursorShape.ArrowCursor)
            # Clear any glows that were lit due to out-of-range drawn notes
            if self.piano.glow_left_plus:
                self.piano.glow_left_plus = False
                self.apply_button_glow(self.left_plus_btn, False)
            if self.piano.glow_right_plus:
                self.piano.glow_right_plus = False
                self.apply_button_glow(self.right_plus_btn, False)
        else:
            # Activate pencil - clear playing state first
            self.pencil_active = True
            self.piano.active_notes.clear()
            self.piano.active_notes_left.clear()
            self.piano.active_notes_right.clear()
            self.piano.mouse_held_note = None
            self.piano.glissando_mode = None

            # Clear button glows
            if self.piano.glow_left_plus:
                self.piano.glow_left_plus = False
                self.apply_button_glow(self.left_plus_btn, False)
            if self.piano.glow_right_plus:
                self.piano.glow_right_plus = False
                self.apply_button_glow(self.right_plus_btn, False)

            self.piano.setCursor(create_pencil_cursor())

        self.update_pencil_button_visual()
        self.piano.update()

    def update_pencil_button_visual(self):
        """
        Updates the pencil button appearance based on pencil tool state.

        When active: highlight color background, icon color adapts for contrast.
        When inactive: normal grey button with black icon.
        """
        if self.pencil_active:
            bg_color = self.piano.highlight_color.name()
            icon_color = get_text_color_for_highlight(self.piano.highlight_color).name()
            self.pencil_button.setIcon(create_pencil_icon(color=icon_color))
            self.pencil_button.setStyleSheet(make_button_style(bg_color=bg_color, text_color=icon_color, interactive=False))
        else:
            self.pencil_button.setIcon(create_pencil_icon(color="#000000"))
            self.pencil_button.setStyleSheet(make_button_style(interactive=False))

    def update_sustain_button_visual(self):
        """
        Updates the sustain button appearance based on the MIDI sustain pedal state.

        Lights up in the highlight color when the pedal is held, unlit otherwise.
        Text color adapts based on highlight color luminance.
        """
        if self.sustain_pedal_active:
            bg_color = self.piano.highlight_color.name()
            text_color = get_text_color_for_highlight(self.piano.highlight_color).name()
            self.sustain_button.setStyleSheet(make_button_style(bg_color=bg_color, text_color=text_color, interactive=False))
        else:
            self.sustain_button.setStyleSheet(make_button_style(interactive=False))

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
        """Returns list of available MIDI input devices using persistent scanner."""
        try:
            if not self.midi_scanner:
                self.midi_scanner = rtmidi.MidiIn()
            return self.midi_scanner.get_ports()
        except Exception as e:
            print(f"Error scanning MIDI devices: {e}")
            return []

    def connect_midi_device(self, device_name):
        """Connects to the specified MIDI input device.
        Returns True on success, False on failure."""
        # Check availability using the persistent scanner
        ports = self.get_midi_devices()
        if device_name not in ports:
            print(f"Device not found: {device_name}")
            self.show_status_message(f"Not found: {device_name}")
            return False

        try:
            new_midi_in = rtmidi.MidiIn()
            port_index = ports.index(device_name)
            new_midi_in.open_port(port_index)
        except Exception as e:
            print(f"Error connecting to MIDI device: {e}")
            self.show_status_message(f"Connection failed: {device_name}")
            return False

        # New connection succeeded — now close the old one
        if self.midi_in:
            try:
                self.midi_in.close_port()
            except Exception:
                pass
            del self.midi_in

        self.midi_in = new_midi_in
        self.current_midi_device = device_name
        print(f"Connected to MIDI device: {device_name}")
        self.show_status_message(f"Connected: {device_name}")
        self.save_settings()
        return True

    def setup_midi_polling(self):
        """Sets up a timer to poll for MIDI messages."""
        self.midi_timer = QTimer()
        self.midi_timer.timeout.connect(self.poll_midi_messages)
        self.midi_timer.start(MIDI_POLL_INTERVAL)

    def setup_device_scanning(self):
        """Sets up a timer to periodically scan for MIDI device changes."""
        # Snapshot current ports so the first scan doesn't treat them as new
        self.known_midi_devices = self.get_midi_devices()
        self.device_scan_timer = QTimer()
        self.device_scan_timer.timeout.connect(self.scan_midi_devices)
        self.device_scan_timer.start(MIDI_SCAN_INTERVAL)

    def scan_midi_devices(self):
        """Checks for MIDI device changes (hot-plug detection)."""
        current_ports = self.get_midi_devices()

        previous = set(self.known_midi_devices)
        current = set(current_ports)
        self.known_midi_devices = list(current_ports)

        if current == previous:
            return

        appeared = current - previous
        disappeared = previous - current

        # Device we were using vanished — handle disconnect
        if self.current_midi_device and self.current_midi_device in disappeared:
            self.handle_midi_disconnect()

        # Auto-connect: if we have no connection and a new device appeared, connect to it
        if not self.midi_in and appeared:
            # Prefer reconnecting to previously saved device if it reappeared
            if self.current_midi_device in appeared:
                self.connect_midi_device(self.current_midi_device)
            else:
                # Connect to the first new device
                self.connect_midi_device(list(appeared)[0])

    def handle_midi_disconnect(self):
        """Handles a MIDI device disconnection gracefully."""
        device_name = self.current_midi_device or "Unknown device"

        # Clean up the MIDI connection
        if self.midi_in:
            try:
                self.midi_in.close_port()
            except Exception:
                pass
            del self.midi_in
            self.midi_in = None

        # Don't clear current_midi_device — keep it for auto-reconnect
        # self.current_midi_device stays set so scan_midi_devices can reconnect

        # Clear all active notes so keys don't stay lit
        self.piano.active_notes.clear()
        self.piano.active_notes_left.clear()
        self.piano.active_notes_right.clear()

        # Reset button glows
        if self.piano.glow_left_plus:
            self.piano.glow_left_plus = False
            self.apply_button_glow(self.left_plus_btn, False)
        if self.piano.glow_right_plus:
            self.piano.glow_right_plus = False
            self.apply_button_glow(self.right_plus_btn, False)

        # Reset sustain indicator
        if self.sustain_pedal_active:
            self.sustain_pedal_active = False
            self.update_sustain_button_visual()

        self.piano.update()
        self.show_status_message(f"Disconnected: {device_name}")

    def show_status_message(self, text):
        """Shows a temporary overlay notification centered on the piano."""
        # Match font size to note labels (based on current key width)
        num_white = count_white_keys(self.piano.start_note, self.piano.end_note)
        if num_white > 0:
            white_key_width = self.piano.width() / num_white
            font_size = max(8, int(white_key_width / 2.0))
        else:
            font_size = 13
        self.status_label.setStyleSheet(
            f"background-color: #404040; color: #ffffff;"
            f"font-size: {font_size}px; padding: 6px 16px; border-radius: 8px;"
        )
        self.status_label.setText(text)
        self.status_label.adjustSize()
        # Center horizontally, place near the bottom of the piano
        x = (self.piano.width() - self.status_label.width()) // 2
        y = self.piano.height() - self.status_label.height() - 12
        self.status_label.move(max(0, x), max(0, y))
        self.status_label.setVisible(True)
        self.status_label.raise_()

        # Cancel any existing hide timer
        if self.status_hide_timer:
            self.status_hide_timer.stop()

        self.status_hide_timer = QTimer()
        self.status_hide_timer.setSingleShot(True)
        self.status_hide_timer.timeout.connect(lambda: self.status_label.setVisible(False))
        self.status_hide_timer.start(STATUS_MESSAGE_DURATION)

    def poll_midi_messages(self):
        """Checks for new MIDI messages and processes them."""
        if not self.midi_in:
            return

        try:
            while True:
                message = self.midi_in.get_message()

                if message is None:
                    break

                midi_data, _ = message
                self.process_midi_message(midi_data)

        except Exception as e:
            print(f"Error polling MIDI: {e}")
            self.handle_midi_disconnect()

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
                self.sustain_pedal_active = (controller_value >= 64)
                self.update_sustain_button_visual()

        # Note On/Off messages
        elif message_type == 0x90 and data2 > 0:
            self.handle_note_on(data1, data2)
        elif message_type == 0x80 or (message_type == 0x90 and data2 == 0):
            self.handle_note_off(data1)

    def handle_note_on(self, note_number, velocity=127):
        """
        Handles a Note On MIDI event.

        Behavior depends on pencil state:
        - Pencil active: toggle in drawn_notes (only visible range)
        - Playing (default): add to active_notes with velocity
        """
        if self.pencil_active:
            # Drawing: toggle in drawn_notes (only visible range)
            if self.piano.start_note <= note_number <= self.piano.end_note:
                if note_number in self.piano.drawn_notes:
                    self.piano.drawn_notes.discard(note_number)
                else:
                    self.piano.drawn_notes.add(note_number)
                self.piano.update()
            # Out-of-range notes ignored in drawing mode
            return

        # Playing mode: highlight the note while it is physically pressed
        if self.piano.start_note <= note_number <= self.piano.end_note:
            self.piano.active_notes[note_number] = velocity
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

        Behavior depends on pencil state:
        - Pencil active: ignore Note Off entirely (marks persist)
        - Playing (default): remove from active_notes (note goes dark immediately)
        """
        if self.pencil_active:
            # Drawing: ignore Note Off entirely
            return

        # Handle notes within visible range
        if note_number in self.piano.active_notes:
            self.piano.active_notes.pop(note_number, None)
            self.piano.update()

        # Handle notes outside visible range (left)
        if note_number in self.piano.active_notes_left:
            self.piano.active_notes_left.discard(note_number)
            if not self.piano.active_notes_left and self.piano.glow_left_plus:
                self.piano.glow_left_plus = False
                self.apply_button_glow(self.left_plus_btn, False)

        # Handle notes outside visible range (right)
        if note_number in self.piano.active_notes_right:
            self.piano.active_notes_right.discard(note_number)
            if not self.piano.active_notes_right and self.piano.glow_right_plus:
                self.piano.glow_right_plus = False
                self.apply_button_glow(self.right_plus_btn, False)

    def apply_button_glow(self, button, glow):
        """Applies or removes a glow effect on a button.
        Text color adapts based on highlight color luminance."""
        if glow:
            bg_color = self.piano.highlight_color.name()
            text_color = get_text_color_for_highlight(self.piano.highlight_color).name()
            button.setStyleSheet(make_button_style(bg_color=bg_color, text_color=text_color, interactive=False))
        else:
            button.setStyleSheet(make_button_style())

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

            # Update left glow if no more notes (active or drawn) remain outside
            drawn_left = any(n < self.piano.start_note for n in self.piano.drawn_notes)
            if not self.piano.active_notes_left and not drawn_left and self.piano.glow_left_plus:
                self.piano.glow_left_plus = False
                self.apply_button_glow(self.left_plus_btn, False)

            # Calculate new window width to maintain key size
            new_num_white = count_white_keys(self.piano.start_note, self.piano.end_note)
            new_piano_width = key_width * new_num_white
            new_window_width = round(new_piano_width + total_horizontal_margin())

            # Resize window
            self.resize(new_window_width, self.height())

            self.piano.update()
            self.update_button_states()
            self.update_minimum_size()

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

            # Turn on glow if active or drawn notes are now outside the left boundary
            drawn_left = any(n < self.piano.start_note for n in self.piano.drawn_notes)
            if (self.piano.active_notes_left or drawn_left) and not self.piano.glow_left_plus:
                self.piano.glow_left_plus = True
                self.apply_button_glow(self.left_plus_btn, True)

            # Calculate new window width to maintain key size
            new_num_white = count_white_keys(self.piano.start_note, self.piano.end_note)
            new_piano_width = key_width * new_num_white
            new_window_width = round(new_piano_width + total_horizontal_margin())

            # Resize window
            self.resize(new_window_width, self.height())

            self.piano.update()
            self.update_button_states()
            self.update_minimum_size()

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

            # Update right glow if no more notes (active or drawn) remain outside
            drawn_right = any(n > self.piano.end_note for n in self.piano.drawn_notes)
            if not self.piano.active_notes_right and not drawn_right and self.piano.glow_right_plus:
                self.piano.glow_right_plus = False
                self.apply_button_glow(self.right_plus_btn, False)

            # Calculate new window width to maintain key size
            new_num_white = count_white_keys(self.piano.start_note, self.piano.end_note)
            new_piano_width = key_width * new_num_white
            new_window_width = round(new_piano_width + total_horizontal_margin())

            # Resize window
            self.resize(new_window_width, self.height())

            self.piano.update()
            self.update_button_states()
            self.update_minimum_size()

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

            # Turn on glow if active or drawn notes are now outside the right boundary
            drawn_right = any(n > self.piano.end_note for n in self.piano.drawn_notes)
            if (self.piano.active_notes_right or drawn_right) and not self.piano.glow_right_plus:
                self.piano.glow_right_plus = True
                self.apply_button_glow(self.right_plus_btn, True)

            # Calculate new window width to maintain key size
            new_num_white = count_white_keys(self.piano.start_note, self.piano.end_note)
            new_piano_width = key_width * new_num_white
            new_window_width = round(new_piano_width + total_horizontal_margin())

            # Resize window
            self.resize(new_window_width, self.height())

            self.piano.update()
            self.update_button_states()
            self.update_minimum_size()

    def update_button_states(self):
        """Updates the enabled/disabled state of octave control buttons."""
        self.left_plus_btn.setEnabled(self.piano.start_note > MIDI_NOTE_MIN + 12)
        self.left_minus_btn.setEnabled(self.piano.end_note - self.piano.start_note > 11)
        self.right_plus_btn.setEnabled(self.piano.end_note < MIDI_NOTE_MAX - 12)
        self.right_minus_btn.setEnabled(self.piano.end_note - self.piano.start_note > 11)

    def update_minimum_size(self):
        """Updates minimum window size based on current octave range."""
        num_white_keys = count_white_keys(self.piano.start_note, self.piano.end_note)
        min_key_width = PRACTICAL_MIN_KEY_WIDTH
        min_key_height = min_key_width * MIN_HEIGHT_RATIO
        min_width = (min_key_width * num_white_keys) + total_horizontal_margin()
        key_based_height = min_key_height + (KEYBOARD_CANVAS_MARGIN * 2) + scaled(WINDOW_VERTICAL_MARGIN)
        min_height = max(key_based_height, min_window_height())  # Ensure buttons fit
        self.setMinimumSize(int(min_width), int(min_height))

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

            h_margin = total_horizontal_margin()
            v_margin = scaled(WINDOW_VERTICAL_MARGIN)
            piano_width = w - h_margin
            piano_height = h - v_margin
            white_key_width = piano_width / num_white_keys
            white_key_height = piano_height - (KEYBOARD_CANVAS_MARGIN * 2)

            # Calculate current height ratio
            if white_key_width > 0:
                height_ratio = white_key_height / white_key_width

                # Too tall (ratio > 6)? Reduce height
                if height_ratio > MAX_HEIGHT_RATIO:
                    white_key_height = white_key_width * MAX_HEIGHT_RATIO
                    h = round(white_key_height + (KEYBOARD_CANVAS_MARGIN * 2) + v_margin)

                # Too short (ratio < 3)? Reduce width
                elif height_ratio < MIN_HEIGHT_RATIO:
                    white_key_width = white_key_height / MIN_HEIGHT_RATIO
                    w = round(white_key_width * num_white_keys + h_margin)

            # Apply constrained size
            if w != self.width() or h != self.height():
                self.resize(w, h)

        finally:
            self._in_resize_event = False

    def keyPressEvent(self, event):
        """Handle keyboard key press events."""
        # Esc exits pencil drawing tool
        if event.key() == Qt.Key.Key_Escape and self.pencil_active:
            self.toggle_pencil()
        # P toggles pencil tool on/off
        elif event.key() == Qt.Key.Key_P and not event.modifiers():
            self.toggle_pencil()

    def closeEvent(self, event):
        """Called when the window is closed. Clean up MIDI resources."""
        # Save settings before closing
        self.save_settings()

        if self.midi_timer:
            self.midi_timer.stop()

        if self.device_scan_timer:
            self.device_scan_timer.stop()

        if self.midi_in:
            try:
                self.midi_in.close_port()
            except Exception:
                pass
            del self.midi_in

        if self.midi_scanner:
            del self.midi_scanner

        event.accept()


# ============================================================================
# APPLICATION ENTRY POINT
# ============================================================================

def main():
    """Creates and runs the application."""
    print(f"Piano MIDI Viewer - Version {VERSION}")
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

    # Load UI scale before window creation (scales buttons, margins, cursors)
    global UI_SCALE_FACTOR
    UI_SCALE_FACTOR = load_ui_scale()
    if UI_SCALE_FACTOR != 1.0:
        print(f"UI Scale: {int(UI_SCALE_FACTOR * 100)}%")

    window = PianoMIDIViewer()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
