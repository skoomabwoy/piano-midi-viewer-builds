"""Piano keyboard widget — custom-drawn piano that responds to MIDI and mouse.

All rendering happens in paintEvent() using Qt's QPainter. The widget tracks
active notes (from MIDI), drawn notes (from pencil tool), and mouse state.
"""

from collections import namedtuple

from PyQt6.QtWidgets import QWidget, QMainWindow
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont

from piano_viewer.constants import (
    DEFAULT_START_NOTE, DEFAULT_END_NOTE, DEFAULT_HIGHLIGHT_COLOR,
    BACKGROUND_COLOR, KEYBOARD_CANVAS_MARGIN, KEYBOARD_CANVAS_RADIUS,
    KEY_GAP_RATIO, KEY_GAP_MIN, KEY_GAP_MAX,
    KEY_CORNER_RADIUS_RATIO, KEY_CORNER_RADIUS_MIN,
    BLACK_KEY_HEIGHT_RATIO, BLACK_KEY_WIDTH_RATIO,
    SHADOW_DISABLE_WIDTH,
    WHITE_TEXT_GAP_RATIO, BLACK_TEXT_GAP_RATIO,
    WHITE_KEY_TEXT_WIDTH_RATIO, BLACK_KEY_TEXT_WIDTH_RATIO,
    WHITE_KEY_TEXT_AREA_RATIO, MIN_FONT_SIZE,
)
import piano_viewer.constants as constants
from piano_viewer.helpers import (
    is_black_key, get_left_white_key,
    get_note_name, get_octave_number, get_black_key_name,
    get_text_color_for_highlight, blend_colors, velocity_factor,
    calculate_font_size_for_width, calculate_font_size_for_height,
)


# Geometry shared by painting and mouse hit-testing, recomputed from the
# widget size and note range on demand. white_index maps each white note to
# its 0-based position so note→x lookups are O(1).
_KeyboardLayout = namedtuple('_KeyboardLayout', [
    'x', 'y', 'width', 'height',
    'white_key_width', 'black_key_width', 'black_key_height',
    'key_gap', 'corner_radius', 'white_index',
])


