#!/usr/bin/env python3
"""
A piano keyboard on your screen that lights up when you play.
Made for music teachers, students, and content creators.

Version: see VERSION constant
License: GPL-3.0
"""

# --- Standard library imports ---
import sys
import os
import json
import logging
import configparser
from pathlib import Path
import subprocess
import ssl
from urllib.request import urlopen, Request
from urllib.error import URLError
from datetime import datetime
import webbrowser

# --- Third-party imports ---
import certifi       # Provides CA certificates for HTTPS (needed in PyInstaller builds)
import rtmidi        # MIDI input handling (python-rtmidi)

# --- Logging setup ---
# Outputs to stderr so it doesn't interfere with stdout.
# All modules in this app use `log.info()`, `log.warning()`, `log.error()`, etc.
log = logging.getLogger("piano-midi-viewer")
log.setLevel(logging.DEBUG)
_log_handler = logging.StreamHandler()
_log_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
log.addHandler(_log_handler)

# Collects errors that happen before the main window exists (e.g. settings migration).
# Flushed into an error dialog once the window is ready.
_startup_errors = []

# --- Translation system ---
# Translations are stored in JSON files under translations/ (one per language).
# English is the default and needs no file. The tr() function returns the
# translated string or falls back to the English original.

LANGUAGES = {
    "en": "English",
    "de": "Deutsch",
    "es": "Español",
    "fr": "Français",
    "pl": "Polski",
    "pt": "Português",
    "ru": "Русский",
    "uk": "Українська",
}

_translations = {}
_current_language = "en"

def load_translations(lang_code):
    """Loads translation strings for the given language code."""
    global _translations, _current_language
    _current_language = lang_code
    if lang_code == "en":
        _translations = {}
        return
    translations_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "translations")
    translation_file = os.path.join(translations_dir, f"{lang_code}.json")
    if os.path.exists(translation_file):
        try:
            with open(translation_file, 'r', encoding='utf-8') as f:
                _translations = json.load(f)
            log.info(f"Loaded translations: {lang_code}")
        except Exception as e:
            log.warning(f"Failed to load translations for {lang_code}: {e}")
            _translations = {}
    else:
        log.warning(f"Translation file not found: {translation_file}")
        _translations = {}

def tr(text):
    """Returns the translated string, or the original English text as fallback."""
    if not _translations:
        return text
    return _translations.get(text, text)

# --- PyQt6 imports ---
# QtWidgets: all the visible UI elements (windows, buttons, dropdowns, etc.)
# QtCore:    non-visual essentials (timers, geometry, signals, threads)
# QtGui:     drawing and rendering (painter, colors, fonts, icons, cursors)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QComboBox, QPushButton, QLabel, QDialog,
    QColorDialog, QCheckBox, QFileDialog, QPlainTextEdit
)
from PyQt6.QtCore import Qt, QRectF, QTimer, QByteArray, QThread, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QFontMetrics, QIcon, QPixmap, QFontDatabase, QCursor


# ============================================================================
# CONSTANTS
# ============================================================================
# All sizing in this app is derived from a single white key's width.
# Change INITIAL_KEY_WIDTH and everything else (height, gaps, text, buttons)
# scales proportionally. This makes the layout consistent at any window size.

# --- App version ---
VERSION = "8.6.3"
# Settings file format version. Increment this when the settings.ini format
# changes, and add a corresponding migration step in migrate_settings().
SETTINGS_VERSION = 1

# --- Colors ---
DEFAULT_HIGHLIGHT_COLOR = QColor(80, 148, 212)  # Arch Blue (#5094d4)
BACKGROUND_COLOR = QColor(120, 120, 120)         # Grey canvas behind the keys

# --- MIDI note range ---
# A standard piano spans A0 (MIDI 21) to C8 (MIDI 108).
# The app lets you show any subset of this range.
MIDI_NOTE_MIN = 21   # A0 — lowest note on a standard piano
MIDI_NOTE_MAX = 108  # C8 — highest note on a standard piano

# --- Default visible range (3 octaves around Middle C) ---
DEFAULT_START_NOTE = 48  # C3
DEFAULT_END_NOTE = 83    # B5

# --- Key sizing ---
# The single white key width is the "anchor" for all other dimensions.
INITIAL_KEY_WIDTH = 32  # pixels — tweak this to change the default key size

# Height ratio limits control how tall keys can be relative to their width.
# white_key_height = white_key_width * height_ratio
MIN_HEIGHT_RATIO = 3    # minimum: keys are 3x as tall as wide (squat)
MAX_HEIGHT_RATIO = 6    # maximum: keys are 6x as tall as wide (tall)

# Initial key height starts at the maximum ratio (tallest allowed shape)
INITIAL_KEY_HEIGHT = INITIAL_KEY_WIDTH * MAX_HEIGHT_RATIO  # = 192px

# Smallest key width allowed (prevents keys from becoming unusably tiny)
PRACTICAL_MIN_KEY_WIDTH = 15  # pixels

# --- Visual styling ---
# Gap between white keys — scales with key width, clamped to a sensible range.
# Each side of a key has this gap, so the visible space between two keys is 2x.
KEY_GAP_RATIO = 0.03            # gap = white_key_width * 0.03
KEY_GAP_MIN = 1                 # at least 1px gap per side
KEY_GAP_MAX = 5                 # at most 5px gap per side

# Shadow lines on white keys (subtle 3D effect) are hidden when keys are
# too narrow, because they make small text harder to read.
SHADOW_DISABLE_WIDTH = 25       # disable shadows below this key width (pixels)

# Black keys are sized as a fraction of white keys
BLACK_KEY_HEIGHT_RATIO = 0.6    # black_key_height = keyboard_height * 0.6
BLACK_KEY_WIDTH_RATIO = 0.8     # black_key_width = white_key_width * 0.8

# Rounded corners on each key
KEY_CORNER_RADIUS_RATIO = 0.08  # corner_radius = white_key_width * 0.08
KEY_CORNER_RADIUS_MIN = 4       # minimum corner radius in pixels

# The grey canvas behind the keys has its own margin and rounded corners
KEYBOARD_CANVAS_MARGIN = 4      # pixels of grey border around the keys
KEYBOARD_CANVAS_RADIUS = 6      # corner radius of the grey canvas

# --- Custom cursor sizing and colors (pencil/eraser tool) ---
CURSOR_SIZE = 24                  # pixel size of cursor icon (try 24-40)
CURSOR_OUTLINE_COLOR = '#010101'  # dark outline for both cursors
CURSOR_FILL_COLOR = '#ffffff'     # white fill so cursors are visible on black keys

# --- UI scale ---
# Loaded from settings before the window is created. All button sizes, margins,
# and cursor sizes are multiplied by this factor via the scaled() helper.
UI_SCALE_FACTOR = 1.0  # Set in main() from saved settings

def scaled(px):
    """Multiply a pixel value by the current UI scale factor.

    Used throughout the app to make buttons, margins, and cursors respect
    the user's chosen UI scale (25%-200%).
    """
    return round(px * UI_SCALE_FACTOR)

# --- Button sizing (base values before scaling) ---
BUTTON_SIZE = 36          # width and height of each button (square)
ICON_SIZE_RATIO = 0.9     # icon fills 90% of the button
BUTTON_AREA_WIDTH = 50    # width of the left/right button columns
BUTTON_SPACING = 5        # vertical gap between buttons

# --- Layout margins (base values before scaling) ---
LAYOUT_MARGIN = 5               # padding around the main layout
WINDOW_VERTICAL_MARGIN = 50     # extra vertical space for title bar and padding

