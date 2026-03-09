"""Application entry point — `python -m piano_viewer` starts the app."""

import sys
import os

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFontDatabase
from PyQt6.QtCore import Qt

from piano_viewer import ASSETS_DIR, VERSION, log
import piano_viewer.constants as constants
from piano_viewer.constants import INITIAL_KEY_WIDTH, INITIAL_KEY_HEIGHT, MIN_HEIGHT_RATIO, MAX_HEIGHT_RATIO
from piano_viewer.helpers import migrate_settings, load_ui_scale
from piano_viewer.i18n import load_translations, load_language_setting
from piano_viewer.icons import create_piano_icon
from piano_viewer.main_window import PianoMIDIViewer


def main():
    """Creates and runs the application.

    Startup sequence:
    1. Log startup info
    2. Migrate settings file (if format has changed since last run)
    3. Set up Qt high-DPI support
    4. Create the QApplication
    5. Load the embedded font (JetBrains Mono for note labels and buttons)
    6. Load UI scale from settings (must happen before any widgets are created)
    7. Load language and translations
    8. Create and show the main window
    9. Enter Qt's event loop (blocks until the window is closed)
    """
    log.info(f"Piano MIDI Viewer - Version {VERSION}")
    log.info(f"Initial key size: {INITIAL_KEY_WIDTH}px \u00d7 {INITIAL_KEY_HEIGHT}px")
    log.info(f"Height ratio limits: {MIN_HEIGHT_RATIO}\u00d7 to {MAX_HEIGHT_RATIO}\u00d7 (height/width)")

    migrate_settings()

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setWindowIcon(create_piano_icon())

    # Load JetBrains Mono font for note names, octave numbers, and button labels.
    # Falls back to the system's default monospace font if loading fails.
    font_path = os.path.join(ASSETS_DIR, "JetBrainsMono-Regular.ttf")
    if os.path.exists(font_path):
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id != -1:
            font_families = QFontDatabase.applicationFontFamilies(font_id)
            if font_families:
                constants.LOADED_FONT_FAMILY = font_families[0]
                log.info(f"Loaded font: {constants.LOADED_FONT_FAMILY}")
            else:
                log.warning("Font loaded but no families found")
                constants.LOADED_FONT_FAMILY = "monospace"
        else:
            log.warning(f"Failed to load font from {font_path}")
            constants.LOADED_FONT_FAMILY = "monospace"
    else:
        log.warning(f"Font file not found: {font_path}")
        constants.LOADED_FONT_FAMILY = "monospace"

    # Load UI scale before the window is created, since button sizes, margins,
    # and cursor dimensions are calculated at widget creation time.
    constants.UI_SCALE_FACTOR = load_ui_scale()
    if constants.UI_SCALE_FACTOR != 1.0:
        log.info(f"UI Scale: {int(constants.UI_SCALE_FACTOR * 100)}%")

    # Load language before the window is created, since all UI strings
    # are set during init via tr() calls.
    lang = load_language_setting()
    load_translations(lang)

    window = PianoMIDIViewer()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
