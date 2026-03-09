"""Translation system — tr() wrapper and language utilities.

Translations are stored in JSON files under translations/ (one per language).
English is the default and needs no file. The tr() function returns the
translated string or falls back to the English original.
"""

import os
import json
import configparser

from piano_viewer import TRANSLATIONS_DIR, log

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


def get_current_language():
    """Returns the currently active language code."""
    return _current_language


def load_translations(lang_code):
    """Loads translation strings for the given language code."""
    global _translations, _current_language
    _current_language = lang_code
    if lang_code == "en":
        _translations = {}
        return
    translation_file = os.path.join(TRANSLATIONS_DIR, f"{lang_code}.json")
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


def tr_for(lang_code, text):
    """Returns a translated string for a specific language (without changing global state)."""
    if lang_code == "en":
        return text
    translation_file = os.path.join(TRANSLATIONS_DIR, f"{lang_code}.json")
    try:
        with open(translation_file, 'r', encoding='utf-8') as f:
            return json.load(f).get(text, text)
    except Exception:
        return text


def load_language_setting():
    """Loads the language setting from config file. Called before window creation."""
    from piano_viewer.helpers import get_config_path
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