class PianoKeyboard(QWidget):
    """Custom widget that draws and manages a piano keyboard."""

    def __init__(self):
        super().__init__()
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)

        # Visible MIDI note range (can be changed with +/- buttons)
        self.start_note = DEFAULT_START_NOTE
        self.end_note = DEFAULT_END_NOTE

        # active_notes: dict of {MIDI note → velocity} for notes currently held via MIDI
        # active_notes_left/right: same, for notes outside the visible range
        # (triggers +button glow; velocity kept so the note lights up correctly
        # if the range is extended while it is still held)
        # drawn_notes: set of MIDI notes marked with the pencil tool
        self.active_notes = {}
        self.active_notes_left = {}
        self.active_notes_right = {}
        self.drawn_notes = set()

        # Mouse interaction state for click-to-play and glissando (drag across keys)
        self.mouse_held_note = None
        self._drag_button = None
        self.glissando_mode = None

        self.highlight_color = DEFAULT_HIGHLIGHT_COLOR
        # Glow flags: True when out-of-range notes are active on that side
        self.glow_left_plus = False
        self.glow_right_plus = False

    def _compute_layout(self):
        """Computes the key geometry for the current widget size and note range.

        Single source of truth for painting and mouse hit-testing (via
        _key_rect), so the two can never disagree. Returns None when the range
        contains no white keys.
        """
        keyboard_width = self.width() - (KEYBOARD_CANVAS_MARGIN * 2)
        keyboard_height = self.height() - (KEYBOARD_CANVAS_MARGIN * 2)

        white_index = {}
        for note in range(self.start_note, self.end_note + 1):
            if not is_black_key(note):
                white_index[note] = len(white_index)
        if not white_index:
            return None

        white_key_width = keyboard_width / len(white_index)
        return _KeyboardLayout(
            x=KEYBOARD_CANVAS_MARGIN,
            y=KEYBOARD_CANVAS_MARGIN,
            width=keyboard_width,
            height=keyboard_height,
            white_key_width=white_key_width,
            black_key_width=white_key_width * BLACK_KEY_WIDTH_RATIO,
            black_key_height=keyboard_height * BLACK_KEY_HEIGHT_RATIO,
            key_gap=min(KEY_GAP_MAX, max(KEY_GAP_MIN, round(white_key_width * KEY_GAP_RATIO))),
            corner_radius=max(KEY_CORNER_RADIUS_MIN, white_key_width * KEY_CORNER_RADIUS_RATIO),
            white_index=white_index,
        )

    def _key_rect(self, note, layout):
        """Returns the on-screen QRectF of a key (white rects exclude the gap)."""
        if is_black_key(note):
            left_index = layout.white_index[get_left_white_key(note, self.start_note)]
            x = layout.x + (left_index + 1) * layout.white_key_width - layout.black_key_width / 2
            return QRectF(x, layout.y, layout.black_key_width, layout.black_key_height)
        x = layout.x + layout.white_index[note] * layout.white_key_width
        return QRectF(x + layout.key_gap, layout.y,
                      layout.white_key_width - layout.key_gap * 2, layout.height)

    def paintEvent(self, event):
        """Draws the entire piano: grey canvas, white keys, black keys, then text labels.

        White keys are drawn first so black keys overlay them at the correct depth.
        Text labels (note names, octave numbers) are drawn last on top of everything.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setBrush(QBrush(BACKGROUND_COLOR))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(
            QRectF(0, 0, self.width(), self.height()),
            KEYBOARD_CANVAS_RADIUS, KEYBOARD_CANVAS_RADIUS
        )

        layout = self._compute_layout()
        if layout is None:
            return

        main_window = self._get_main_window()
        show_velocity = main_window.show_velocity if main_window else False

        for note in range(self.start_note, self.end_note + 1):
            if not is_black_key(note):
                self._draw_white_key(painter, note, layout, show_velocity)

        for note in range(self.start_note, self.end_note + 1):
            if is_black_key(note):
                self._draw_black_key(painter, note, layout, show_velocity)

        if main_window:
            if main_window.show_white_key_names or main_window.show_octave_numbers:
                self._draw_white_key_text(painter, layout, main_window)
            if main_window.show_black_key_names:
                self._draw_black_key_text(painter, layout, main_window)

    def _is_highlighted(self, midi_note):
        """Check if a note should be highlighted (active, drawn, or mouse-held)."""
        return (midi_note in self.active_notes or
                midi_note in self.drawn_notes or
                (midi_note == self.mouse_held_note and self.glissando_mode != 'off'))

    def _get_fill_color(self, midi_note, base_color, show_velocity):
        """Get the fill color for a key, accounting for highlight and velocity.

        With velocity mode on, the highlight color intensity reflects how hard
        the key was pressed: factor 0.3 (soft) to 1.0 (full force). The 0.3
        floor ensures even the softest notes are clearly visible.
        """
        if not self._is_highlighted(midi_note):
            return base_color
        if show_velocity and midi_note in self.active_notes:
            factor = velocity_factor(self.active_notes[midi_note])
            return blend_colors(base_color, self.highlight_color, factor)
        return self.highlight_color

    def _draw_white_key(self, painter, midi_note, layout, show_velocity=False):
        rect = self._key_rect(midi_note, layout)
        radius = layout.corner_radius

        is_highlighted = self._is_highlighted(midi_note)
        base_color = QColor(252, 252, 252)
        fill_color = self._get_fill_color(midi_note, base_color, show_velocity)

        painter.setBrush(QBrush(fill_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, radius, radius)

        if not is_highlighted and layout.white_key_width >= SHADOW_DISABLE_WIDTH:
            shadow_color = QColor(170, 170, 170)
            painter.setPen(QPen(shadow_color, 1))
            painter.drawLine(
                int(rect.x() + radius), int(rect.y() + rect.height() - 1),
                int(rect.x() + rect.width() - radius), int(rect.y() + rect.height() - 1)
            )
            painter.drawLine(
                int(rect.x() + rect.width() - 1), int(rect.y() + radius),
                int(rect.x() + rect.width() - 1), int(rect.y() + rect.height() - radius)
            )

        border_color = QColor(25, 25, 25) if is_highlighted else QColor(85, 85, 85)
        painter.setPen(QPen(border_color, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, radius, radius)

    def _draw_black_key(self, painter, midi_note, layout, show_velocity=False):
        rect = self._key_rect(midi_note, layout)
        radius = layout.corner_radius

        base_color = QColor(16, 16, 16)
        fill_color = self._get_fill_color(midi_note, base_color, show_velocity)

        painter.setBrush(QBrush(fill_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, radius, radius)

        painter.setPen(QPen(QColor(0, 0, 0), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, radius, radius)

    def _get_text_color(self, note, base_color, show_velocity):
        """Get the text color for a key label, adapting to highlight state."""
        if self._is_highlighted(note):
            if show_velocity and note in self.active_notes:
                factor = velocity_factor(self.active_notes[note])
                fill = blend_colors(base_color, self.highlight_color, factor)
                return get_text_color_for_highlight(fill)
            return get_text_color_for_highlight(self.highlight_color)
        # Default: black on white keys, white on black keys
        if is_black_key(note):
            return QColor(255, 255, 255)
        return QColor(0, 0, 0)

    def _draw_white_key_text(self, painter, layout, main_window):
        font_family = constants.LOADED_FONT_FAMILY if constants.LOADED_FONT_FAMILY else "monospace"
        white_key_height = layout.height
        white_key_width = layout.white_key_width

        text_gap = white_key_height * WHITE_TEXT_GAP_RATIO
        target_width = white_key_width * WHITE_KEY_TEXT_WIDTH_RATIO
        width_based_size = calculate_font_size_for_width(target_width, 1, font_family)

        available_height = white_key_height * WHITE_KEY_TEXT_AREA_RATIO
        both_enabled = main_window.show_white_key_names and main_window.show_octave_numbers

        if both_enabled:
            symbol_height = (available_height - (text_gap * 3)) / 2
        else:
            symbol_height = available_height - (text_gap * 2)
        height_based_size = calculate_font_size_for_height(symbol_height, font_family)

        if width_based_size == 0:
            return

        font_size = min(width_based_size, height_based_size)
        if font_size < MIN_FONT_SIZE:
            return

        font = QFont(font_family, font_size)
        painter.setFont(font)
        font_metrics = painter.fontMetrics()

        for note in range(self.start_note, self.end_note + 1):
            if is_black_key(note):
                continue

            key_x = layout.x + layout.white_index[note] * white_key_width
            key_center_x = key_x + white_key_width / 2

            text_color = self._get_text_color(note, QColor(252, 252, 252), main_window.show_velocity)
            painter.setPen(text_color)

            note_name = get_note_name(note)
            octave_num = get_octave_number(note)
            is_c_note = (note % 12 == 0)

            ascent = font_metrics.ascent()
            descent = font_metrics.descent()
            key_bottom = layout.y + white_key_height

            if main_window.show_white_key_names and main_window.show_octave_numbers:
                letter_baseline_y = key_bottom - text_gap - descent
                octave_baseline_y = key_bottom - (2 * text_gap) - (2 * descent) - ascent

                show_name = not main_window.show_names_when_pressed or self._is_highlighted(note)
                if note_name and show_name:
                    text_width = font_metrics.horizontalAdvance(note_name)
                    text_x = key_center_x - text_width / 2
                    painter.drawText(int(text_x), int(letter_baseline_y), note_name)

                if is_c_note:
                    octave_text = str(octave_num)
                    text_width = font_metrics.horizontalAdvance(octave_text)
                    text_x = key_center_x - text_width / 2
                    painter.drawText(int(text_x), int(octave_baseline_y), octave_text)

            elif main_window.show_white_key_names:
                if main_window.show_names_when_pressed and not self._is_highlighted(note):
                    continue
                letter_baseline_y = key_bottom - text_gap - descent
                if note_name:
                    text_width = font_metrics.horizontalAdvance(note_name)
                    text_x = key_center_x - text_width / 2
                    painter.drawText(int(text_x), int(letter_baseline_y), note_name)

            elif main_window.show_octave_numbers:
                octave_baseline_y = key_bottom - text_gap - descent
                if is_c_note:
                    octave_text = str(octave_num)
                    text_width = font_metrics.horizontalAdvance(octave_text)
                    text_x = key_center_x - text_width / 2
                    painter.drawText(int(text_x), int(octave_baseline_y), octave_text)

    def _draw_black_key_text(self, painter, layout, main_window):
        font_family = constants.LOADED_FONT_FAMILY if constants.LOADED_FONT_FAMILY else "monospace"
        black_key_height = layout.black_key_height

        text_gap = layout.height * BLACK_TEXT_GAP_RATIO
        target_width = layout.white_key_width * BLACK_KEY_TEXT_WIDTH_RATIO
        width_based_size = calculate_font_size_for_width(target_width, 2, font_family)

        both_enabled = (main_window.black_key_notation == "Both")
        if both_enabled:
            symbol_height = (black_key_height - (text_gap * 3)) / 2
        else:
            symbol_height = black_key_height - (text_gap * 2)
        height_based_size = calculate_font_size_for_height(symbol_height, font_family)

        if width_based_size == 0:
            return

        font_size = min(width_based_size, height_based_size)
        if font_size < MIN_FONT_SIZE:
            return

        font = QFont(font_family, font_size)
        painter.setFont(font)
        font_metrics = painter.fontMetrics()

        for note in range(self.start_note, self.end_note + 1):
            if not is_black_key(note):
                continue

            key_center_x = self._key_rect(note, layout).center().x()

            if main_window.show_names_when_pressed and not self._is_highlighted(note):
                continue

            text_color = self._get_text_color(note, QColor(16, 16, 16), main_window.show_velocity)
            painter.setPen(text_color)

            sharp_name, flat_name = get_black_key_name(note, main_window.black_key_notation)
            if not sharp_name and not flat_name:
                continue

            text_height = font_metrics.height()
            ascent = font_metrics.ascent()

            key_top = layout.y
            sharp_top = key_top + text_gap
            sharp_baseline_y = sharp_top + ascent

            if both_enabled:
                sharp_width = font_metrics.horizontalAdvance(sharp_name)
                sharp_x = key_center_x - sharp_width / 2
                painter.drawText(int(sharp_x), int(sharp_baseline_y), sharp_name)

                flat_top = sharp_top + text_height + text_gap
                flat_baseline_y = flat_top + ascent
                flat_width = font_metrics.horizontalAdvance(flat_name)
                flat_x = key_center_x - flat_width / 2
                painter.drawText(int(flat_x), int(flat_baseline_y), flat_name)
            else:
                name = sharp_name if sharp_name else flat_name
                text_width = font_metrics.horizontalAdvance(name)
                text_x = key_center_x - text_width / 2
                painter.drawText(int(text_x), int(sharp_baseline_y), name)

    def _get_main_window(self):
        """Walks up the widget tree to find the main window.

        Used to access display settings (show_velocity, show_white_key_names, etc.)
        without creating a circular import between keyboard.py and main_window.py.
        """
        parent = self.parent()
        while parent and not isinstance(parent, QMainWindow):
            parent = parent.parent()
        return parent

    def _layout_if_inside(self, x, y):
        """Returns the layout when (x, y) lies inside the key canvas, else None."""
        layout = self._compute_layout()
        if layout is None:
            return None
        if not (layout.x <= x <= layout.x + layout.width and
                layout.y <= y <= layout.y + layout.height):
            return None
        return layout

    def _find_closest_note_to_position(self, x, y):
        layout = self._layout_if_inside(x, y)
        if layout is None:
            return None

        closest_note = None
        min_distance_sq = float('inf')

        for note in range(self.start_note, self.end_note + 1):
            center = self._key_rect(note, layout).center()
            distance_sq = (x - center.x()) ** 2 + (y - center.y()) ** 2
            if distance_sq < min_distance_sq:
                min_distance_sq = distance_sq
                closest_note = note

        return closest_note

    def _get_note_at_position(self, x, y):
        layout = self._layout_if_inside(x, y)
        if layout is None:
            return None

        # Black keys first — they sit on top of the white keys.
        for note in range(self.start_note, self.end_note + 1):
            if is_black_key(note):
                rect = self._key_rect(note, layout)
                if (rect.left() <= x <= rect.right() and
                        rect.top() <= y <= rect.bottom()):
                    return note

        # White keys span the full canvas height; only x needs checking
        # (a click in the gap between two keys hits neither).
        for note in range(self.start_note, self.end_note + 1):
            if not is_black_key(note):
                rect = self._key_rect(note, layout)
                if rect.left() <= x <= rect.right():
                    return note

        return None

    def mousePressEvent(self, event):
        note = self._get_note_at_position(event.position().x(), event.position().y())
        if note is None:
            note = self._find_closest_note_to_position(event.position().x(), event.position().y())

        if note is not None:
            main_window = self._get_main_window()

            if main_window and main_window.pencil_active:
                if self.mouse_held_note is not None:
                    return
                if event.button() == Qt.MouseButton.LeftButton:
                    self.glissando_mode = 'on'
                    self.drawn_notes.add(note)
                elif event.button() == Qt.MouseButton.RightButton:
                    self.glissando_mode = 'off'
                    self.drawn_notes.discard(note)
                    if main_window:
                        self.setCursor(main_window._eraser_cursor)
                else:
                    return
                self._drag_button = event.button()
                self.mouse_held_note = note
                self.update()

            elif event.button() == Qt.MouseButton.LeftButton:
                self.active_notes[note] = 127
                self.mouse_held_note = note
                self.glissando_mode = None
                if main_window and main_window.sound_enabled and main_window.synth:
                    main_window.synth.note_on(note)
                self.update()

    def mouseMoveEvent(self, event):
        if self.mouse_held_note is not None:
            note = self._get_note_at_position(event.position().x(), event.position().y())
            if note is None:
                return

            if note != self.mouse_held_note:
                main_window = self._get_main_window()

                if main_window and main_window.pencil_active:
                    if self.glissando_mode == 'on':
                        self.drawn_notes.add(note)
                    elif self.glissando_mode == 'off':
                        self.drawn_notes.discard(note)
                else:
                    if main_window and main_window.sound_enabled and main_window.synth:
                        main_window.synth.note_off(self.mouse_held_note)
                        main_window.synth.note_on(note)
                    self.active_notes.pop(self.mouse_held_note, None)
                    self.active_notes[note] = 127

                self.mouse_held_note = note
                self.update()

    def mouseReleaseEvent(self, event):
        if self.mouse_held_note is not None:
            main_window = self._get_main_window()

            if main_window and main_window.pencil_active:
                if event.button() != getattr(self, '_drag_button', None):
                    return
                self._drag_button = None
                if self.glissando_mode == 'off' and main_window:
                    self.setCursor(main_window._pencil_cursor)
            else:
                if self.mouse_held_note in self.active_notes:
                    self.active_notes.pop(self.mouse_held_note, None)
                    if main_window and main_window.sound_enabled and main_window.synth:
                        main_window.synth.note_off(self.mouse_held_note)

            self.mouse_held_note = None
            self.glissando_mode = None
            self.update()
