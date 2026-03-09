"""Icon and cursor creation — loads SVGs from assets/ and renders them.

All icons are loaded from SVG files in the assets/ directory at runtime.
They use the Phosphor icon set (Bold weight, 256x256 viewBox, single fill).
Color customization is done via string replacement on the SVG source before
rendering to a QPixmap.

The pedal icon is custom (stroke-based, not from Phosphor).
"""

import os
import re

from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtCore import Qt

from piano_viewer import ASSETS_DIR
from piano_viewer.constants import scaled, BUTTON_SIZE


def _load_svg(filename):
    """Load an SVG file from the assets directory."""
    path = os.path.join(ASSETS_DIR, filename)
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def _render_svg_to_pixmap(svg_data, size):
    """Renders an SVG string to a QPixmap at the given pixel size.

    Replaces or injects width/height attributes so Qt renders at the exact
    size we want. Handles SVGs both with and without existing dimensions.
    """
    # Strip any existing width/height so we can set our own
    svg = re.sub(r'\bwidth="[^"]*"', '', svg_data, count=1)
    svg = re.sub(r'\bheight="[^"]*"', '', svg, count=1)
    svg = svg.replace('viewBox=', f'width="{size}" height="{size}" viewBox=')
    pixmap = QPixmap()
    pixmap.loadFromData(svg.encode())
    return pixmap


def create_piano_icon():
    """Creates the app icon from assets/icon.svg."""
    svg_data = _load_svg('icon.svg')
    # icon.svg has its own width/height, load directly
    pixmap = QPixmap()
    pixmap.loadFromData(svg_data.encode())
    if pixmap.isNull():
        return QIcon()
    return QIcon(pixmap)


def _create_icon(filename, size=None, color="#000000"):
    """Creates a QIcon from an SVG file with the given color.

    Generic helper — most icon functions delegate here.
    """
    if size is None:
        size = scaled(BUTTON_SIZE)
    svg_data = _load_svg(filename)
    svg = svg_data.replace('#000000', color)
    return QIcon(_render_svg_to_pixmap(svg, size))


def create_settings_icon(size=None, color="#000000"):
    """Creates a cogwheel/gear settings icon as a QIcon."""
    return _create_icon('settings.svg', size, color)


def create_pencil_icon(size=None, color="#000000"):
    """Creates a pencil QIcon for the drawing tool button."""
    return _create_icon('pencil.svg', size, color)


def create_save_icon(size=None, color="#000000"):
    """Creates a camera/save QIcon for the 'Save as PNG' button."""
    return _create_icon('camera.svg', size, color)


def create_plus_icon(size=None, color="#000000"):
    """Creates a plus QIcon for the 'add octave' buttons."""
    return _create_icon('plus.svg', size, color)


def create_minus_icon(size=None, color="#000000"):
    """Creates a minus QIcon for the 'remove octave' buttons."""
    return _create_icon('minus.svg', size, color)


def create_refresh_icon(size=None, color="#000000"):
    """Creates a refresh/reload QIcon for the MIDI device refresh button."""
    return _create_icon('refresh.svg', size, color)


def create_pedal_icon(size=None, color="#000000"):
    """Creates a sustain pedal QIcon.

    Unlike Phosphor icons (which use fill), the pedal is stroke-based.
    The same #000000 replacement works because it targets the stroke color.
    """
    return _create_icon('pedal.svg', size, color)
