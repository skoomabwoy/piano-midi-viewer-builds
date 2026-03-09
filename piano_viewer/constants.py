"""All sizing constants, colors, MIDI ranges, and layout helpers.

Everything in the app derives from a single white key's width.
Change INITIAL_KEY_WIDTH and everything else scales proportionally.
"""

from PyQt6.QtGui import QColor

# --- Colors ---
DEFAULT_HIGHLIGHT_COLOR = QColor(80, 148, 212)  # Arch Blue (#5094d4)
BACKGROUND_COLOR = QColor(120, 120, 120)         # Grey canvas behind the keys

# --- MIDI note range ---
# A standard piano spans A0 (MIDI 21) to C8 (MIDI 108).
MIDI_NOTE_MIN = 21   # A0
MIDI_NOTE_MAX = 108  # C8

# --- Default visible range (3 octaves around Middle C) ---
DEFAULT_START_NOTE = 48  # C3
DEFAULT_END_NOTE = 83    # B5

# --- Key sizing ---
INITIAL_KEY_WIDTH = 32  # pixels — the anchor for all dimensions

# Height ratio limits: white_key_height = white_key_width * height_ratio
MIN_HEIGHT_RATIO = 3    # squat
MAX_HEIGHT_RATIO = 6    # tall

INITIAL_KEY_HEIGHT = INITIAL_KEY_WIDTH * MAX_HEIGHT_RATIO  # pixels

PRACTICAL_MIN_KEY_WIDTH = 15  # pixels

# --- Visual styling ---
KEY_GAP_RATIO = 0.03
KEY_GAP_MIN = 1
KEY_GAP_MAX = 5

SHADOW_DISABLE_WIDTH = 25  # disable shadows below this key width

BLACK_KEY_HEIGHT_RATIO = 0.6
BLACK_KEY_WIDTH_RATIO = 0.8

KEY_CORNER_RADIUS_RATIO = 0.08
KEY_CORNER_RADIUS_MIN = 4

KEYBOARD_CANVAS_MARGIN = 4
KEYBOARD_CANVAS_RADIUS = 6

# --- Custom cursor sizing and colors (pencil/eraser tool) ---
CURSOR_SIZE = 24
CURSOR_OUTLINE_COLOR = '#010101'
CURSOR_FILL_COLOR = '#ffffff'

# --- UI scale ---
# Set in main() from saved settings before the window is created.
# Mutable: other modules should access via `constants.UI_SCALE_FACTOR`,
# not `from constants import UI_SCALE_FACTOR`.
UI_SCALE_FACTOR = 1.0


def scaled(px):
    """Multiply a pixel value by the current UI scale factor."""
    return round(px * UI_SCALE_FACTOR)


# --- Button sizing (base values before scaling) ---
BUTTON_SIZE = 36
ICON_SIZE_RATIO = 0.9
BUTTON_AREA_WIDTH = 50
BUTTON_SPACING = 5

# --- Layout margins (base values before scaling) ---
LAYOUT_MARGIN = 5
WINDOW_VERTICAL_MARGIN = 50


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
MIDI_POLL_INTERVAL = 10
MIDI_SCAN_INTERVAL = 3000
STATUS_MESSAGE_DURATION = 3000

# --- Note names for text rendering on keys ---
NOTE_NAMES_WHITE = ['C', 'D', 'E', 'F', 'G', 'A', 'B']
NOTE_NAMES_BLACK_SHARPS = ['C♯', 'D♯', 'F♯', 'G♯', 'A♯']
NOTE_NAMES_BLACK_FLATS = ['D♭', 'E♭', 'G♭', 'A♭', 'B♭']

# --- Text sizing ratios (all relative to key dimensions) ---
WHITE_TEXT_GAP_RATIO = 0.02
BLACK_TEXT_GAP_RATIO = 0.05
WHITE_KEY_TEXT_WIDTH_RATIO = 0.7
BLACK_KEY_TEXT_WIDTH_RATIO = 0.5
WHITE_KEY_TEXT_AREA_RATIO = 0.4
MIN_FONT_SIZE = 6

# Font family name — set in main() after loading JetBrains Mono.
# Mutable: other modules should access via `constants.LOADED_FONT_FAMILY`.
LOADED_FONT_FAMILY = None

# --- Loudness compensation ---
LOUDNESS_MULT_LOW = 2.0    # multiplier for A0 (MIDI 21)
LOUDNESS_MULT_HIGH = 0.2   # multiplier for C8 (MIDI 108)