# Derived layout helpers — these are functions (not constants) because they
# call scaled(), which depends on UI_SCALE_FACTOR set at runtime.
def total_horizontal_margin():
    """Total horizontal space taken by margins and button columns."""
    return scaled(LAYOUT_MARGIN) * 2 + scaled(BUTTON_AREA_WIDTH) * 2

def min_button_area_height():
    """Minimum height needed to fit 4 buttons stacked vertically."""
    return scaled(BUTTON_SIZE) * 4 + scaled(BUTTON_SPACING) * 3

def min_window_height():
    """Minimum window height so that buttons are never clipped."""
    return min_button_area_height() + scaled(LAYOUT_MARGIN) * 2

# --- MIDI timing ---
MIDI_POLL_INTERVAL = 10          # milliseconds between MIDI message polls (100 Hz)
MIDI_SCAN_INTERVAL = 3000        # milliseconds between device scans (hot-plug detection)
STATUS_MESSAGE_DURATION = 3000   # milliseconds before toast notification auto-hides

# --- Note names for text rendering on keys ---
NOTE_NAMES_WHITE = ['C', 'D', 'E', 'F', 'G', 'A', 'B']
NOTE_NAMES_BLACK_SHARPS = ['C♯', 'D♯', 'F♯', 'G♯', 'A♯']
NOTE_NAMES_BLACK_FLATS = ['D♭', 'E♭', 'G♭', 'A♭', 'B♭']

# --- Text sizing ratios (all relative to key dimensions) ---
WHITE_TEXT_GAP_RATIO = 0.02         # gap between text and key edge = key_height * 0.02
BLACK_TEXT_GAP_RATIO = 0.05         # gap for black keys = key_height * 0.05
WHITE_KEY_TEXT_WIDTH_RATIO = 0.7    # 1 character must fit in key_width * 0.7
BLACK_KEY_TEXT_WIDTH_RATIO = 0.5    # 2 characters must fit in key_width * 0.5
WHITE_KEY_TEXT_AREA_RATIO = 0.4     # bottom 40% of white key is reserved for text
MIN_FONT_SIZE = 6                   # text is hidden entirely below this point size

# The font family name is set in main() after loading JetBrains Mono.
# Falls back to "monospace" if the font file is missing.
LOADED_FONT_FAMILY = None


# ============================================================================
# APP ICONS AND CURSORS
# ============================================================================
# All icons and cursors are generated at runtime from embedded SVG strings.
# This means no external icon files are needed — the app looks the same on
# every platform (Linux, Windows, macOS) without shipping image assets.

def create_piano_icon():
    """Creates the app icon (white piano keys on blue background) from embedded SVG."""
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


# Embedded SVG for pencil cursor and button icon.
# Source: SVG Repo (www.svgrepo.com), CC0 license.
# The SVG has two layers: a white fill path (so the cursor is visible on dark
# keys) and a black detail path drawn on top for the outline.
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

# Embedded SVG for eraser cursor (same two-layer approach as pencil above).
# Source: SVG Repo (www.svgrepo.com), CC0 license.
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


