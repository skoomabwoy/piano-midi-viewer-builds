"""Piano MIDI Viewer — a visual piano that lights up when you play."""

import os
import logging

VERSION = "9.1.1"
SETTINGS_VERSION = 1

# Package paths — used by i18n.py and icons.py to locate resources.
# Works in development (piano_viewer/ is next to assets/ and translations/)
# and in PyInstaller builds (_internal/piano_viewer/ next to _internal/assets/).
_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(os.path.dirname(_PACKAGE_DIR), 'assets')
TRANSLATIONS_DIR = os.path.join(os.path.dirname(_PACKAGE_DIR), 'translations')

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
except Exception:
    # ImportError if sounddevice is not installed, or PortAudioError / OSError
    # if the audio subsystem is broken (e.g. no ALSA/PulseAudio on headless Linux).
    _SOUND_AVAILABLE = False

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
