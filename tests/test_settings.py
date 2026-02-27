"""Tests for settings migration.

Uses tmp_path fixture to isolate from real settings files.
Monkeypatches get_config_path() to point at a temporary directory.
"""
import configparser
from pathlib import Path

import pytest

import piano_viewer


def _write_ini(path, sections):
    """Helper: write a dict-of-dicts as an INI file."""
    config = configparser.ConfigParser()
    for section, values in sections.items():
        config[section] = values
    with open(path, 'w') as f:
        config.write(f)


def _read_ini(path):
    """Helper: read an INI file and return a ConfigParser."""
    config = configparser.ConfigParser()
    config.read(path)
    return config


@pytest.fixture
def settings_file(tmp_path, monkeypatch):
    """Provides a temporary settings.ini path and patches get_config_path()."""
    ini_path = tmp_path / "settings.ini"
    monkeypatch.setattr(piano_viewer, "get_config_path", lambda: ini_path)
    return ini_path


class TestMigrateSettings:
    """Test the settings migration framework."""

    def test_no_file_does_nothing(self, settings_file):
        # File doesn't exist yet — should return without error
        assert not settings_file.exists()
        piano_viewer.migrate_settings()
        assert not settings_file.exists()

    def test_stamps_version_on_old_file(self, settings_file):
        # File exists but has no [meta] section (pre-migration settings)
        _write_ini(settings_file, {
            'appearance': {'highlight_color': '#ff0000'},
        })
        piano_viewer.migrate_settings()

        config = _read_ini(settings_file)
        assert config.getint('meta', 'settings_version') == piano_viewer.SETTINGS_VERSION

    def test_preserves_existing_settings(self, settings_file):
        _write_ini(settings_file, {
            'appearance': {'highlight_color': '#ff0000', 'ui_scale': '1.5'},
            'keyboard': {'start_note': '48', 'end_note': '83'},
        })
        piano_viewer.migrate_settings()

        config = _read_ini(settings_file)
        assert config.get('appearance', 'highlight_color') == '#ff0000'
        assert config.get('appearance', 'ui_scale') == '1.5'
        assert config.get('keyboard', 'start_note') == '48'

    def test_already_current_version_is_noop(self, settings_file):
        _write_ini(settings_file, {
            'meta': {'settings_version': str(piano_viewer.SETTINGS_VERSION)},
            'appearance': {'highlight_color': '#ff0000'},
        })
        # Record modification time
        mtime_before = settings_file.stat().st_mtime_ns

        piano_viewer.migrate_settings()

        # File should not have been rewritten
        mtime_after = settings_file.stat().st_mtime_ns
        assert mtime_before == mtime_after

    def test_future_version_is_noop(self, settings_file):
        # If someone has a newer version somehow, don't downgrade
        _write_ini(settings_file, {
            'meta': {'settings_version': '999'},
        })
        piano_viewer.migrate_settings()

        config = _read_ini(settings_file)
        assert config.getint('meta', 'settings_version') == 999

    def test_invalid_version_treated_as_zero(self, settings_file):
        _write_ini(settings_file, {
            'meta': {'settings_version': 'garbage'},
        })
        piano_viewer.migrate_settings()

        config = _read_ini(settings_file)
        assert config.getint('meta', 'settings_version') == piano_viewer.SETTINGS_VERSION

    def test_version_zero_migrates(self, settings_file):
        # Explicit version 0 should still trigger migration
        _write_ini(settings_file, {
            'meta': {'settings_version': '0'},
        })
        piano_viewer.migrate_settings()

        config = _read_ini(settings_file)
        assert config.getint('meta', 'settings_version') == piano_viewer.SETTINGS_VERSION