# Camera icon for the "Save as PNG" button.
# Simple camera shape: body rectangle with rounded corners, lens circle, viewfinder bump.
# Two layers: white fill (opaque interior) + black outline (detail).
SAVE_SVG = """<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M2 8.37722C2 8.0269 2 7.85174 2.01462 7.70421C2.1556 6.28127 3.28127 5.1556 4.70421 5.01462C4.85174 5 5.03636 5 5.40558 5C5.54785 5 5.61899 5 5.67939 4.99634C6.45061 4.94963 7.12595 4.46288 7.41414 3.746C7.43671 3.68986 7.45781 3.62657 7.5 3.5C7.54219 3.37343 7.56329 3.31014 7.58586 3.254C7.87405 2.53712 8.54939 2.05037 9.32061 2.00366C9.38101 2 9.44772 2 9.58114 2H14.4189C14.5523 2 14.619 2 14.6794 2.00366C15.4506 2.05037 16.126 2.53712 16.4141 3.254C16.4367 3.31014 16.4578 3.37343 16.5 3.5C16.5422 3.62657 16.5633 3.68986 16.5859 3.746C16.874 4.46288 17.5494 4.94963 18.3206 4.99634C18.381 5 18.4521 5 18.5944 5C18.9636 5 19.1483 5 19.2958 5.01462C20.7187 5.1556 21.8444 6.28127 21.9854 7.70421C22 7.85174 22 8.0269 22 8.37722V16.2C22 17.8802 22 18.7202 21.673 19.362C21.3854 19.9265 20.9265 20.3854 20.362 20.673C19.7202 21 18.8802 21 17.2 21H6.8C5.11984 21 4.27976 21 3.63803 20.673C3.07354 20.3854 2.6146 19.9265 2.32698 19.362C2 18.7202 2 17.8802 2 16.2V8.37722Z" stroke="#000000" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M12 16.5C14.2091 16.5 16 14.7091 16 12.5C16 10.2909 14.2091 8.5 12 8.5C9.79086 8.5 8 10.2909 8 12.5C8 14.7091 9.79086 16.5 12 16.5Z" stroke="#000000" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""


def _render_svg_to_pixmap(svg_data, size):
    """Renders an SVG string to a QPixmap at the given pixel size.

    Injects width/height attributes into the SVG so Qt renders it at the
    exact size we want, regardless of the SVG's original viewBox dimensions.
    """
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


def create_save_icon(size=None, color="#000000"):
    """
    Creates a camera/save QIcon from embedded SVG at the given size and color.

    Used for the "Save as PNG" button that captures the piano keyboard.

    Args:
        size: Icon size in pixels
        color: Hex color for the icon

    Returns:
        QIcon: The camera icon
    """
    if size is None:
        size = scaled(BUTTON_SIZE)
    svg = SAVE_SVG.replace('#000000', color)
    return QIcon(_render_svg_to_pixmap(svg, size))


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
# Standalone utility functions used by the main classes. These handle:
# - Settings file location and migration
# - MIDI note math (which notes are black keys, counting white keys, etc.)
# - Window size calculations
# - Text color contrast and font sizing for note labels
# - Button stylesheet generation

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
    """Loads the UI scale factor from settings file. Called before the window is created.

    This must happen early (before any widgets exist) because the scale factor
    affects button sizes, margins, and cursor dimensions at creation time.
    Returns 1.0 (100%) if no saved setting exists.
    """
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


def load_language_setting():
    """Loads the language setting from config file. Called before window creation."""
    config_path = get_config_path()
    if not config_path.exists():
        return "en"
    config = configparser.ConfigParser()
    try:
        config.read(config_path)
        if config.has_option('appearance', 'language'):
            lang = config.get('appearance', 'language')
            if lang in LANGUAGES:
                return lang
    except Exception:
        pass
    return "en"


def migrate_settings():
    """Migrates settings file to the current SETTINGS_VERSION.

    Called once at startup before load_settings(). Reads the settings_version
    field from [meta], applies any needed migrations sequentially, then writes
    the updated version back. No-op if the file doesn't exist or is already
    at the current version.

    To add a migration:
    1. Increment SETTINGS_VERSION constant
    2. Add an `if old_version < N:` block below with the migration logic
    """
    config_path = get_config_path()
    if not config_path.exists():
        return

    config = configparser.ConfigParser()
    try:
        config.read(config_path)
    except Exception as e:
        log.error(f"Error reading settings for migration: {e}")
        _startup_errors.append(f"Could not read settings file: {e}")
        return

    old_version = 0
    if config.has_option('meta', 'settings_version'):
        try:
            old_version = config.getint('meta', 'settings_version')
        except ValueError:
            old_version = 0

    if old_version >= SETTINGS_VERSION:
        return  # Already up to date

    log.info(f"Migrating settings from version {old_version} to {SETTINGS_VERSION}")

    # --- Add future migrations here ---
    # Example:
    # if old_version < 2:
    #     # Rename a setting, add a new default, etc.
    #     if config.has_option('appearance', 'old_name'):
    #         value = config.get('appearance', 'old_name')
    #         config.set('appearance', 'new_name', value)
    #         config.remove_option('appearance', 'old_name')

    # Stamp the current version
    if not config.has_section('meta'):
        config.add_section('meta')
    config.set('meta', 'settings_version', str(SETTINGS_VERSION))

    try:
        with open(config_path, 'w') as f:
            config.write(f)
        log.info("Settings migration complete")
    except Exception as e:
        log.error(f"Error writing migrated settings: {e}")
        _startup_errors.append(f"Could not save migrated settings: {e}")


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

    Used for velocity visualization — soft notes blend just a little towards the
    highlight color (factor ~0.3), while hard notes blend almost fully (factor ~1.0).

    Args:
        base: QColor to blend from (factor=0.0 gives this color exactly)
        target: QColor to blend towards (factor=1.0 gives this color exactly)
        factor: Blend amount between 0.0 and 1.0

    Returns:
        QColor: The blended result
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
    Generates a QPushButton stylesheet string with scaled border and radius.

    Every button in the app uses this function so they all look consistent.
    The `interactive` flag controls whether hover/pressed/disabled states are
    included — set it to False for indicator-only buttons (like sustain "S")
    that shouldn't change appearance on hover.

    Args:
        bg_color: Background color as a hex string (e.g. "#f5f5f5")
        text_color: Text color as a hex string (e.g. "#2a2a2a")
        interactive: If True, adds hover/pressed/disabled CSS states
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
# The settings dialog lets users configure MIDI devices, highlight color,
# note display options, UI scale, and check for updates. It opens as a
# non-modal window so MIDI input keeps working while settings are open.

class UpdateChecker(QThread):
    """Background thread that checks Codeberg for a newer release.

    Runs an HTTPS request in a separate thread so the UI doesn't freeze.
    Emits a `result` signal with (display_text, url_or_empty) when done.
    """
    result = pyqtSignal(str, str)  # (display_text, url_or_empty)

    def run(self):
        try:
            url = "https://codeberg.org/api/v1/repos/skoomabwoy/piano-midi-viewer/releases/latest"
            req = Request(url, headers={"User-Agent": "PianoMIDIViewer"})
            ctx = ssl.create_default_context(cafile=certifi.where())
            with urlopen(req, timeout=10, context=ctx) as resp:
                data = json.loads(resp.read().decode())
            tag = data.get("tag_name", "")
            latest = tag.lstrip("v")
            if latest and self._is_newer(latest, VERSION):
                self.result.emit(
                    tr("Version {} available").format(latest),
                    "https://codeberg.org/skoomabwoy/piano-midi-viewer/releases"
                )
            else:
                self.result.emit(tr("Up to date"), "")
        except (URLError, OSError, ValueError, KeyError):
            self.result.emit(tr("Check failed"), "")

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
    """Dialog window for app configuration.

    Only one instance can be open at a time (singleton pattern enforced by
    open_settings() in PianoMIDIViewer). The dialog is non-modal, meaning
    MIDI input and the piano display keep working while this is open.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Settings"))
        self.setModal(True)
        self.setMinimumWidth(300)
        self.main_window = parent  # Reference to PianoMIDIViewer for reading/writing settings
        self.init_ui()

    def init_ui(self):
        """Creates all the controls in the settings dialog."""
        layout = QVBoxLayout()
        layout.setSpacing(15)

        # LANGUAGE
        lang_layout = QHBoxLayout()
        lang_label = QLabel(tr("Language"))

        self.lang_dropdown = QComboBox()
        for code, name in LANGUAGES.items():
            self.lang_dropdown.addItem(name, code)
        # Set current value
        lang_index = self.lang_dropdown.findData(_current_language)
        if lang_index >= 0:
            self.lang_dropdown.setCurrentIndex(lang_index)
        self.lang_dropdown.currentIndexChanged.connect(self.language_changed)

        self.lang_restart_button = QPushButton(tr("Restart"))
        self.lang_restart_button.setVisible(False)
        self.lang_restart_button.clicked.connect(self.restart_app)

        lang_layout.addWidget(lang_label)
        lang_layout.addStretch()
        lang_layout.addWidget(self.lang_restart_button)
        lang_layout.addWidget(self.lang_dropdown)
        layout.addLayout(lang_layout)

        # MIDI INPUT
        midi_header = QHBoxLayout()
        midi_label = QLabel(tr("MIDI Input Device:"))
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
        refresh_btn.setToolTip(tr("Refresh MIDI device list"))
        refresh_btn.clicked.connect(self.refresh_midi_devices)

        midi_layout.addWidget(self.midi_dropdown, 1)
        midi_layout.addWidget(refresh_btn)

        layout.addLayout(midi_header)
        layout.addLayout(midi_layout)

        # HIGHLIGHT COLOR
        color_layout = QHBoxLayout()
        color_label = QLabel(tr("Highlight Color"))

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
        scale_label = QLabel(tr("UI Scale"))

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
        self.restart_button = QPushButton(tr("Restart"))
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
        self.octave_numbers_checkbox = QCheckBox(tr("Show Octave Numbers"))
        self.octave_numbers_checkbox.setChecked(self.main_window.show_octave_numbers)
        self.octave_numbers_checkbox.stateChanged.connect(self.toggle_octave_numbers)

        layout.addWidget(self.octave_numbers_checkbox)

        # WHITE KEY NAMES CHECKBOX
        self.white_key_names_checkbox = QCheckBox(tr("Show White Key Names"))
        self.white_key_names_checkbox.setChecked(self.main_window.show_white_key_names)
        self.white_key_names_checkbox.stateChanged.connect(self.toggle_white_key_names)

        layout.addWidget(self.white_key_names_checkbox)

        # BLACK KEY NAMES CHECKBOX
        self.black_key_names_checkbox = QCheckBox(tr("Show Black Key Names"))
        self.black_key_names_checkbox.setChecked(self.main_window.show_black_key_names)
        self.black_key_names_checkbox.stateChanged.connect(self.toggle_black_key_names)

        layout.addWidget(self.black_key_names_checkbox)

        # BLACK KEY NOTATION DROPDOWN
        notation_layout = QHBoxLayout()
        notation_layout.setContentsMargins(20, 0, 0, 0)  # Indent to show it's related to black keys

        self.black_key_notation_dropdown = QComboBox()
        self.black_key_notation_dropdown.addItem(tr("♭ Flats"), "Flats")
        self.black_key_notation_dropdown.addItem(tr("♯ Sharps"), "Sharps")
        self.black_key_notation_dropdown.addItem(tr("Both"), "Both")

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
        self.names_when_pressed_checkbox = QCheckBox(tr("Show note names only when pressed"))
        self.names_when_pressed_checkbox.setChecked(self.main_window.show_names_when_pressed)
        self.names_when_pressed_checkbox.stateChanged.connect(self.toggle_names_when_pressed)
        # Enable only if at least one of white/black key names is on
        names_enabled = self.main_window.show_white_key_names or self.main_window.show_black_key_names
        self.names_when_pressed_checkbox.setEnabled(names_enabled)
        layout.addWidget(self.names_when_pressed_checkbox)

        # SEPARATOR
        layout.addSpacing(10)

        # SHOW VELOCITY CHECKBOX
        self.velocity_checkbox = QCheckBox(tr("Show Velocity"))
        self.velocity_checkbox.setChecked(self.main_window.show_velocity)
        self.velocity_checkbox.stateChanged.connect(self.toggle_velocity)
        layout.addWidget(self.velocity_checkbox)

        # VERSION + CHECK FOR UPDATES
        layout.addStretch()
        version_row = QHBoxLayout()
        self.version_label = QLabel(tr("Version {}").format(VERSION))
        self.version_label.setTextFormat(Qt.TextFormat.RichText)
        self.version_label.linkActivated.connect(self._open_url)
        self.version_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        version_row.addWidget(self.version_label, 1)
        self.update_button = QPushButton(tr("Check for Updates"))
        self.update_button.setFixedWidth(self.update_button.sizeHint().width())
        self.update_button.clicked.connect(self.check_for_updates)
        version_row.addWidget(self.update_button, 0)
        layout.addLayout(version_row)

        # INFO LINK
        info_label = QLabel()
        info_label.setText(f'<a href="https://codeberg.org/skoomabwoy/piano-midi-viewer" style="color: #5094d4;">{tr("Project Info & Source Code")}</a>')
        info_label.linkActivated.connect(self._open_url)
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setTextFormat(Qt.TextFormat.RichText)
        info_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        layout.addWidget(info_label)

        # CLOSE BUTTON
        close_button = QPushButton(tr("Close"))
        close_button.clicked.connect(self.accept)

        layout.addWidget(close_button)
        self.setLayout(layout)

        self.restart_button.setVisible(self.main_window.pending_ui_scale != UI_SCALE_FACTOR)
        self.lang_restart_button.setVisible(self.main_window.pending_language != _current_language)
        self.adjustSize()
        self.setFixedSize(self.size())

    def populate_midi_devices(self):
        """Scans for available MIDI input devices and populates the dropdown.

        Temporarily blocks signals on the dropdown to prevent the
        currentIndexChanged signal from firing during rebuild, which would
        cause an unwanted reconnection attempt for each item added.
        """
        self.midi_dropdown.blockSignals(True)
        self.midi_dropdown.clear()
        devices = self.main_window.get_midi_devices()

        if not devices:
            self.midi_dropdown.addItem(tr("No MIDI devices found"))
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
        if device_name and device_name != tr("No MIDI devices found"):
            if self.main_window.connect_midi_device(device_name):
                self.midi_status.setText("")
            else:
                # Connection failed — show status, revert dropdown, refresh list
                self.midi_status.setText(tr("Device not found"))
                QTimer.singleShot(3000, lambda: self.midi_status.setText(""))
                self.populate_midi_devices()

    def choose_color(self):
        """Opens color picker dialog."""
        color = QColorDialog.getColor(
            self.main_window.piano.highlight_color,
            self,
            tr("Choose Highlight Color")
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

    def language_changed(self, index):
        """Called when user selects a different language."""
        new_lang = self.lang_dropdown.currentData()
        self.lang_restart_button.setVisible(new_lang != _current_language)
        self.main_window.pending_language = new_lang
        self.main_window.save_settings()

    def restart_app(self):
        """Saves settings and restarts the application.

        Spawns a new process and then quits the current one. Handles three cases:
        - AppImage: uses $APPIMAGE path (the .AppImage file itself), because
          sys.executable points inside the mounted squashfs which unmounts on exit.
        - Frozen (PyInstaller) builds: runs the binary directly, and clears
          PyInstaller's temp-directory env vars so the child process doesn't
          try to reuse the parent's extraction folder (which gets deleted on exit).
        - Development (python script): runs via the Python interpreter.
        """
        self.main_window.save_settings()
        kwargs = {"creationflags": subprocess.DETACHED_PROCESS} if sys.platform == "win32" else {"start_new_session": True}
        devnull = subprocess.DEVNULL
        appimage_path = os.environ.get("APPIMAGE")
        if appimage_path:
            # AppImage — restart via the .AppImage file, not the internal binary
            cmd = [appimage_path] + sys.argv[1:]
            kwargs["cwd"] = os.path.dirname(appimage_path)
        elif getattr(sys, "frozen", False):
            # PyInstaller frozen build — run the binary directly
            exe = os.path.abspath(sys.executable)
            cmd = [exe] + sys.argv[1:]
            kwargs["cwd"] = os.path.dirname(exe)
            env = os.environ.copy()
            env.pop("_MEIPASS2", None)
            env.pop("_PYI_ARCHIVE_FILE", None)
            kwargs["env"] = env
        else:
            # Development — run via Python interpreter
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
        """Checks Codeberg for a newer release in a background thread.

        Disables the button while the check is running to prevent duplicate
        requests. The result is handled by _on_update_result().
        """
        self.update_button.setEnabled(False)
        self.update_button.setText(tr("Checking..."))
        self._update_checker = UpdateChecker()
        self._update_checker.result.connect(self._on_update_result)
        self._update_checker.start()

    def _on_update_result(self, text, url):
        """Handles the result from the update checker thread."""
        self.update_button.setEnabled(True)
        self.update_button.setText(tr("Check for Updates"))
        if url:
            self.version_label.setText(f'<a href="{url}" style="color: #5094d4;">{text}</a>')
        else:
            self.version_label.setText(text)
            # Revert to version number after a few seconds
            QTimer.singleShot(STATUS_MESSAGE_DURATION, self._restore_version_label)

    def _restore_version_label(self):
        """Restores the version label to show the version number."""
        self.version_label.setText(tr("Version {}").format(VERSION))

    def _open_url(self, url):
        """Opens a URL in the default browser. On Linux, xdg-open delegates
        to kde-open (KDE) or gio (GNOME), which are Qt/GTK apps themselves.
        AppImage and PyInstaller set environment variables (LD_LIBRARY_PATH,
        QT_PLUGIN_PATH, etc.) that cause these helpers to load incompatible
        bundled libraries and crash. Strip all problematic variables so child
        processes use system libraries."""
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(('LD_', 'QT_', 'QML', 'PYTHON'))
               and k not in ('APPIMAGE', 'APPDIR', 'ARGV0', 'OWD')}
        try:
            subprocess.Popen(['xdg-open', url], env=env)
        except FileNotFoundError:
            webbrowser.open(url)


