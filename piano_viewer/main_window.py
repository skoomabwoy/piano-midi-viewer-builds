"""Main application window — manages MIDI, UI layout, and app state."""

import os
import configparser
from datetime import datetime

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QLabel, QFileDialog, QApplication,
)
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt, QTimer, QByteArray

from piano_viewer import (
    SETTINGS_VERSION, _SOUND_AVAILABLE, log, _startup_errors,
)
import piano_viewer.constants as constants
import piano_viewer.i18n as i18n
from piano_viewer.constants import (
    scaled, total_horizontal_margin, min_window_height,
    DEFAULT_START_NOTE, DEFAULT_END_NOTE,
    MIDI_NOTE_MIN, MIDI_NOTE_MAX,
    INITIAL_KEY_WIDTH, INITIAL_KEY_HEIGHT,
    PRACTICAL_MIN_KEY_WIDTH, MIN_HEIGHT_RATIO, MAX_HEIGHT_RATIO,
    KEYBOARD_CANVAS_MARGIN, WINDOW_VERTICAL_MARGIN,
    LAYOUT_MARGIN, BUTTON_SIZE, BUTTON_AREA_WIDTH,
    BUTTON_SPACING, STATUS_MESSAGE_DURATION,
)
from piano_viewer.i18n import tr
from piano_viewer.helpers import (
    get_config_path, calculate_initial_window_size,
    count_white_keys, get_text_color_for_highlight, make_button_style,
    velocity_factor,
)
from piano_viewer.midi_input import MidiInput
from piano_viewer.icons import (
    create_settings_icon, create_pencil_icon, create_save_icon,
    create_plus_icon, create_minus_icon, create_pedal_icon,
    create_pencil_cursor, create_eraser_cursor,
)
from piano_viewer.synth import PianoSynthesizer
from piano_viewer.dialogs import ErrorDialog
from piano_viewer.settings import SettingsDialog
from piano_viewer.keyboard import PianoKeyboard


