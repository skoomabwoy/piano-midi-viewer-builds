"""Piano MIDI Viewer — a visual piano that lights up when you play."""

import os
import logging

VERSION = "9.4.0"
SETTINGS_VERSION = 1

# Package paths — runtime resources live inside the package (piano_viewer/
# resources/) as package data, so they travel with the import in both dev and
# PyInstaller builds. The spec bundles resources/ to the same relative location.
_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
RESOURCES_DIR = os.path.join(_PACKAGE_DIR, 'resources')
ICONS_DIR = os.path.join(RESOURCES_DIR, 'icons')
FONTS_DIR = os.path.join(RESOURCES_DIR, 'fonts')
IMAGES_DIR = os.path.join(RESOURCES_DIR, 'images')
TRANSLATIONS_DIR = os.path.join(RESOURCES_DIR, 'translations')

# Logger — all modules use `log.info()`, `log.warning()`, `log.error()`.
# Outputs to stderr so it doesn't interfere with stdout.
log = logging.getLogger("piano-midi-viewer")
log.setLevel(logging.DEBUG)
_log_handler = logging.StreamHandler()
_log_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
log.addHandler(_log_handler)

# Collects errors that happen before the main window exists (e.g. settings migration).
# Flushed into an error dialog once the window is ready.
_startup_errors = []

# Optional: sounddevice for built-in piano sound (wavetable synthesis).
# If not installed, the Sound feature is simply unavailable in Settings.
try:
    import sounddevice as _sd
    _SOUND_AVAILABLE = True
    log.info("Sound backend: %s", _sd.query_hostapis())
except Exception as e:
    # ImportError if sounddevice is not installed, or PortAudioError / OSError
    # if the audio subsystem is broken (e.g. no ALSA/PulseAudio on headless Linux).
    _SOUND_AVAILABLE = False
    log.warning("Built-in sound unavailable: %s", e)

# Re-exports — so `from piano_viewer import X` keeps working for tests and
# any code that imports from the top-level package name.
from piano_viewer.helpers import (  # noqa: E402, F401
    get_config_path,
    migrate_settings,
    is_black_key,
    count_white_keys,
    get_white_key_index,
    get_left_white_key,
    get_note_name,
    get_octave_number,
    get_black_key_name,
    get_text_color_for_highlight,
    blend_colors,
)