# ============================================================================
# ERROR DIALOG
# ============================================================================
# A simple dialog that appears when something goes wrong. Shows the error
# details with a "Copy to Clipboard" button so users can easily paste the
# info into a bug report or message.

class ErrorDialog(QDialog):
    """Dialog for displaying errors with copy-to-clipboard support.

    Shows error details in a readable format with app version and timestamp.
    The "Copy to Clipboard" button lets users easily share error info when
    reporting issues.
    """

    def __init__(self, title, details, parent=None, reset_callback=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(450)
        self.setMinimumHeight(250)
        self.reset_callback = reset_callback

        layout = QVBoxLayout()
        layout.setSpacing(10)

        # Header
        header = QLabel(tr("Something went wrong. You can copy the details "
                        "below and report this issue."))
        header.setWordWrap(True)
        layout.addWidget(header)

        # Build error report text
        report_lines = [
            f"Piano MIDI Viewer v{VERSION}",
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"",
            f"Error: {details}",
        ]
        self.report_text = "\n".join(report_lines)

        # Read-only text area with the error details
        self.text_area = QPlainTextEdit()
        self.text_area.setPlainText(self.report_text)
        self.text_area.setReadOnly(True)
        self.text_area.setFont(QFont("monospace", 10))
        layout.addWidget(self.text_area)

        # Button row
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        if reset_callback:
            reset_btn = QPushButton(tr("Reset Settings"))
            reset_btn.setFixedHeight(32)
            reset_btn.setStyleSheet(make_button_style())
            reset_btn.clicked.connect(self._reset_settings)
            button_layout.addWidget(reset_btn)

        self.copy_btn = QPushButton(tr("Copy to Clipboard"))
        self.copy_btn.setFixedHeight(32)
        self.copy_btn.setStyleSheet(make_button_style())
        self.copy_btn.clicked.connect(self._copy_to_clipboard)

        close_btn = QPushButton(tr("Close"))
        close_btn.setFixedHeight(32)
        close_btn.setStyleSheet(make_button_style())
        close_btn.clicked.connect(self.close)

        button_layout.addWidget(self.copy_btn)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def _copy_to_clipboard(self):
        """Copies the error report text to the system clipboard."""
        QApplication.clipboard().setText(self.report_text)
        self.copy_btn.setText(tr("Copied!"))
        QTimer.singleShot(1500, lambda: self.copy_btn.setText(tr("Copy to Clipboard")))

    def _reset_settings(self):
        """Deletes the settings file and closes the dialog."""
        if self.reset_callback:
            self.reset_callback()
        self.close()


# ============================================================================
# PIANO KEYBOARD WIDGET
# ============================================================================
# This is the visual heart of the app — a custom-drawn piano keyboard that
# responds to MIDI input, mouse clicks, and the pencil drawing tool.
# All rendering happens in paintEvent() using Qt's QPainter.

class PianoKeyboard(QWidget):
    """Custom widget that draws and manages a piano keyboard.

    This widget handles:
    - Drawing white and black keys with proper proportions
    - Highlighting keys that are currently pressed (via MIDI or mouse)
    - Rendering note names and octave numbers on keys
    - Mouse interaction (click, drag/glissando, pencil tool)
    - Velocity-based brightness when that setting is enabled
    """

    def __init__(self):
        super().__init__()
        # Prevent the right-click context menu from appearing (right-click
        # is used for erasing in pencil mode instead).
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)

        # --- MIDI note range (which notes are visible on screen) ---
        self.start_note = DEFAULT_START_NOTE  # leftmost note (default: C3)
        self.end_note = DEFAULT_END_NOTE      # rightmost note (default: B5)

        # --- Note tracking ---
        # These collections track which notes are currently highlighted.
        # active_notes is a dict because we need to store velocity for each note.
        # The left/right sets track out-of-range notes (used for + button glow).
        self.active_notes = {}              # {MIDI note: velocity} for pressed notes in visible range
        self.active_notes_left = set()      # MIDI notes pressed below visible range
        self.active_notes_right = set()     # MIDI notes pressed above visible range

        # Drawn notes are separate from playing — these are marks left by the
        # pencil tool and persist until the user erases them or exits pencil mode.
        self.drawn_notes = set()

        # --- Mouse interaction state ---
        self.mouse_held_note = None   # MIDI note currently under the mouse cursor (or None)
        self._drag_button = None      # which mouse button started the current drag
        self.glissando_mode = None    # 'on' (painting) or 'off' (erasing), set at mouse press

        # --- Visual appearance ---
        self.highlight_color = DEFAULT_HIGHLIGHT_COLOR
        # These flags tell the main window to light up the + buttons when
        # notes are being played outside the visible range.
        self.glow_left_plus = False
        self.glow_right_plus = False

    def paintEvent(self, event):
        """Draws the entire piano keyboard from scratch.

        Qt calls this method every time the widget needs to be repainted
        (e.g., after a note is pressed or released). The drawing order is:
        1. Grey rounded background canvas
        2. White keys (full height of the keyboard)
        3. Black keys (drawn on top, covering the upper portion of white keys)
        4. Note names and octave numbers (text rendered last, on top of keys)
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()

        # Draw grey rounded canvas (the background behind all keys)
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
        """Draws a single white key (rectangle with optional highlight and shadow)."""
        white_index = get_white_key_index(midi_note, self.start_note)
        x = x_offset + (white_index * key_width)

        # Calculate dynamic gap based on key width (3%, clamped 1-5px per side)
        key_gap = min(KEY_GAP_MAX, max(KEY_GAP_MIN, round(key_width * KEY_GAP_RATIO)))

        rect_x = x + key_gap
        rect_y = y_offset
        rect_width = key_width - key_gap * 2
        rect_height = height

        # A key is highlighted if it's being pressed via MIDI, marked by the
        # pencil tool, or currently under the mouse cursor (during a draw drag).
        # The glissando_mode != 'off' check prevents keys from highlighting
        # while the user is erasing with right-click.
        is_highlighted = (midi_note in self.active_notes or
                         midi_note in self.drawn_notes or
                         (midi_note == self.mouse_held_note and self.glissando_mode != 'off'))

        # Choose the fill color: highlighted keys use the highlight color,
        # optionally blended with the base color for velocity visualization.
        base_color = QColor(252, 252, 252)  # off-white
        if is_highlighted:
            if show_velocity and midi_note in self.active_notes:
                # Velocity blending: soft notes (low velocity) are faintly colored,
                # hard notes (high velocity) are fully colored. The 0.3 minimum
                # ensures even the softest notes are always visible.
                velocity = self.active_notes[midi_note]
                factor = 0.3 + 0.7 * (velocity / 127.0)
                fill_color = blend_colors(base_color, self.highlight_color, factor)
            else:
                fill_color = self.highlight_color
        else:
            fill_color = base_color

        # Draw the key body (filled rounded rectangle)
        painter.setBrush(QBrush(fill_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(
            QRectF(rect_x, rect_y, rect_width, rect_height),
            corner_radius, corner_radius
        )

        # Draw subtle shadow lines on the bottom and right edges for a 3D effect.
        # Only on non-highlighted keys, and only when keys are wide enough that
        # the shadows don't interfere with text readability.
        if not is_highlighted and key_width >= SHADOW_DISABLE_WIDTH:
            shadow_color = QColor(170, 170, 170)
            painter.setPen(QPen(shadow_color, 1))
            # Bottom edge shadow
            painter.drawLine(
                int(rect_x + corner_radius), int(rect_y + rect_height - 1),
                int(rect_x + rect_width - corner_radius), int(rect_y + rect_height - 1)
            )
            # Right edge shadow
            painter.drawLine(
                int(rect_x + rect_width - 1), int(rect_y + corner_radius),
                int(rect_x + rect_width - 1), int(rect_y + rect_height - corner_radius)
            )

        # Draw the key border (darker when highlighted so the key stands out)
        border_color = QColor(25, 25, 25) if is_highlighted else QColor(85, 85, 85)
        painter.setPen(QPen(border_color, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(
            QRectF(rect_x, rect_y, rect_width, rect_height),
            corner_radius, corner_radius
        )

    def _draw_black_key(self, painter, midi_note, white_key_width,
                        black_key_width, x_offset, y_offset, black_key_height, corner_radius, show_velocity=False):
        """Draws a single black key (positioned between two white keys)."""
        # Black keys are centered on the boundary between two adjacent white keys.
        # Find the white key to the left, then position the black key so its
        # center sits on the right edge of that white key.
        left_white_note = get_left_white_key(midi_note, self.start_note)
        white_index = get_white_key_index(left_white_note, self.start_note)

        x = x_offset + ((white_index + 1) * white_key_width - black_key_width / 2)

        rect_x = x
        rect_y = y_offset
        rect_width = black_key_width
        rect_height = black_key_height

        # Same highlight logic as white keys (see _draw_white_key for details)
        is_highlighted = (midi_note in self.active_notes or
                         midi_note in self.drawn_notes or
                         (midi_note == self.mouse_held_note and self.glissando_mode != 'off'))

        base_color = QColor(16, 16, 16)  # near-black
        if is_highlighted:
            if show_velocity and midi_note in self.active_notes:
                velocity = self.active_notes[midi_note]
                factor = 0.3 + 0.7 * (velocity / 127.0)
                fill_color = blend_colors(base_color, self.highlight_color, factor)
            else:
                fill_color = self.highlight_color
        else:
            fill_color = base_color

        # Draw the key body
        painter.setBrush(QBrush(fill_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(
            QRectF(rect_x, rect_y, rect_width, rect_height),
            corner_radius, corner_radius
        )

        # Draw black border (always black, regardless of highlight state)
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
        """Walks up the widget tree to find the PianoMIDIViewer main window.

        The piano widget is nested inside layouts, so self.parent() isn't
        necessarily the main window — we have to traverse upward until we
        find it. Returns None if no PianoMIDIViewer ancestor exists.
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
        """Handle mouse button release. Clears highlight (playing) or restores cursor (pencil)."""
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
# The main window ties everything together: it owns the piano widget, manages
# MIDI connections, handles octave range changes, and coordinates settings.
# The three-column layout is: [pencil/+/-] | [piano keyboard] | [settings/S/+/-]