class PianoMIDIViewer(QMainWindow):
    """Main application window — manages MIDI, UI layout, and app state."""

    def __init__(self):
        super().__init__()

        # Reentrancy guard: resizeEvent() may call self.resize() to enforce
        # height ratio limits, which triggers another resizeEvent(). Without
        # this guard, we'd get infinite recursion.
        self._in_resize_event = False

        # --- MIDI input transport (owns rtmidi handles + poll/scan timers) ---
        self.midi = MidiInput(
            on_note_on=self.handle_note_on,
            on_note_off=self.handle_note_off,
            on_sustain=self.handle_sustain,
            on_disconnect=self.on_midi_disconnect,
            on_connect=self._on_midi_connect,
            on_status=self.show_status_message,
            on_error=self.show_error_dialog,
        )
        self.status_hide_timer = None

        # --- Sustain pedal state ---
        self.sustain_pedal_active = False

        # --- Pencil tool state ---
        self.pencil_active = False
        self._pencil_cursor = create_pencil_cursor()
        self._eraser_cursor = create_eraser_cursor()

        # --- Computer keyboard input ---
        self.computer_keyboard_enabled = False
        self.computer_keyboard_octave = 4  # C4–C5 by default
        self._computer_keys_held = {}  # Qt key code → MIDI note

        # --- Note display settings (all saved to settings.ini) ---
        self.show_octave_numbers = True
        self.show_white_key_names = True
        self.show_black_key_names = False
        self.black_key_notation = "Flats"
        self.show_names_when_pressed = False
        self.show_velocity = False

        # --- Built-in sound ---
        self.sound_enabled = False
        self.synth = PianoSynthesizer() if _SOUND_AVAILABLE else None

        self.init_ui()
        self.midi.start()

        # Always attempt the load, even if migration reported a startup error
        # (e.g. it couldn't write the migrated file) — the file may still be
        # perfectly readable, and skipping the load here would run the app on
        # defaults and then overwrite the user's real settings on the next save.
        self.load_settings()

        # MIDI device auto-select — for users who have exactly one real instrument.
        # Priority: (1) saved device from config (handled by load_settings above),
        # (2) single real device auto-select (here), (3) no device.
        # Virtual ports (e.g. ALSA "Midi Through") are filtered out so they don't
        # count — only real instruments trigger auto-select.
        if not self.midi.connected:
            real = self.midi.real_devices()
            if len(real) == 1 and self.midi.connect(real[0]):
                self.save_settings()

        if _startup_errors:
            errors = "\n".join(_startup_errors)
            QTimer.singleShot(0, lambda: self.show_error_dialog(
                tr("Startup Error"),
                tr("Errors occurred during startup:\n\n{}").format(errors),
                offer_reset=True))
            _startup_errors.clear()

    def init_ui(self):
        """Sets up the user interface (three-column layout with piano in center)."""
        self.setWindowTitle("Piano MIDI Viewer")
        # App-level icon is set in __main__.py; no need to set it per-window.

        # Only set initial size on first call; rebuilds keep the current window size.
        if not self.centralWidget():
            initial_width, initial_height = calculate_initial_window_size()
            self.resize(initial_width, initial_height)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(0)
        lm = scaled(LAYOUT_MARGIN)
        main_layout.setContentsMargins(lm, lm, lm, lm)

        button_style = make_button_style()
        btn_sz = scaled(BUTTON_SIZE)

        # LEFT SIDE (pencil button + save + octave controls)
        left_container = QWidget()
        left_container.setFixedWidth(scaled(BUTTON_AREA_WIDTH))
        left_layout = QVBoxLayout(left_container)
        left_layout.setSpacing(scaled(BUTTON_SPACING))
        left_layout.setContentsMargins(0, 0, scaled(3), 0)
        left_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.pencil_button = QPushButton()
        self.pencil_button.setToolTip(tr("Pencil tool — left click to mark, right click to erase\nPress Esc to exit"))
        self.pencil_button.setFixedSize(btn_sz, btn_sz)
        self.pencil_button.setIcon(create_pencil_icon())
        self.pencil_button.setIconSize(self.pencil_button.size() * 0.7)
        self.pencil_button.setStyleSheet(button_style)
        self.pencil_button.clicked.connect(self.toggle_pencil)
        left_layout.addWidget(self.pencil_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self.save_button = QPushButton()
        self.save_button.setToolTip(tr("Save keyboard as image\nRight-click to quick save"))
        self.save_button.setFixedSize(btn_sz, btn_sz)
        self.save_button.setIcon(create_save_icon())
        self.save_button.setIconSize(self.save_button.size() * 0.7)
        self.save_button.setStyleSheet(button_style)
        self.save_button.clicked.connect(self.save_keyboard_image)
        self.save_button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.save_button.customContextMenuRequested.connect(self.quick_save_keyboard_image)
        left_layout.addWidget(self.save_button, alignment=Qt.AlignmentFlag.AlignCenter)

        left_layout.addStretch()

        self.left_plus_btn = QPushButton()
        self.left_plus_btn.setToolTip(tr("Add octave on the left (lower notes)"))
        self.left_plus_btn.setFixedSize(btn_sz, btn_sz)
        self.left_plus_btn.setIcon(create_plus_icon())
        self.left_plus_btn.setIconSize(self.left_plus_btn.size() * 0.7)
        self.left_plus_btn.setStyleSheet(button_style)
        self.left_plus_btn.clicked.connect(self.add_octave_left)

        self.left_minus_btn = QPushButton()
        self.left_minus_btn.setToolTip(tr("Remove octave on the left (lower notes)"))
        self.left_minus_btn.setFixedSize(btn_sz, btn_sz)
        self.left_minus_btn.setIcon(create_minus_icon())
        self.left_minus_btn.setIconSize(self.left_minus_btn.size() * 0.7)
        self.left_minus_btn.setStyleSheet(button_style)
        self.left_minus_btn.clicked.connect(self.remove_octave_left)

        left_layout.addWidget(self.left_plus_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(self.left_minus_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # CENTER — reuse existing piano widget on rebuild (preserves state)
        if not hasattr(self, 'piano') or self.piano is None:
            self.piano = PianoKeyboard()

        # RIGHT SIDE (settings + sustain + octave controls)
        right_container = QWidget()
        right_container.setFixedWidth(scaled(BUTTON_AREA_WIDTH))
        right_layout = QVBoxLayout(right_container)
        right_layout.setSpacing(scaled(BUTTON_SPACING))
        right_layout.setContentsMargins(scaled(3), 0, 0, 0)
        right_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.settings_button = QPushButton()
        self.settings_button.setToolTip(tr("Open Settings"))
        self.settings_button.setFixedSize(btn_sz, btn_sz)
        self.settings_button.setIcon(create_settings_icon(btn_sz, "#000000"))
        self.settings_button.setIconSize(self.settings_button.size() * 0.7)
        self.settings_button.setStyleSheet(button_style)
        self.settings_button.clicked.connect(self.open_settings)

        self.sustain_button = QPushButton()
        self.sustain_button.setToolTip(tr("Sustain pedal indicator — lights up when your sustain pedal is held"))
        self.sustain_button.setFixedSize(btn_sz, btn_sz)
        self.sustain_button.setIcon(create_pedal_icon())
        self.sustain_button.setIconSize(self.sustain_button.size() * 0.7)
        self.sustain_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        right_layout.addWidget(self.settings_button, alignment=Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(self.sustain_button, alignment=Qt.AlignmentFlag.AlignCenter)
        right_layout.addStretch()

        self.right_plus_btn = QPushButton()
        self.right_plus_btn.setToolTip(tr("Add octave on the right (higher notes)"))
        self.right_plus_btn.setFixedSize(btn_sz, btn_sz)
        self.right_plus_btn.setIcon(create_plus_icon())
        self.right_plus_btn.setIconSize(self.right_plus_btn.size() * 0.7)
        self.right_plus_btn.setStyleSheet(button_style)
        self.right_plus_btn.clicked.connect(self.add_octave_right)

        self.right_minus_btn = QPushButton()
        self.right_minus_btn.setToolTip(tr("Remove octave on the right (higher notes)"))
        self.right_minus_btn.setFixedSize(btn_sz, btn_sz)
        self.right_minus_btn.setIcon(create_minus_icon())
        self.right_minus_btn.setIconSize(self.right_minus_btn.size() * 0.7)
        self.right_minus_btn.setStyleSheet(button_style)
        self.right_minus_btn.clicked.connect(self.remove_octave_right)

        right_layout.addWidget(self.right_plus_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(self.right_minus_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # Status overlay (parented to the piano, floats on top). Created once and
        # reused across rebuilds — the piano widget survives rebuild_ui(), so a
        # fresh label each time would just orphan the previous one on the piano.
        if not hasattr(self, 'status_label') or self.status_label is None:
            self.status_label = QLabel("", self.piano)
            self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.status_label.setStyleSheet(
                "background-color: #404040; color: #ffffff;"
                "padding: 6px 16px; border-radius: 8px;"
            )
            self.status_label.setVisible(False)

        # ASSEMBLE
        main_layout.addWidget(left_container)
        main_layout.addWidget(self.piano, 1)
        main_layout.addWidget(right_container)

        self.update_button_states()
        self.update_minimum_size()
        self.update_sustain_button_visual()

    # --- Live UI refresh ---

    def rebuild_ui(self):
        """Tears down and rebuilds the UI layout, preserving the piano widget and all state."""
        # Detach piano so it survives central widget destruction
        self.piano.setParent(None)
        old = self.centralWidget()
        if old:
            old.setParent(None)

        self.init_ui()

        # Re-apply stateful visuals
        self.update_pencil_button_visual()
        self.update_sustain_button_visual()
        if self.piano.glow_left_plus:
            self.apply_button_glow(self.left_plus_btn, True)
        if self.piano.glow_right_plus:
            self.apply_button_glow(self.right_plus_btn, True)
        if self.pencil_active:
            self.piano.setCursor(self._pencil_cursor)

    def apply_scale(self, new_scale):
        """Applies a new UI scale factor live, without restart."""
        constants.UI_SCALE_FACTOR = new_scale
        self.rebuild_ui()
        self.save_settings()

    def apply_language(self, lang_code):
        """Applies a new language live, without restart."""
        i18n.load_translations(lang_code)
        self.rebuild_ui()
        self.save_settings()

    # --- Settings dialog ---

    def open_settings(self):
        """Opens the settings dialog (non-modal, one instance at a time)."""
        if hasattr(self, '_settings_dialog') and self._settings_dialog.isVisible():
            self._settings_dialog.raise_()
            return
        self._settings_dialog = SettingsDialog(self)
        self._settings_dialog.show()

    # --- Settings persistence ---

    # Plain on/off settings, shared by load_settings() and save_settings():
    # (config section, key, attribute name). Adding a boolean toggle is a
    # one-line change here instead of three edits across load and save.
    _BOOL_SETTINGS = (
        ('appearance', 'show_octave_numbers', 'show_octave_numbers'),
        ('appearance', 'show_white_key_names', 'show_white_key_names'),
        ('appearance', 'show_black_key_names', 'show_black_key_names'),
        ('appearance', 'show_names_when_pressed', 'show_names_when_pressed'),
        ('appearance', 'show_velocity', 'show_velocity'),
        ('input', 'computer_keyboard', 'computer_keyboard_enabled'),
    )

    def load_settings(self):
        """Loads settings from the configuration file."""
        config_path = get_config_path()
        config = configparser.ConfigParser()

        if not config_path.exists():
            return

        try:
            config.read(config_path)
        except Exception as e:
            log.error(f"Error reading settings file: {e}")
            error_msg = tr("Could not read settings file: {}\n\nDefault settings will be used.").format(e)
            QTimer.singleShot(0, lambda: self.show_error_dialog(
                tr("Settings Error"), error_msg, offer_reset=True))
            return

        reset_keys = []

        if config.has_option('midi', 'device'):
            device_name = config.get('midi', 'device')
            if device_name:
                self.connect_midi_device(device_name, save=False)

        if config.has_option('appearance', 'highlight_color'):
            color_hex = config.get('appearance', 'highlight_color')
            color = QColor(color_hex)
            if color.isValid():
                self.piano.highlight_color = color
                self.piano.update()
            else:
                reset_keys.append('highlight_color')

        for section, key, attr in self._BOOL_SETTINGS:
            if config.has_option(section, key):
                try:
                    setattr(self, attr, config.getboolean(section, key))
                except ValueError:
                    reset_keys.append(key)

        if config.has_option('appearance', 'black_key_notation'):
            notation = config.get('appearance', 'black_key_notation')
            if notation in ['Flats', 'Sharps', 'Both']:
                self.black_key_notation = notation
            else:
                reset_keys.append('black_key_notation')

        if config.has_option('keyboard', 'start_note') and config.has_option('keyboard', 'end_note'):
            try:
                start_note = config.getint('keyboard', 'start_note')
                end_note = config.getint('keyboard', 'end_note')
                if (MIDI_NOTE_MIN <= start_note <= MIDI_NOTE_MAX and
                    MIDI_NOTE_MIN <= end_note <= MIDI_NOTE_MAX and
                    end_note >= start_note + 11):
                    self.piano.start_note = start_note
                    self.piano.end_note = end_note
                    self.update_button_states()
                    self.update_minimum_size()
                else:
                    reset_keys.append('start_note/end_note')
            except ValueError:
                reset_keys.append('start_note/end_note')

        if _SOUND_AVAILABLE and config.has_option('audio', 'sound_enabled'):
            try:
                self.sound_enabled = config.getboolean('audio', 'sound_enabled')
                if self.sound_enabled and self.synth:
                    self.synth.start()
            except ValueError:
                reset_keys.append('sound_enabled')

        if config.has_option('window', 'geometry'):
            geometry_string = config.get('window', 'geometry')
            geometry_bytes = QByteArray.fromBase64(geometry_string.encode())
            self.restoreGeometry(geometry_bytes)

        if reset_keys:
            names = ", ".join(reset_keys)
            log.warning(f"Reset invalid settings to defaults: {names}")
            QTimer.singleShot(0, lambda: self.show_status_message(
                tr("Reset invalid settings: {}").format(names)))
            QTimer.singleShot(100, lambda: self.save_settings())

    def save_settings(self):
        """Saves current settings to the configuration file."""
        config_path = get_config_path()
        config = configparser.ConfigParser()

        config['midi'] = {
            'device': self.current_midi_device or ''
        }

        config['appearance'] = {
            'highlight_color': self.piano.highlight_color.name(),
            'black_key_notation': self.black_key_notation,
            'ui_scale': str(constants.UI_SCALE_FACTOR),
            'language': i18n.get_current_language(),
        }

        config['keyboard'] = {
            'start_note': str(self.piano.start_note),
            'end_note': str(self.piano.end_note),
        }

        config['audio'] = {
            'sound_enabled': str(self.sound_enabled),
        }

        config['input'] = {}

        geometry_bytes = self.saveGeometry()
        geometry_string = geometry_bytes.toBase64().data().decode()
        config['window'] = {
            'geometry': geometry_string,
        }

        config['meta'] = {
            'settings_version': str(SETTINGS_VERSION),
        }

        # On/off toggles (table-driven, shared with load_settings). Each target
        # section is created above before we fill these in.
        for section, key, attr in self._BOOL_SETTINGS:
            config[section][key] = str(getattr(self, attr))

        try:
            with open(config_path, 'w') as f:
                config.write(f)
        except Exception as e:
            log.error(f"Error saving settings: {e}")
            self.show_error_dialog(
                tr("Settings Error"),
                tr("Could not save settings: {}\n\nYour changes may be lost.").format(e),
                offer_reset=True)

    # --- Pencil tool ---

    def toggle_pencil(self):
        """Toggles the pencil drawing tool on/off."""
        if self.pencil_active:
            self.pencil_active = False
            self.piano.drawn_notes.clear()
            self.piano.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            self.pencil_active = True
            self.piano.active_notes.clear()
            self.piano.active_notes_left.clear()
            self.piano.active_notes_right.clear()
            self.piano.mouse_held_note = None
            self.piano.glissando_mode = None
            self.piano.setCursor(self._pencil_cursor)

        # Both transitions clear the state that drives the glow (drawn marks on
        # exit, active notes on enter), so a single recompute settles both sides.
        self._refresh_out_of_range_glow()
        self.update_pencil_button_visual()
        self.piano.update()

    # --- Save keyboard image ---

    def save_keyboard_image(self):
        """Opens a file dialog to save the piano keyboard as a PNG image."""
        filename, _ = QFileDialog.getSaveFileName(
            self, tr("Save Keyboard Image"),
            os.path.join(os.path.expanduser("~"), "piano_keyboard.png"),
            tr("PNG Image (*.png)")
        )
        if filename:
            if not filename.lower().endswith('.png'):
                filename += '.png'
            pixmap = self.piano.grab()
            if pixmap.save(filename, "PNG"):
                self.show_status_message(tr("Saved to {}").format(os.path.basename(filename)))
            else:
                log.error(f"Failed to save keyboard image to {filename}")
                self.show_status_message(tr("Save failed: {}").format(os.path.basename(filename)))

    def quick_save_keyboard_image(self):
        """Quick-saves the piano keyboard as PNG to ~/Pictures with a timestamp."""
        save_dir = os.path.join(os.path.expanduser("~"), "Pictures", "PianoMIDIViewer")
        os.makedirs(save_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(save_dir, f"piano_{timestamp}.png")
        pixmap = self.piano.grab()
        if pixmap.save(filename, "PNG"):
            self.show_status_message(tr("Saved to {}").format(os.path.basename(filename)))
        else:
            log.error(f"Failed to quick-save keyboard image to {filename}")
            self.show_status_message(tr("Save failed: {}").format(os.path.basename(filename)))

    # --- Button visual updates ---

    def update_pencil_button_visual(self):
        """Updates the pencil button appearance based on pencil tool state."""
        if self.pencil_active:
            bg_color = self.piano.highlight_color.name()
            icon_color = get_text_color_for_highlight(self.piano.highlight_color).name()
            self.pencil_button.setIcon(create_pencil_icon(color=icon_color))
            self.pencil_button.setStyleSheet(make_button_style(bg_color=bg_color, text_color=icon_color, interactive=False))
        else:
            self.pencil_button.setIcon(create_pencil_icon(color="#000000"))
            self.pencil_button.setStyleSheet(make_button_style(interactive=False))

    def update_sustain_button_visual(self):
        """Updates the sustain button appearance based on the MIDI sustain pedal state."""
        if self.sustain_pedal_active:
            bg_color = self.piano.highlight_color.name()
            icon_color = get_text_color_for_highlight(self.piano.highlight_color).name()
            self.sustain_button.setIcon(create_pedal_icon(color=icon_color))
            self.sustain_button.setStyleSheet(make_button_style(bg_color=bg_color, text_color=icon_color, interactive=False))
        else:
            self.sustain_button.setIcon(create_pedal_icon())
            self.sustain_button.setStyleSheet(make_button_style(interactive=False))

    def apply_button_glow(self, button, glow):
        """Applies or removes a highlight glow on a + button.

        Updates both the stylesheet (background) and the SVG icon color
        so the icon stays visible against the highlighted background.
        """
        if glow:
            bg_color = self.piano.highlight_color.name()
            icon_color = get_text_color_for_highlight(self.piano.highlight_color).name()
            button.setIcon(create_plus_icon(color=icon_color))
            button.setStyleSheet(make_button_style(bg_color=bg_color, text_color=icon_color, interactive=False))
        else:
            button.setIcon(create_plus_icon())
            button.setStyleSheet(make_button_style())

    def get_current_key_dimensions(self):
        """Calculates current white key width and height from the piano widget size."""
        num_white_keys = count_white_keys(self.piano.start_note, self.piano.end_note)
        if num_white_keys == 0:
            return None, None
        key_width = self.piano.width() / num_white_keys
        key_height = self.piano.height() - (KEYBOARD_CANVAS_MARGIN * 2)
        return key_width, key_height

    # --- MIDI (transport lives in self.midi; these bridge it to the UI) ---

    @property
    def current_midi_device(self):
        """Name of the connected device (or None) — read by Settings and save."""
        return self.midi.current_device

    def get_midi_devices(self):
        """Returns the list of available MIDI input device names (for Settings)."""
        return self.midi.get_devices()

    def connect_midi_device(self, device_name, save=True):
        """Connects to a MIDI device by name. Returns True on success.

        `save` defaults to True so user-initiated connections persist immediately.
        It is passed False during load_settings(), where saving mid-load would
        write half-initialized state (default display flags, pre-restore geometry)
        over the file we are still reading.
        """
        if self.midi.connect(device_name):
            if save:
                self.save_settings()
            return True
        return False

    def _on_midi_connect(self, device_name):
        """Persist a connection the transport made on its own (background scan)."""
        self.save_settings()

    def handle_sustain(self, active):
        """Handles a sustain-pedal (CC 64) state change."""
        self.sustain_pedal_active = active
        self.update_sustain_button_visual()
        if self.sound_enabled and self.synth:
            self.synth.set_sustain(active)

    def on_midi_disconnect(self, device_name):
        """Clears playing state when the active device disconnects.

        The transport has already closed the port; this only resets UI/visual
        state (active notes, glow, sustain) and shows a toast.
        """
        self.piano.active_notes.clear()
        self.piano.active_notes_left.clear()
        self.piano.active_notes_right.clear()
        self._refresh_out_of_range_glow()

        if self.sustain_pedal_active:
            self.sustain_pedal_active = False
            self.update_sustain_button_visual()

        self.piano.update()
        self.show_status_message(tr("Disconnected: {}").format(device_name))

    def _refresh_out_of_range_glow(self):
        """Recomputes the +button glow on both sides from current state.

        A side glows when any active note or any pencil mark falls outside the
        visible range on that side. Idempotent — call it after any change to the
        range, active notes, or drawn notes instead of toggling the glow by hand.
        """
        want_left = (bool(self.piano.active_notes_left) or
                     any(n < self.piano.start_note for n in self.piano.drawn_notes))
        want_right = (bool(self.piano.active_notes_right) or
                      any(n > self.piano.end_note for n in self.piano.drawn_notes))

        if want_left != self.piano.glow_left_plus:
            self.piano.glow_left_plus = want_left
            self.apply_button_glow(self.left_plus_btn, want_left)
        if want_right != self.piano.glow_right_plus:
            self.piano.glow_right_plus = want_right
            self.apply_button_glow(self.right_plus_btn, want_right)

    def handle_note_on(self, note_number, velocity=127):
        """Handles a Note On event (from MIDI or the computer keyboard)."""
        if self.pencil_active:
            if note_number in self.piano.drawn_notes:
                self.piano.drawn_notes.discard(note_number)
            else:
                self.piano.drawn_notes.add(note_number)

            if self.piano.start_note <= note_number <= self.piano.end_note:
                self.piano.update()
            else:
                self._refresh_out_of_range_glow()
            return

        if self.sound_enabled and self.synth:
            vel_scale = velocity_factor(velocity) if self.show_velocity else 1.0
            self.synth.note_on(note_number, vel_scale)

        if self.piano.start_note <= note_number <= self.piano.end_note:
            self.piano.active_notes[note_number] = velocity
            self.piano.update()
        elif note_number < self.piano.start_note:
            self.piano.active_notes_left.add(note_number)
            self._refresh_out_of_range_glow()
        else:
            self.piano.active_notes_right.add(note_number)
            self._refresh_out_of_range_glow()

    def handle_note_off(self, note_number):
        """Handles a Note Off event (from MIDI or the computer keyboard)."""
        if self.pencil_active:
            return

        if self.sound_enabled and self.synth:
            self.synth.note_off(note_number)

        if note_number in self.piano.active_notes:
            self.piano.active_notes.pop(note_number, None)
            self.piano.update()

        self.piano.active_notes_left.discard(note_number)
        self.piano.active_notes_right.discard(note_number)
        self._refresh_out_of_range_glow()

    # --- Octave management ---

    def add_octave_left(self):
        """Extends the keyboard range by one octave on the left (lower notes)."""
        self._change_range('start', -12)

    def remove_octave_left(self):
        """Removes an octave from the left."""
        self._change_range('start', 12)

    def add_octave_right(self):
        """Adds an octave to the right (higher notes)."""
        self._change_range('end', 12)

    def remove_octave_right(self):
        """Removes an octave from the right."""
        self._change_range('end', -12)

    def _change_range(self, edge, delta):
        """Shifts one edge of the visible range by `delta` semitones.

        edge is 'start' (left/low) or 'end' (right/high). No-ops if the change
        would cross the MIDI bounds or shrink below the one-octave (12-key)
        minimum. Resizes the window to keep the current key width, refreshes the
        out-of-range glow, and updates button/minimum-size state.
        """
        if edge == 'start':
            new_value = self.piano.start_note + delta
        else:
            new_value = self.piano.end_note + delta

        # Reject out-of-bounds or below the one-octave minimum span.
        if new_value < MIDI_NOTE_MIN or new_value > MIDI_NOTE_MAX:
            return
        if edge == 'start' and new_value > self.piano.end_note - 11:
            return
        if edge == 'end' and new_value < self.piano.start_note + 11:
            return

        key_width, _ = self.get_current_key_dimensions()
        if key_width is None:
            return

        if edge == 'start':
            self.piano.start_note = new_value
        else:
            self.piano.end_note = new_value

        self._refresh_out_of_range_glow()

        new_num_white = count_white_keys(self.piano.start_note, self.piano.end_note)
        new_window_width = round(key_width * new_num_white + total_horizontal_margin())
        self.resize(new_window_width, self.height())

        self.piano.update()
        self.update_button_states()
        self.update_minimum_size()

    def update_button_states(self):
        """Updates the enabled/disabled state of octave +/- buttons."""
        self.left_plus_btn.setEnabled(self.piano.start_note > MIDI_NOTE_MIN + 12)
        self.left_minus_btn.setEnabled(self.piano.end_note - self.piano.start_note > 11)
        self.right_plus_btn.setEnabled(self.piano.end_note < MIDI_NOTE_MAX - 12)
        self.right_minus_btn.setEnabled(self.piano.end_note - self.piano.start_note > 11)

    def update_minimum_size(self):
        """Updates minimum window size based on current octave range."""
        num_white_keys = count_white_keys(self.piano.start_note, self.piano.end_note)
        min_key_width = PRACTICAL_MIN_KEY_WIDTH
        min_key_height = min_key_width * MIN_HEIGHT_RATIO
        min_width = (min_key_width * num_white_keys) + total_horizontal_margin()
        key_based_height = min_key_height + (KEYBOARD_CANVAS_MARGIN * 2) + scaled(WINDOW_VERTICAL_MARGIN)
        min_height = max(key_based_height, min_window_height())
        self.setMinimumSize(int(min_width), int(min_height))

    # --- Status messages ---

    def show_status_message(self, text):
        """Shows a temporary toast notification centered near the bottom of the piano."""
        num_white = count_white_keys(self.piano.start_note, self.piano.end_note)
        if num_white > 0:
            white_key_width = self.piano.width() / num_white
            font_size = max(8, int(white_key_width / 2.0))
        else:
            font_size = 13
        self.status_label.setStyleSheet(
            f"background-color: #404040; color: #ffffff;"
            f"font-size: {font_size}px; padding: 6px 16px; border-radius: 8px;"
        )
        self.status_label.setText(text)
        self.status_label.adjustSize()
        x = (self.piano.width() - self.status_label.width()) // 2
        y = self.piano.height() - self.status_label.height() - 12
        self.status_label.move(max(0, x), max(0, y))
        self.status_label.setVisible(True)
        self.status_label.raise_()

        if self.status_hide_timer:
            self.status_hide_timer.stop()

        self.status_hide_timer = QTimer()
        self.status_hide_timer.setSingleShot(True)
        self.status_hide_timer.timeout.connect(lambda: self.status_label.setVisible(False))
        self.status_hide_timer.start(STATUS_MESSAGE_DURATION)

    def show_error_dialog(self, title, details, offer_reset=False):
        """Shows an error dialog with copy-to-clipboard support."""
        reset_cb = self._reset_settings_file if offer_reset else None
        dialog = ErrorDialog(title, str(details), parent=self, reset_callback=reset_cb)
        dialog.exec()

    def _reset_settings_file(self):
        """Deletes the settings file and shows a confirmation toast."""
        config_path = get_config_path()
        try:
            if config_path.exists():
                config_path.unlink()
            self.show_status_message(tr("Settings reset — restart to apply"))
        except Exception as e:
            log.error(f"Error resetting settings: {e}")

    # --- Window events ---

    def resizeEvent(self, event):
        """Enforces height ratio limits during window resize."""
        if self._in_resize_event:
            super().resizeEvent(event)
            return

        self._in_resize_event = True
        try:
            super().resizeEvent(event)

            w = self.width()
            h = self.height()

            num_white_keys = count_white_keys(self.piano.start_note, self.piano.end_note)
            if num_white_keys == 0:
                return

            h_margin = total_horizontal_margin()
            v_margin = scaled(WINDOW_VERTICAL_MARGIN)
            piano_width = w - h_margin
            piano_height = h - v_margin
            white_key_width = piano_width / num_white_keys
            white_key_height = piano_height - (KEYBOARD_CANVAS_MARGIN * 2)

            if white_key_width > 0:
                height_ratio = white_key_height / white_key_width

                if height_ratio > MAX_HEIGHT_RATIO:
                    white_key_height = white_key_width * MAX_HEIGHT_RATIO
                    h = round(white_key_height + (KEYBOARD_CANVAS_MARGIN * 2) + v_margin)
                elif height_ratio < MIN_HEIGHT_RATIO:
                    white_key_width = white_key_height / MIN_HEIGHT_RATIO
                    w = round(white_key_width * num_white_keys + h_margin)

            if w != self.width() or h != self.height():
                self.resize(w, h)
        finally:
            self._in_resize_event = False

    # Computer keyboard → MIDI note offset mapping (one octave + C above).
    # Home row = white keys, row above = black keys (standard DAW layout).
    _COMPUTER_KEY_MAP = {
        Qt.Key.Key_A: 0,   # C
        Qt.Key.Key_W: 1,   # C#
        Qt.Key.Key_S: 2,   # D
        Qt.Key.Key_E: 3,   # D#
        Qt.Key.Key_D: 4,   # E
        Qt.Key.Key_F: 5,   # F
        Qt.Key.Key_T: 6,   # F#
        Qt.Key.Key_G: 7,   # G
        Qt.Key.Key_Y: 8,   # G#
        Qt.Key.Key_H: 9,   # A
        Qt.Key.Key_U: 10,  # A#
        Qt.Key.Key_J: 11,  # B
        Qt.Key.Key_K: 12,  # C (next octave)
    }

    def _computer_key_to_note(self, key):
        """Converts a Qt key code to a MIDI note number, or None if unmapped."""
        offset = self._COMPUTER_KEY_MAP.get(key)
        if offset is None:
            return None
        note = (self.computer_keyboard_octave + 1) * 12 + offset
        if MIDI_NOTE_MIN <= note <= MIDI_NOTE_MAX:
            return note
        return None

    def _octave_label(self):
        """Returns a string like 'C4–C5' for the current computer keyboard octave."""
        return f"C{self.computer_keyboard_octave}\u2013C{self.computer_keyboard_octave + 1}"

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts and computer keyboard input."""
        if event.isAutoRepeat():
            return

        key = event.key()

        # Caps Lock toggles computer keyboard
        if key == Qt.Key.Key_CapsLock:
            self.computer_keyboard_enabled = not self.computer_keyboard_enabled
            if self.computer_keyboard_enabled:
                self.show_status_message(
                    tr("Computer keyboard: ON ({})").format(self._octave_label()))
            else:
                # Release all held computer keyboard notes
                for held_note in list(self._computer_keys_held.values()):
                    self.handle_note_off(held_note)
                self._computer_keys_held.clear()
                self.show_status_message(tr("Computer keyboard: OFF"))
            self.save_settings()
            return

        # Pencil shortcuts (always active)
        if key == Qt.Key.Key_Escape and self.pencil_active:
            self.toggle_pencil()
            return
        if key == Qt.Key.Key_P and not event.modifiers():
            self.toggle_pencil()
            return

        # Octave range shortcuts (always active)
        if key == Qt.Key.Key_BracketLeft and not event.modifiers():
            self.add_octave_left()
            return
        if key == Qt.Key.Key_BraceLeft:
            self.remove_octave_left()
            return
        if key == Qt.Key.Key_BracketRight and not event.modifiers():
            self.add_octave_right()
            return
        if key == Qt.Key.Key_BraceRight:
            self.remove_octave_right()
            return

        # Toggle shortcuts (always active)
        if key == Qt.Key.Key_O and not event.modifiers():
            self.show_octave_numbers = not self.show_octave_numbers
            self.piano.update()
            self.save_settings()
            return
        if key == Qt.Key.Key_V and not event.modifiers():
            self.show_velocity = not self.show_velocity
            self.piano.update()
            self.save_settings()
            state = tr("ON") if self.show_velocity else tr("OFF")
            self.show_status_message(tr("Velocity: {}").format(state))
            return

        # Everything below requires computer keyboard to be enabled
        if not self.computer_keyboard_enabled:
            return

        # Z/X shift octave
        if key == Qt.Key.Key_Z:
            if self.computer_keyboard_octave > 1:
                self.computer_keyboard_octave -= 1
                self.show_status_message(
                    tr("Keyboard: {}").format(self._octave_label()))
            return
        if key == Qt.Key.Key_X:
            if self.computer_keyboard_octave < 7:
                self.computer_keyboard_octave += 1
                self.show_status_message(
                    tr("Keyboard: {}").format(self._octave_label()))
            return

        # Piano keys
        note = self._computer_key_to_note(key)
        if note is not None and key not in self._computer_keys_held:
            self._computer_keys_held[key] = note
            self.handle_note_on(note, 100)

    def keyReleaseEvent(self, event):
        """Handle computer keyboard note-off on key release."""
        if event.isAutoRepeat():
            return

        key = event.key()
        if key in self._computer_keys_held:
            note = self._computer_keys_held.pop(key)
            self.handle_note_off(note)

    def closeEvent(self, event):
        """Saves settings and frees MIDI/audio resources on close."""
        self.save_settings()

        if self.synth:
            self.synth.stop()

        self.midi.shutdown()

        event.accept()
