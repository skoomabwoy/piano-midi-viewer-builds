"""Test configuration for Piano MIDI Viewer.

Adds the project root to sys.path so tests can import from piano_viewer.py.
Creates a shared QApplication instance needed by any Qt-dependent tests.
"""
import sys
from pathlib import Path

# Add project root to path so `import piano_viewer` works
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    """Shared QApplication instance for tests that need Qt (colors, fonts, etc.)."""
    app = QApplication.instance() or QApplication([])
    return app
