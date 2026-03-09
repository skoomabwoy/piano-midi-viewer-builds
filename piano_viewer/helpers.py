"""Utility functions — config management, MIDI math, colors, fonts, button styles.

All functions are pure logic with no GUI state. Some use Qt types (QColor,
QFont) for color math and font measurement, but none create or modify widgets.
"""

import sys
import os
import configparser
from pathlib import Path

from PyQt6.QtGui import QColor, QFont, QFontMetrics

from piano_viewer import VERSION, SETTINGS_VERSION, log, _startup_errors
from piano_viewer.constants import (
    MIDI_NOTE_MIN, MIDI_NOTE_MAX,
    DEFAULT_START_NOTE, DEFAULT_END_NOTE,
    INITIAL_KEY_WIDTH, INITIAL_KEY_HEIGHT,
    PRACTICAL_MIN_KEY_WIDTH, MIN_HEIGHT_RATIO,
    KEYBOARD_CANVAS_MARGIN,
    NOTE_NAMES_BLACK_SHARPS, NOTE_NAMES_BLACK_FLATS,
    MIN_FONT_SIZE,
    scaled, total_horizontal_margin,
    WINDOW_VERTICAL_MARGIN,
)


# ---- Config file management ----

def get_config_path():
    """Returns the path to the configuration file.

    On Linux: ~/.config/piano-midi-viewer/settings.ini
    On Windows: %APPDATA%/piano-midi-viewer/settings.ini
    On macOS: ~/Library/Application Support/piano-midi-viewer/settings.ini

    Creates the directory if it doesn't exist.
    """
    if sys.platform == "win32":
        config_dir = Path(os.environ.get("APPDATA", "~")) / "piano-midi-viewer"
    elif sys.platform == "darwin":
        config_dir = Path.home() / "Library" / "Application Support" / "piano-midi-viewer"
    else:
        config_dir = Path.home() / ".config" / "piano-midi-viewer"

    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "settings.ini"


def load_ui_scale():
    """Loads the UI scale factor from settings file.

    Called before the window is created, since button sizes, margins, and
    cursor dimensions are calculated at widget creation time.
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


def migrate_settings():
    """Migrates settings file to the current SETTINGS_VERSION.

    Called once at startup before load_settings(). Reads the settings_version
    field from [meta], applies any needed migrations sequentially, then writes
    the updated version back.
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
        return

    log.info(f"Migrating settings from version {old_version} to {SETTINGS_VERSION}")

    # --- Add future migrations here ---
    # if old_version < 2:
    #     ...

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


# ---- MIDI note math ----

def is_black_key(midi_note):
    """Determines if a MIDI note number corresponds to a black key."""
    return midi_note % 12 in (1, 3, 6, 8, 10)


def count_white_keys(start_note, end_note):
    """Counts how many white keys exist in a given MIDI note range."""
    count = 0
    for note in range(start_note, end_note + 1):
        if not is_black_key(note):
            count += 1
    return count


def get_white_key_index(midi_note, start_note):
    """Gets the position index of a white key (0, 1, 2, 3...)."""
    index = 0
    for note in range(start_note, midi_note):
        if not is_black_key(note):
            index += 1
    return index


def get_left_white_key(black_midi_note, start_note):
    """For a black key, finds the white key immediately to its left."""
    for note in range(black_midi_note - 1, start_note - 1, -1):
        if not is_black_key(note):
            return note
    return start_note


def get_note_name(midi_note):
    """Gets the note name (C, D, E, etc.) for a MIDI note number."""
    note_in_octave = midi_note % 12
    note_map = {0: 'C', 2: 'D', 4: 'E', 5: 'F', 7: 'G', 9: 'A', 11: 'B'}
    return note_map.get(note_in_octave, '')


def get_octave_number(midi_note):
    """Gets the octave number for a MIDI note (60 = C4)."""
    return (midi_note // 12) - 1


def get_black_key_name(midi_note, notation_type):
    """Gets the name(s) for a black key based on notation type.

    Returns:
        tuple: (sharp_name, flat_name) or (name, None) for single notation.
               Returns (None, None) if not a black key.
    """
    if not is_black_key(midi_note):
        return (None, None)

    note_in_octave = midi_note % 12
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


# ---- Window sizing ----

def calculate_initial_window_size():
    """Calculates starting window size from initial key dimensions."""
    num_white_keys = count_white_keys(DEFAULT_START_NOTE, DEFAULT_END_NOTE)
    piano_width = INITIAL_KEY_WIDTH * num_white_keys
    window_width = int(piano_width + total_horizontal_margin())
    window_height = int(INITIAL_KEY_HEIGHT + scaled(WINDOW_VERTICAL_MARGIN))
    return window_width, window_height


# ---- Color and text helpers ----

def get_text_color_for_highlight(highlight_color):
    """Returns black or white text color for optimal contrast on the given background."""
    r = highlight_color.red()
    g = highlight_color.green()
    b = highlight_color.blue()
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
    if luminance > 0.5:
        return QColor(0, 0, 0)
    else:
        return QColor(255, 255, 255)


def blend_colors(base, target, factor):
    """Linearly interpolates between two QColors.

    Used for velocity visualization — soft notes blend just a little towards the
    highlight color (factor ~0.3), while hard notes blend almost fully (factor ~1.0).
    """
    r = base.red() + (target.red() - base.red()) * factor
    g = base.green() + (target.green() - base.green()) * factor
    b = base.blue() + (target.blue() - base.blue()) * factor
    return QColor(int(r), int(g), int(b))


def calculate_font_size_for_width(target_width, num_chars, font_family):
    """Calculates font size to fit a given number of characters in a target width."""
    reference_size = 20
    reference_font = QFont(font_family, reference_size)
    metrics = QFontMetrics(reference_font)
    char_width_at_reference = metrics.horizontalAdvance('M')

    if char_width_at_reference == 0:
        return 0

    pixels_per_point = char_width_at_reference / reference_size
    font_size = int(target_width / (num_chars * pixels_per_point))

    if font_size < MIN_FONT_SIZE:
        return 0
    return font_size


def calculate_font_size_for_height(target_height, font_family):
    """Calculates font size to fit a character in a target height."""
    reference_size = 20
    reference_font = QFont(font_family, reference_size)
    metrics = QFontMetrics(reference_font)
    char_height_at_reference = metrics.ascent() + metrics.descent()

    if char_height_at_reference == 0:
        return 0

    height_per_point = char_height_at_reference / reference_size
    font_size = int(target_height / height_per_point)

    if font_size < MIN_FONT_SIZE:
        return 0
    return font_size


# ---- Button styling ----

def make_button_style(bg_color="#f5f5f5", text_color="#2a2a2a", interactive=True):
    """Generates a QPushButton stylesheet string with scaled border and radius.

    Every button in the app uses this function so they all look consistent.
    The `interactive` flag controls whether hover/pressed/disabled states are
    included — set it to False for indicator-only buttons.
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
