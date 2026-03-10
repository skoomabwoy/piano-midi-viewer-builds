"""Main application window — manages MIDI, UI layout, and app state."""

import os
import configparser
from datetime import datetime

import rtmidi
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
    BUTTON_SPACING, MIDI_POLL_INTERVAL, MIDI_SCAN_INTERVAL,
    STATUS_MESSAGE_DURATION,
)
from piano_viewer.i18n import tr
from piano_viewer.helpers import (
    get_config_path, calculate_initial_window_size,
    count_white_keys, get_text_color_for_highlight, make_button_style,
)
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

        # --- MIDI connection state ---
        self.midi_in = None
        self.midi_scanner = None
        self.current_midi_device = None
        self.midi_timer = None
        self.known_midi_devices = []
        self.device_scan_timer = None
        self.status_hide_timer = None

        # --- Sustain pedal state ---
        self.sustain_pedal_active = False

        # --- Pencil tool state ---
        self.pencil_active = False
        self._pencil_cursor = create_pencil_cursor()
        self._eraser_cursor = create_eraser_cursor()

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
        self.setup_midi_polling()
        self.setup_device_scanning()

        if not _startup_errors:
            self.load_settings()

        # MIDI device auto-select — for users who have exactly one real instrument.
        # Priority: (1) saved device from config (handled by load_settings above),
        # (2) single real device auto-select (here), (3) no device.
        # Virtual ports (e.g. ALSA "Midi Through") are filtered out so they don't
        # count — only real instruments trigger auto-select.
        if not self.midi_in:
            real = self._filter_virtual_devices(self.known_midi_devices)
            if len(real) == 1:
                self.connect_midi_device(real[0])

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

        # Status overlay (parented to piano, floats on top)
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
                self.connect_midi_device(device_name)

        if config.has_option('appearance', 'highlight_color'):
            color_hex = config.get('appearance', 'highlight_color')
            color = QColor(color_hex)
            if color.isValid():
                self.piano.highlight_color = color
                self.piano.update()
            else:
                reset_keys.append('highlight_color')

        for key, attr in [
            ('show_octave_numbers', 'show_octave_numbers'),
            ('show_white_key_names', 'show_white_key_names'),
            ('show_black_key_names', 'show_black_key_names'),
            ('show_names_when_pressed', 'show_names_when_pressed'),
            ('show_velocity', 'show_velocity'),
        ]:
            if config.has_option('appearance', key):
                try:
                    setattr(self, attr, config.getboolean('appearance', key))
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
            'show_octave_numbers': str(self.show_octave_numbers),
            'show_white_key_names': str(self.show_white_key_names),
            'show_black_key_names': str(self.show_black_key_names),
            'black_key_notation': self.black_key_notation,
            'show_names_when_pressed': str(self.show_names_when_pressed),
            'show_velocity': str(self.show_velocity),
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

        geometry_bytes = self.saveGeometry()
        geometry_string = geometry_bytes.toBase64().data().decode()
        config['window'] = {
            'geometry': geometry_string,
        }

        config['meta'] = {
            'settings_version': str(SETTINGS_VERSION),
        }

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
            if self.piano.glow_left_plus:
                self.piano.glow_left_plus = False
                self.apply_button_glow(self.left_plus_btn, False)
            if self.piano.glow_right_plus:
                self.piano.glow_right_plus = False
                self.apply_button_glow(self.right_plus_btn, False)
        else:
            self.pencil_active = True
            self.piano.active_notes.clear()
            self.piano.active_notes_left.clear()
            self.piano.active_notes_right.clear()
            self.piano.mouse_held_note = None
            self.piano.glissando_mode = None
            if self.piano.glow_left_plus:
                self.piano.glow_left_plus = False
                self.apply_button_glow(self.left_plus_btn, False)
            if self.piano.glow_right_plus:
                self.piano.glow_right_plus = False
                self.apply_button_glow(self.right_plus_btn, False)
            self.piano.setCursor(self._pencil_cursor)

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
            pixmap.save(filename, "PNG")
            self.show_status_message(tr("Saved to {}").format(os.path.basename(filename)))

    def quick_save_keyboard_image(self):
        """Quick-saves the piano keyboard as PNG to ~/Pictures with a timestamp."""
        save_dir = os.path.join(os.path.expanduser("~"), "Pictures", "PianoMIDIViewer")
        os.makedirs(save_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(save_dir, f"piano_{timestamp}.png")
        pixmap = self.piano.grab()
        pixmap.save(filename, "PNG")
        self.show_status_message(tr("Saved to {}").format(os.path.basename(filename)))

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

    # --- MIDI ---

    # Known virtual/system MIDI port prefixes — never auto-selected, but always
    # visible in Settings so the user can connect manually if they want to.
    _VIRTUAL_MIDI_PREFIXES = (
        "Midi Through",     # ALSA built-in virtual loopback
    )

    @staticmethod
    def _filter_virtual_devices(devices):
        """Returns devices that don't match known virtual port prefixes."""
        return [d for d in devices
                if not d.startswith(PianoMIDIViewer._VIRTUAL_MIDI_PREFIXES)]

    def get_midi_devices(self):
        """Returns list of available MIDI input device names."""
        try:
            if not self.midi_scanner:
                self.midi_scanner = rtmidi.MidiIn()
            return self.midi_scanner.get_ports()
        except Exception as e:
            log.error(f"Error scanning MIDI devices: {e}")
            self.show_error_dialog(
                tr("MIDI Error"), tr("Could not scan for MIDI devices: {}").format(e))
            return []

    def connect_midi_device(self, device_name):
        """Connects to the specified MIDI input device. Returns True on success."""
        ports = self.get_midi_devices()
        if device_name not in ports:
            log.warning(f"Device not found: {device_name}")
            self.show_status_message(tr("Not found: {}").format(device_name))
            return False

        try:
            new_midi_in = rtmidi.MidiIn()
            port_index = ports.index(device_name)
            new_midi_in.open_port(port_index)
        except Exception as e:
            log.error(f"Error connecting to MIDI device: {e}")
            self.show_status_message(tr("Connection failed: {}").format(device_name))
            return False

        if self.midi_in:
            try:
                self.midi_in.close_port()
            except Exception:
                pass
            del self.midi_in

        self.midi_in = new_midi_in
        self.current_midi_device = device_name
        log.info(f"Connected to MIDI device: {device_name}")
        self.show_status_message(tr("Connected: {}").format(device_name))
        self.save_settings()
        return True

    def setup_midi_polling(self):
        """Sets up a timer to poll for MIDI messages."""
        self.midi_timer = QTimer()
        self.midi_timer.timeout.connect(self.poll_midi_messages)
        self.midi_timer.start(MIDI_POLL_INTERVAL)

    def setup_device_scanning(self):
        """Sets up a timer to periodically scan for MIDI device changes."""
        self.known_midi_devices = self.get_midi_devices()
        self.device_scan_timer = QTimer()
        self.device_scan_timer.timeout.connect(self.scan_midi_devices)
        self.device_scan_timer.start(MIDI_SCAN_INTERVAL)

    def scan_midi_devices(self):
        """Checks for MIDI device changes (called every 3 seconds).

        Handles two scenarios:
        - Device disappeared: if it was our active device, disconnect gracefully.
        - Device appeared: if we have no active connection, try to auto-connect.
          Previously used device gets priority (e.g. USB cable reconnected).
          Otherwise, auto-connect only if exactly one new real device appeared.
        """
        current_ports = self.get_midi_devices()

        previous = set(self.known_midi_devices)
        current = set(current_ports)
        self.known_midi_devices = list(current_ports)

        if current == previous:
            return

        appeared = current - previous
        disappeared = previous - current

        if self.current_midi_device and self.current_midi_device in disappeared:
            self.handle_midi_disconnect()

        if not self.midi_in and appeared:
            if self.current_midi_device in appeared:
                # Previously used device came back — reconnect regardless of filter
                self.connect_midi_device(self.current_midi_device)
            else:
                # Only auto-connect if exactly one real (non-virtual) device appeared
                real_appeared = self._filter_virtual_devices(list(appeared))
                if len(real_appeared) == 1:
                    self.connect_midi_device(real_appeared[0])

    def handle_midi_disconnect(self):
        """Handles a MIDI device disconnection gracefully."""
        device_name = self.current_midi_device or "Unknown device"

        if self.midi_in:
            try:
                self.midi_in.close_port()
            except Exception:
                pass
            del self.midi_in
            self.midi_in = None

        self.piano.active_notes.clear()
        self.piano.active_notes_left.clear()
        self.piano.active_notes_right.clear()

        if self.piano.glow_left_plus:
            self.piano.glow_left_plus = False
            self.apply_button_glow(self.left_plus_btn, False)
        if self.piano.glow_right_plus:
            self.piano.glow_right_plus = False
            self.apply_button_glow(self.right_plus_btn, False)

        if self.sustain_pedal_active:
            self.sustain_pedal_active = False
            self.update_sustain_button_visual()

        self.piano.update()
        self.show_status_message(tr("Disconnected: {}").format(device_name))

    def poll_midi_messages(self):
        """Checks for new MIDI messages and processes them (called every 10ms)."""
        if not self.midi_in:
            return

        try:
            while True:
                message = self.midi_in.get_message()
                if message is None:
                    break
                midi_data, _ = message
                self.process_midi_message(midi_data)
        except Exception as e:
            log.error(f"Error polling MIDI: {e}")
            self.handle_midi_disconnect()

    def process_midi_message(self, midi_data):
        """Processes a MIDI message and updates the keyboard display."""
        if len(midi_data) < 3:
            return

        status_byte = midi_data[0]
        data1 = midi_data[1]
        data2 = midi_data[2]
        message_type = status_byte & 0xF0

        if message_type == 0xB0:
            if data1 == 64:  # Sustain pedal
                self.sustain_pedal_active = (data2 >= 64)
                self.update_sustain_button_visual()
                if self.sound_enabled and self.synth:
                    self.synth.set_sustain(self.sustain_pedal_active)
        elif message_type == 0x90 and data2 > 0:
            self.handle_note_on(data1, data2)
        elif message_type == 0x80 or (message_type == 0x90 and data2 == 0):
            self.handle_note_off(data1)

    def handle_note_on(self, note_number, velocity=127):
        """Handles a Note On MIDI event."""
        if self.pencil_active:
            if note_number in self.piano.drawn_notes:
                self.piano.drawn_notes.discard(note_number)
            else:
                self.piano.drawn_notes.add(note_number)

            if self.piano.start_note <= note_number <= self.piano.end_note:
                self.piano.update()
            elif note_number < self.piano.start_note:
                has_drawn_left = any(n < self.piano.start_note for n in self.piano.drawn_notes)
                if has_drawn_left and not self.piano.glow_left_plus:
                    self.piano.glow_left_plus = True
                    self.apply_button_glow(self.left_plus_btn, True)
                elif not has_drawn_left and self.piano.glow_left_plus:
                    self.piano.glow_left_plus = False
                    self.apply_button_glow(self.left_plus_btn, False)
            else:
                has_drawn_right = any(n > self.piano.end_note for n in self.piano.drawn_notes)
                if has_drawn_right and not self.piano.glow_right_plus:
                    self.piano.glow_right_plus = True
                    self.apply_button_glow(self.right_plus_btn, True)
                elif not has_drawn_right and self.piano.glow_right_plus:
                    self.piano.glow_right_plus = False
                    self.apply_button_glow(self.right_plus_btn, False)
            return

        if self.sound_enabled and self.synth:
            vel_scale = (0.3 + 0.7 * (velocity / 127.0)) if self.show_velocity else 1.0
            self.synth.note_on(note_number, vel_scale)

        if self.piano.start_note <= note_number <= self.piano.end_note:
            self.piano.active_notes[note_number] = velocity
            self.piano.update()
        elif note_number < self.piano.start_note:
            self.piano.active_notes_left.add(note_number)
            if not self.piano.glow_left_plus:
                self.piano.glow_left_plus = True
                self.apply_button_glow(self.left_plus_btn, True)
        else:
            self.piano.active_notes_right.add(note_number)
            if not self.piano.glow_right_plus:
                self.piano.glow_right_plus = True
                self.apply_button_glow(self.right_plus_btn, True)

    def handle_note_off(self, note_number):
        """Handles a Note Off MIDI event."""
        if self.pencil_active:
            return

        if self.sound_enabled and self.synth:
            self.synth.note_off(note_number)

        if note_number in self.piano.active_notes:
            self.piano.active_notes.pop(note_number, None)
            self.piano.update()

        if note_number in self.piano.active_notes_left:
            self.piano.active_notes_left.discard(note_number)
            if not self.piano.active_notes_left and self.piano.glow_left_plus:
                self.piano.glow_left_plus = False
                self.apply_button_glow(self.left_plus_btn, False)

        if note_number in self.piano.active_notes_right:
            self.piano.active_notes_right.discard(note_number)
            if not self.piano.active_notes_right and self.piano.glow_right_plus:
                self.piano.glow_right_plus = False
                self.apply_button_glow(self.right_plus_btn, False)

    # --- Octave management ---

    def add_octave_left(self):
        """Extends the keyboard range by one octave on the left."""
        new_start = self.piano.start_note - 12
        if new_start < MIDI_NOTE_MIN:
            return

        key_width, _ = self.get_current_key_dimensions()
        if key_width is None:
            return

        self.piano.start_note = new_start

        drawn_left = any(n < self.piano.start_note for n in self.piano.drawn_notes)
        if not self.piano.active_notes_left and not drawn_left and self.piano.glow_left_plus:
            self.piano.glow_left_plus = False
            self.apply_button_glow(self.left_plus_btn, False)

        new_num_white = count_white_keys(self.piano.start_note, self.piano.end_note)
        new_window_width = round(key_width * new_num_white + total_horizontal_margin())
        self.resize(new_window_width, self.height())

        self.piano.update()
        self.update_button_states()
        self.update_minimum_size()

    def remove_octave_left(self):
        """Removes an octave from the left."""
        new_start = self.piano.start_note + 12
        if new_start > self.piano.end_note - 11:
            return

        key_width, _ = self.get_current_key_dimensions()
        if key_width is None:
            return

        self.piano.start_note = new_start

        drawn_left = any(n < self.piano.start_note for n in self.piano.drawn_notes)
        if (self.piano.active_notes_left or drawn_left) and not self.piano.glow_left_plus:
            self.piano.glow_left_plus = True
            self.apply_button_glow(self.left_plus_btn, True)

        new_num_white = count_white_keys(self.piano.start_note, self.piano.end_note)
        new_window_width = round(key_width * new_num_white + total_horizontal_margin())
        self.resize(new_window_width, self.height())

        self.piano.update()
        self.update_button_states()
        self.update_minimum_size()

    def add_octave_right(self):
        """Adds an octave to the right (higher notes)."""
        new_end = self.piano.end_note + 12
        if new_end > MIDI_NOTE_MAX:
            return

        key_width, _ = self.get_current_key_dimensions()
        if key_width is None:
            return

        self.piano.end_note = new_end

        drawn_right = any(n > self.piano.end_note for n in self.piano.drawn_notes)
        if not self.piano.active_notes_right and not drawn_right and self.piano.glow_right_plus:
            self.piano.glow_right_plus = False
            self.apply_button_glow(self.right_plus_btn, False)

        new_num_white = count_white_keys(self.piano.start_note, self.piano.end_note)
        new_window_width = round(key_width * new_num_white + total_horizontal_margin())
        self.resize(new_window_width, self.height())

        self.piano.update()
        self.update_button_states()
        self.update_minimum_size()

    def remove_octave_right(self):
        """Removes an octave from the right."""
        new_end = self.piano.end_note - 12
        if new_end < self.piano.start_note + 11:
            return

        key_width, _ = self.get_current_key_dimensions()
        if key_width is None:
            return

        self.piano.end_note = new_end

        drawn_right = any(n > self.piano.end_note for n in self.piano.drawn_notes)
        if (self.piano.active_notes_right or drawn_right) and not self.piano.glow_right_plus:
            self.piano.glow_right_plus = True
            self.apply_button_glow(self.right_plus_btn, True)

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

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts (Esc/P for pencil tool)."""
        if event.key() == Qt.Key.Key_Escape and self.pencil_active:
            self.toggle_pencil()
        elif event.key() == Qt.Key.Key_P and not event.modifiers():
            self.toggle_pencil()

    def closeEvent(self, event):
        """Saves settings and frees MIDI resources on close."""
        self.save_settings()

        if self.synth:
            self.synth.stop()

        if self.midi_timer:
            self.midi_timer.stop()

        if self.device_scan_timer:
            self.device_scan_timer.stop()

        if self.midi_in:
            try:
                self.midi_in.close_port()
            except Exception:
                pass
            del self.midi_in

        if self.midi_scanner:
            del self.midi_scanner

        event.accept()
