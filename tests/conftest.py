"""Test configuration for Piano MIDI Viewer.

Creates a shared QApplication instance needed by any Qt-dependent tests.
Import of `piano_viewer` works via `pythonpath = ["."]` in pyproject.toml.
"""
import pytest
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    """Shared QApplication instance for tests that need Qt (colors, fonts, etc.)."""
    app = QApplication.instance() or QApplication([])
    return app
