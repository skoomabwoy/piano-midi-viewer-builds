"""Icon and cursor creation — loads SVGs from assets/ and renders them.

All icons are loaded from SVG files in the assets/ directory at runtime.
Color customization is done via string replacement on the SVG source before
rendering to a QPixmap.
"""

import os

from PyQt6.QtGui import QPixmap, QIcon, QCursor
from PyQt6.QtCore import Qt

from piano_viewer import ASSETS_DIR
from piano_viewer.constants import (
    scaled, CURSOR_SIZE, CURSOR_OUTLINE_COLOR, CURSOR_FILL_COLOR, BUTTON_SIZE,
)


def _load_svg(filename):
    """Load an SVG file from the assets directory."""
    path = os.path.join(ASSETS_DIR, filename)
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def _render_svg_to_pixmap(svg_data, size):
    """Renders an SVG string to a QPixmap at the given pixel size.

    Injects width/height attributes into the SVG so Qt renders it at the
    exact size we want, regardless of the SVG's original viewBox dimensions.
    """
    svg = svg_data.replace('viewBox=', f'width="{size}" height="{size}" viewBox=')
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


def create_settings_icon(size=64, color="#000000"):
    """Creates a cogwheel/gear settings icon as a QIcon."""
    svg_data = _load_svg('settings.svg')
    svg_data = svg_data.replace('#000000', color)
    return QIcon(_render_svg_to_pixmap(svg_data, size))


def create_pencil_cursor():
    """Creates a pencil cursor with hotspot at the pencil tip (bottom-left).

    Hotspot coordinates are fractions of cursor size, derived from the SVG layout:
    the pencil tip sits at ~0% from left edge and ~90% from top edge.
    """
    size = max(16, scaled(CURSOR_SIZE))
    svg_data = _load_svg('pencil.svg')
    svg = svg_data.replace('#ffffff', CURSOR_FILL_COLOR).replace('#000000', CURSOR_OUTLINE_COLOR)
    pixmap = _render_svg_to_pixmap(svg, size)
    return QCursor(pixmap, max(0, int(size * 0.004)), int(size * 0.90))


def create_eraser_cursor():
    """Creates an eraser cursor with hotspot at bottom-left erasing edge.

    Hotspot coordinates are fractions of cursor size, derived from the SVG layout:
    the eraser's working edge sits at ~9% from left and ~94% from top.
    """
    size = max(16, scaled(CURSOR_SIZE))
    svg_data = _load_svg('eraser.svg')
    svg = svg_data.replace('#ffffff', CURSOR_FILL_COLOR).replace('#000000', CURSOR_OUTLINE_COLOR)
    pixmap = _render_svg_to_pixmap(svg, size)
    return QCursor(pixmap, max(0, int(size * 0.09)), int(size * 0.94))


def create_pencil_icon(size=None, color="#000000"):
    """Creates a pencil QIcon — transparent interior, colored outline."""
    if size is None:
        size = scaled(BUTTON_SIZE)
    svg_data = _load_svg('pencil.svg')
    svg = svg_data.replace('fill="#ffffff"', 'fill="none"').replace('#000000', color)
    return QIcon(_render_svg_to_pixmap(svg, size))


def create_save_icon(size=None, color="#000000"):
    """Creates a camera/save QIcon for the 'Save as PNG' button."""
    if size is None:
        size = scaled(BUTTON_SIZE)
    svg_data = _load_svg('camera.svg')
    svg = svg_data.replace('#000000', color)
    return QIcon(_render_svg_to_pixmap(svg, size))
