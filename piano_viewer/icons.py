"""Icon and cursor creation — loads SVGs from resources/icons/ and renders them.

All icons are loaded from SVG files in the resources/icons/ directory at runtime.
They use the Phosphor icon set (Bold weight, 256x256 viewBox, single fill).
Color customization is done via string replacement on the SVG source before
rendering to a QPixmap.

The pedal icon is custom (stroke-based, not from Phosphor).
"""

import os
import re

from PyQt6.QtGui import QPixmap, QIcon, QCursor, QGuiApplication

from piano_viewer import ICONS_DIR, IMAGES_DIR
from piano_viewer.constants import scaled, BUTTON_SIZE

CURSOR_SIZE = 24  # logical px at 100% UI scale; scaled() is applied at creation


def _device_pixel_ratio():
    """Highest device pixel ratio among attached screens (1.0 pre-QApplication)."""
    app = QGuiApplication.instance()
    return app.devicePixelRatio() if app is not None else 1.0


def _load_svg(filename):
    """Load an SVG file from the resources/icons directory."""
    path = os.path.join(ICONS_DIR, filename)
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def _render_svg_to_pixmap(svg_data, size):
    """Renders an SVG string to a QPixmap at the given logical pixel size.

    Replaces or injects width/height attributes so Qt renders at the exact
    size we want. Handles SVGs both with and without existing dimensions.
    Renders at device resolution (logical size x screen pixel ratio) and tags
    the pixmap with the ratio, so icons and cursors stay crisp on HiDPI
    displays instead of being upscaled from a 1x raster.
    """
    dpr = _device_pixel_ratio()
    px = max(1, round(size * dpr))
    # Strip any existing width/height so we can set our own
    svg = re.sub(r'\bwidth="[^"]*"', '', svg_data, count=1)
    svg = re.sub(r'\bheight="[^"]*"', '', svg, count=1)
    svg = svg.replace('viewBox=', f'width="{px}" height="{px}" viewBox=')
    pixmap = QPixmap()
    pixmap.loadFromData(svg.encode())
    pixmap.setDevicePixelRatio(dpr)
    return pixmap


def create_piano_icon():
    """Creates the app icon from resources/images/icon.png."""
    path = os.path.join(IMAGES_DIR, 'icon.png')
    pixmap = QPixmap(path)
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


def create_pencil_cursor():
    """Creates a pencil QCursor from the cursor SVG. Hotspot at the pencil tip (bottom-left).

    Size and hotspot follow the UI scale so the cursor keeps its proportion
    to the buttons and keys it is used with.
    """
    svg_data = _load_svg('pencil-cursor.svg')
    pixmap = _render_svg_to_pixmap(svg_data, scaled(CURSOR_SIZE))
    return QCursor(pixmap, scaled(1), scaled(23))


def create_eraser_cursor():
    """Creates an eraser QCursor from the cursor SVG. Hotspot at the eraser edge (bottom-left)."""
    svg_data = _load_svg('eraser-cursor.svg')
    pixmap = _render_svg_to_pixmap(svg_data, scaled(CURSOR_SIZE))
    return QCursor(pixmap, scaled(4), scaled(21))