class PianoMIDIViewer(QMainWindow):
    """Main application window — manages MIDI, UI layout, and app state."""

    def __init__(self):
        super().__init__()

        self._in_resize_event = False  # Prevents recursive resize loops

        # --- MIDI connection state ---
        self.midi_in = None             # Active MidiIn connection (or None if disconnected)
        self.midi_scanner = None        # Persistent MidiIn used only for listing ports (never opens a port)
        self.current_midi_device = None # Name of the connected device (kept for auto-reconnect)
        self.midi_timer = None          # QTimer for polling MIDI messages every 10ms
        self.known_midi_devices = []    # Last-seen device list (for hot-plug detection)
        self.device_scan_timer = None   # QTimer for scanning device changes every 3s
        self.status_hide_timer = None   # QTimer for auto-hiding toast notifications

        # --- Sustain pedal state ---
        # Tracked purely to light up the "S" indicator button.
        # Does not affect note highlighting (notes go dark on release regardless).
        self.sustain_pedal_active = False

        # --- Pencil tool state ---
        # When active, MIDI notes toggle drawn_notes instead of active_notes,
        # and the cursor changes to a pencil/eraser icon.
        self.pencil_active = False

        # --- Note display settings (all saved to settings.ini) ---
        self.show_octave_numbers = True       # show "3", "4", "5" on C keys
        self.show_white_key_names = True      # show "C", "D", "E" etc. on white keys
        self.show_black_key_names = False     # show accidental names on black keys
        self.black_key_notation = "Flats"     # "Flats", "Sharps", or "Both"
        self.show_names_when_pressed = False  # only show names on highlighted keys
        self.show_velocity = False            # brightness reflects how hard each key is pressed

        # --- UI scale ---
        # The current scale is applied at startup. If the user changes it in
        # settings, the new value is saved here for the NEXT launch (requires restart).
        self.pending_ui_scale = UI_SCALE_FACTOR
        self.pending_language = _current_language

        self.init_ui()
        self.setup_midi_polling()
        self.setup_device_scanning()

        # If migration already failed (file is corrupt), skip loading —
        # the startup error dialog will offer reset instead.
        if not _startup_errors:
            self.load_settings()

        # Show any errors that occurred during startup (before the window existed)
        if _startup_errors:
            errors = "\n".join(_startup_errors)
            QTimer.singleShot(0, lambda: self.show_error_dialog(
                tr("Startup Error"),
                tr("Errors occurred during startup:\n\n{}").format(errors),
                offer_reset=True))
            _startup_errors.clear()

    def init_ui(self):
        """Sets up the user interface (three-column layout with piano in center)."""
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
        self.pencil_button.setToolTip(tr("Pencil tool — left click to mark, right click to erase\nPress Esc to exit"))
        self.pencil_button.setFixedSize(btn_sz, btn_sz)
        self.pencil_button.setIcon(create_pencil_icon())
        self.pencil_button.setIconSize(self.pencil_button.size() * 0.7)
        self.pencil_button.setStyleSheet(button_style)
        self.pencil_button.clicked.connect(self.toggle_pencil)

        left_layout.addWidget(self.pencil_button, alignment=Qt.AlignmentFlag.AlignCenter)

        # Save as PNG button: left-click opens file dialog, right-click quick saves
        self.save_button = QPushButton()
        self.save_button.setToolTip(tr("Save keyboard as image\nRight-click to quick save"))
        self.save_button.setFixedSize(btn_sz, btn_sz)
        self.save_button.setIcon(create_save_icon())
        self.save_button.setIconSize(self.save_button.size() * 0.7)
        self.save_button.setStyleSheet(button_style)
        self.save_button.clicked.connect(self.save_keyboard_image)
        self.save_button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.save_button.customContextMenuRequested.connect(self.quick_save_keyboard_image)

        left_layout.addWidget(self.save_button, alignment=Qt.AlignmentFlag.AlignCenter)
        left_layout.addStretch()

        self.left_plus_btn = QPushButton("+")
        self.left_plus_btn.setToolTip(tr("Add octave on the left (lower notes)"))
        self.left_plus_btn.setFixedSize(btn_sz, btn_sz)
        self.left_plus_btn.setFont(button_font)
        self.left_plus_btn.setStyleSheet(button_style)
        self.left_plus_btn.clicked.connect(self.add_octave_left)

        # Using the proper minus sign (−) instead of hyphen (-) because it
        # centers vertically much better in JetBrains Mono.
        self.left_minus_btn = QPushButton("−")
        self.left_minus_btn.setToolTip(tr("Remove octave on the left (lower notes)"))
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
        self.settings_button.setToolTip(tr("Open Settings"))
        self.settings_button.setFixedSize(btn_sz, btn_sz)
        self.settings_button.setIcon(create_settings_icon(btn_sz, "#000000"))
        self.settings_button.setIconSize(self.settings_button.size() * 0.7)
        self.settings_button.setStyleSheet(button_style)
        self.settings_button.clicked.connect(self.open_settings)

        # Sustain button: indicator only (lights up when sustain pedal is held)
        self.sustain_button = QPushButton("S")
        self.sustain_button.setToolTip(tr("Sustain pedal indicator — lights up when your sustain pedal is held"))
        self.sustain_button.setFixedSize(btn_sz, btn_sz)
        self.sustain_button.setFont(button_font)
        self.sustain_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        right_layout.addWidget(self.settings_button, alignment=Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(self.sustain_button, alignment=Qt.AlignmentFlag.AlignCenter)
        right_layout.addStretch()

        self.right_plus_btn = QPushButton("+")
        self.right_plus_btn.setToolTip(tr("Add octave on the right (higher notes)"))
        self.right_plus_btn.setFixedSize(btn_sz, btn_sz)
        self.right_plus_btn.setFont(button_font)
        self.right_plus_btn.setStyleSheet(button_style)
        self.right_plus_btn.clicked.connect(self.add_octave_right)

        # Same minus sign as left side (see comment there)
        self.right_minus_btn = QPushButton("−")
        self.right_minus_btn.setToolTip(tr("Remove octave on the right (higher notes)"))
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
        """Opens the settings dialog. Only one instance can be open at a time.

        If the dialog is already visible, just bring it to the front instead of
        creating a second one. The dialog is non-modal so MIDI keeps working.
        """
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
        Each setting is loaded independently so one bad value doesn't
        prevent loading the rest. Bad values are reset to defaults and
        the user is notified via a toast message.
        """
        config_path = get_config_path()
        config = configparser.ConfigParser()

        if not config_path.exists():
            return  # No saved settings yet, use defaults

        try:
            config.read(config_path)
        except Exception as e:
            log.error(f"Error reading settings file: {e}")
            error_msg = tr("Could not read settings file: {}\n\nDefault settings will be used.").format(e)
            QTimer.singleShot(0, lambda: self.show_error_dialog(
                tr("Settings Error"), error_msg, offer_reset=True))
            return

        reset_keys = []  # Track which settings had bad values

        # Load MIDI device
        if config.has_option('midi', 'device'):
            device_name = config.get('midi', 'device')
            if device_name:  # Only connect if not empty
                self.connect_midi_device(device_name)

        # Load highlight color
        if config.has_option('appearance', 'highlight_color'):
            color_hex = config.get('appearance', 'highlight_color')
            color = QColor(color_hex)
            if color.isValid():
                self.piano.highlight_color = color
                self.piano.update()
            else:
                reset_keys.append('highlight_color')

        # Load note name and octave number settings
        for key, attr in [
            ('show_octave_numbers', 'show_octave_numbers'),
            ('show_white_key_names', 'show_white_key_names'),
            ('show_black_key_names', 'show_black_key_names'),
            ('show_names_when_pressed', 'show_names_when_pressed'),
            ('show_velocity', 'show_velocity'),
        ]:
            if config.has_option('appearance', key):
                try:
                    setattr(self, attr, config.getboolean('appearance', key))
                except ValueError:
                    reset_keys.append(key)

        if config.has_option('appearance', 'black_key_notation'):
            notation = config.get('appearance', 'black_key_notation')
            if notation in ['Flats', 'Sharps', 'Both']:
                self.black_key_notation = notation
            else:
                reset_keys.append('black_key_notation')

        # Load keyboard range (must be before geometry restoration)
        if config.has_option('keyboard', 'start_note') and config.has_option('keyboard', 'end_note'):
            try:
                start_note = config.getint('keyboard', 'start_note')
                end_note = config.getint('keyboard', 'end_note')
                if (MIDI_NOTE_MIN <= start_note <= MIDI_NOTE_MAX and
                    MIDI_NOTE_MIN <= end_note <= MIDI_NOTE_MAX and
                    end_note >= start_note + 11):  # At least 1 octave
                    self.piano.start_note = start_note
                    self.piano.end_note = end_note
                    self.update_button_states()
                    self.update_minimum_size()
                else:
                    reset_keys.append('start_note/end_note')
            except ValueError:
                reset_keys.append('start_note/end_note')

        # Load window geometry (size and position)
        if config.has_option('window', 'geometry'):
            geometry_string = config.get('window', 'geometry')
            geometry_bytes = QByteArray.fromBase64(geometry_string.encode())
            self.restoreGeometry(geometry_bytes)

        # If any values were bad, notify the user and save cleaned config
        if reset_keys:
            names = ", ".join(reset_keys)
            log.warning(f"Reset invalid settings to defaults: {names}")
            QTimer.singleShot(0, lambda: self.show_status_message(
                tr("Reset invalid settings: {}").format(names)))
            QTimer.singleShot(100, lambda: self.save_settings())

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
            'ui_scale': str(self.pending_ui_scale),
            'language': self.pending_language
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

        # Settings format version (used by migrate_settings on startup)
        config['meta'] = {
            'settings_version': str(SETTINGS_VERSION)
        }

        try:
            with open(config_path, 'w') as f:
                config.write(f)
        except Exception as e:
            log.error(f"Error saving settings: {e}")
            self.show_error_dialog(
                tr("Settings Error"),
                tr("Could not save settings: {}\n\nYour changes may be lost.").format(e),
                offer_reset=True)

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

    def save_keyboard_image(self):
        """Opens a file dialog to save the piano keyboard as a PNG image."""
        filename, _ = QFileDialog.getSaveFileName(
            self, tr("Save Keyboard Image"),
            os.path.join(os.path.expanduser("~"), "piano_keyboard.png"),
            tr("PNG Image (*.png)")
        )
        if filename:
            if not filename.lower().endswith('.png'):
                filename += '.png'
            pixmap = self.piano.grab()
            pixmap.save(filename, "PNG")
            self.show_status_message(tr("Saved to {}").format(os.path.basename(filename)))

    def quick_save_keyboard_image(self):
        """Quick-saves the piano keyboard as PNG to ~/Pictures with a timestamp."""
        save_dir = os.path.join(os.path.expanduser("~"), "Pictures", "PianoMIDIViewer")
        os.makedirs(save_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(save_dir, f"piano_{timestamp}.png")
        pixmap = self.piano.grab()
        pixmap.save(filename, "PNG")
        self.show_status_message(tr("Saved to {}").format(os.path.basename(filename)))

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
        """Calculates current white key width and height from the piano widget size.

        Used when adding/removing octaves to maintain consistent key proportions.
        """
        num_white_keys = count_white_keys(self.piano.start_note, self.piano.end_note)
        if num_white_keys == 0:
            return None, None

        piano_width = self.piano.width()
        piano_height = self.piano.height()

        key_width = piano_width / num_white_keys
        key_height = piano_height - (KEYBOARD_CANVAS_MARGIN * 2)

        return key_width, key_height

    # --- MIDI FUNCTIONALITY ---
    # Uses a polling approach (QTimer every 10ms) rather than callbacks.
    # A persistent scanner instance is reused for port listing to avoid
    # leaking ALSA sequencer handles (each rtmidi.MidiIn() opens a new one).

    def get_midi_devices(self):
        """Returns list of available MIDI input device names.

        Uses a persistent MidiIn scanner instance to avoid leaking ALSA
        sequencer handles (creating a temporary MidiIn for each scan would
        leak one handle per call).
        """
        try:
            if not self.midi_scanner:
                self.midi_scanner = rtmidi.MidiIn()
            return self.midi_scanner.get_ports()
        except Exception as e:
            log.error(f"Error scanning MIDI devices: {e}")
            self.show_error_dialog(
                tr("MIDI Error"), tr("Could not scan for MIDI devices: {}").format(e))
            return []

    def connect_midi_device(self, device_name):
        """Connects to the specified MIDI input device.

        Uses a "connect-before-disconnect" approach: opens the new connection
        first, and only closes the old one after success. This way, a failed
        connection attempt doesn't leave the app disconnected.

        Returns True on success, False on failure.
        """
        # Check availability using the persistent scanner
        ports = self.get_midi_devices()
        if device_name not in ports:
            log.warning(f"Device not found: {device_name}")
            self.show_status_message(tr("Not found: {}").format(device_name))
            return False

        try:
            new_midi_in = rtmidi.MidiIn()
            port_index = ports.index(device_name)
            new_midi_in.open_port(port_index)
        except Exception as e:
            log.error(f"Error connecting to MIDI device: {e}")
            self.show_status_message(tr("Connection failed: {}").format(device_name))
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
        log.info(f"Connected to MIDI device: {device_name}")
        self.show_status_message(tr("Connected: {}").format(device_name))
        self.save_settings()
        return True

    def setup_midi_polling(self):
        """Sets up a timer to poll for MIDI messages."""
        self.midi_timer = QTimer()
        self.midi_timer.timeout.connect(self.poll_midi_messages)
        self.midi_timer.start(MIDI_POLL_INTERVAL)

    def setup_device_scanning(self):
        """Sets up a timer to periodically scan for MIDI device changes (hot-plug detection).

        Takes a snapshot of currently connected ports so the first scan doesn't
        falsely report existing devices as newly appeared.
        """
        self.known_midi_devices = self.get_midi_devices()
        self.device_scan_timer = QTimer()
        self.device_scan_timer.timeout.connect(self.scan_midi_devices)
        self.device_scan_timer.start(MIDI_SCAN_INTERVAL)

    def scan_midi_devices(self):
        """Checks for MIDI device changes (called every 3 seconds by device_scan_timer).

        Compares the current port list against the last-known list to detect
        newly appeared or disappeared devices. Handles auto-reconnect when a
        previously used device reappears.
        """
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
        """Handles a MIDI device disconnection gracefully.

        Cleans up the MIDI connection, clears all lit keys and button glows,
        resets the sustain indicator, and shows a toast notification.
        Keeps current_midi_device set so scan_midi_devices() can auto-reconnect
        if the device reappears later.
        """
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
        self.show_status_message(tr("Disconnected: {}").format(device_name))

    def show_status_message(self, text):
        """Shows a temporary toast notification centered near the bottom of the piano.

        The notification auto-hides after STATUS_MESSAGE_DURATION milliseconds.
        Font size scales with key width so the toast looks proportional at any zoom.
        """
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

    def show_error_dialog(self, title, details, offer_reset=False):
        """Shows an error dialog with copy-to-clipboard support.

        The error is also logged via the logging module. The dialog is modal
        so the user must acknowledge it before continuing.
        If offer_reset is True, a "Reset Settings" button is shown.
        """
        reset_cb = self._reset_settings_file if offer_reset else None
        dialog = ErrorDialog(title, str(details), parent=self, reset_callback=reset_cb)
        dialog.exec()

    def _reset_settings_file(self):
        """Deletes the settings file and shows a confirmation toast."""
        config_path = get_config_path()
        try:
            if config_path.exists():
                config_path.unlink()
            self.show_status_message(tr("Settings reset — restart to apply"))
        except Exception as e:
            log.error(f"Error resetting settings: {e}")

    def poll_midi_messages(self):
        """Checks for new MIDI messages and processes them.

        Called every 10ms (100 Hz) by midi_timer. Drains all pending messages
        in a loop, since multiple notes can arrive between polls. If an
        exception occurs (e.g., the device was unplugged), triggers disconnect.
        """
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
            log.error(f"Error polling MIDI: {e}")
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
        """Applies or removes a highlight glow on a + button.

        Used to indicate that notes are being played outside the visible
        range — the + button on that side lights up in the highlight color
        to signal the user can expand the range. Text color automatically
        adapts (black on light highlights, white on dark) for readability.
        """
        if glow:
            bg_color = self.piano.highlight_color.name()
            text_color = get_text_color_for_highlight(self.piano.highlight_color).name()
            button.setStyleSheet(make_button_style(bg_color=bg_color, text_color=text_color, interactive=False))
        else:
            button.setStyleSheet(make_button_style())

    # --- OCTAVE MANAGEMENT ---
    # Each method: gets the current key width, updates the note range, adjusts
    # the window width to maintain key proportions, and updates button states.

    def add_octave_left(self):
        """Extends the keyboard range by one octave on the left (lower notes)."""
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
        """Updates the enabled/disabled state of octave +/- buttons.

        + buttons are disabled when the range already reaches the MIDI limit.
        - buttons are disabled when only 1 octave remains (minimum range).
        """
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

    # --- WINDOW MANAGEMENT ---

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
        """Handle keyboard shortcuts.

        Esc: exit pencil tool (only when active)
        P:   toggle pencil tool on/off (only when no modifier keys are held,
             to avoid conflicts with Ctrl+P, Alt+P, etc.)
        """
        if event.key() == Qt.Key.Key_Escape and self.pencil_active:
            self.toggle_pencil()
        elif event.key() == Qt.Key.Key_P and not event.modifiers():
            self.toggle_pencil()

    def closeEvent(self, event):
        """Called when the window is closed. Saves settings and frees MIDI resources.

        Stops all timers, closes the active MIDI port, and deletes both the
        connection and scanner MidiIn objects. The `del` calls are important
        because they release the underlying ALSA sequencer handles — Python's
        garbage collector doesn't guarantee timely cleanup.
        """
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
    """Creates and runs the application.

    Startup sequence:
    1. Log startup info
    2. Migrate settings file (if format has changed since last run)
    3. Set up Qt high-DPI support
    4. Create the QApplication
    5. Load the embedded font (JetBrains Mono for note labels and buttons)
    6. Load UI scale from settings (must happen before any widgets are created)
    7. Create and show the main window
    8. Enter Qt's event loop (blocks until the window is closed)
    """
    log.info(f"Piano MIDI Viewer - Version {VERSION}")
    log.info(f"Initial key size: {INITIAL_KEY_WIDTH}px × {INITIAL_KEY_HEIGHT}px")
    log.info(f"Height ratio limits: {MIN_HEIGHT_RATIO}× to {MAX_HEIGHT_RATIO}× (height/width)")

    # Migrate settings file to the current format before anything reads it
    migrate_settings()

    # Allow fractional scale factors on high-DPI displays (e.g., 125%, 150%)
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setWindowIcon(create_piano_icon())

    # Load JetBrains Mono font for note names, octave numbers, and button labels.
    # The font file is bundled alongside the script (and inside PyInstaller builds).
    # Falls back to the system's default monospace font if loading fails.
    global LOADED_FONT_FAMILY
    font_path = os.path.join(os.path.dirname(__file__), "assets", "JetBrainsMono-Regular.ttf")
    if os.path.exists(font_path):
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id != -1:
            font_families = QFontDatabase.applicationFontFamilies(font_id)
            if font_families:
                LOADED_FONT_FAMILY = font_families[0]
                log.info(f"Loaded font: {LOADED_FONT_FAMILY}")
            else:
                log.warning("Font loaded but no families found")
                LOADED_FONT_FAMILY = "monospace"
        else:
            log.warning(f"Failed to load font from {font_path}")
            LOADED_FONT_FAMILY = "monospace"
    else:
        log.warning(f"Font file not found: {font_path}")
        LOADED_FONT_FAMILY = "monospace"

    # Load UI scale before the window is created, since button sizes, margins,
    # and cursor dimensions are calculated at widget creation time.
    global UI_SCALE_FACTOR
    UI_SCALE_FACTOR = load_ui_scale()
    if UI_SCALE_FACTOR != 1.0:
        log.info(f"UI Scale: {int(UI_SCALE_FACTOR * 100)}%")

    # Load language before the window is created, since all UI strings
    # are set during init via tr() calls.
    lang = load_language_setting()
    load_translations(lang)

    window = PianoMIDIViewer()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
