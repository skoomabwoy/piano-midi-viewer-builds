"""Settings dialog and update checker.

The settings dialog lets users configure MIDI devices, highlight color,
note display options, UI scale, and check for updates. It opens as a
non-modal window so MIDI input keeps working while settings are open.
"""

import os
import subprocess
import ssl
import json
import webbrowser
from urllib.request import urlopen, Request
from urllib.error import URLError

import certifi

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton, QLabel,
    QCheckBox, QColorDialog,
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal

from piano_viewer import VERSION, _SOUND_AVAILABLE, log
import piano_viewer.constants as constants
import piano_viewer.i18n as i18n
from piano_viewer.i18n import tr, LANGUAGES
from piano_viewer.helpers import make_button_style
from piano_viewer.icons import create_refresh_icon


class UpdateChecker(QThread):
    """Background thread that checks Codeberg for a newer release."""
    result = pyqtSignal(str, str)

    def run(self):
        try:
            url = "https://codeberg.org/api/v1/repos/skoomabwoy/piano-midi-viewer/releases/latest"
            req = Request(url, headers={"User-Agent": "PianoMIDIViewer"})
            ctx = ssl.create_default_context(cafile=certifi.where())
            with urlopen(req, timeout=10, context=ctx) as resp:
                data = json.loads(resp.read().decode())
            tag = data.get("tag_name", "")
            latest = tag.lstrip("v")
            if latest and self._is_newer(latest, VERSION):
                self.result.emit(
                    tr("Version {} available").format(latest),
                    "https://skoomabwoy.codeberg.page/piano-midi-viewer/"
                )
            else:
                self.result.emit(tr("Up to date"), "")
        except (URLError, OSError, ValueError, KeyError):
            self.result.emit(tr("Check failed"), "")

    @staticmethod
    def _is_newer(remote, local):
        try:
            r = tuple(int(x) for x in remote.split("."))
            l = tuple(int(x) for x in local.split("."))
            return r > l
        except (ValueError, AttributeError):
            return False


class SettingsDialog(QDialog):
    """Dialog window for app configuration."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Settings"))
        # Must NOT be modal — MIDI polling runs on QTimer in the main window,
        # and a modal dialog blocks input to the parent, freezing note display.
        self.setMinimumWidth(300)
        self.main_window = parent
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)

        # LANGUAGE
        lang_layout = QHBoxLayout()
        lang_label = QLabel(tr("Language"))

        self.lang_dropdown = QComboBox()
        for code, name in LANGUAGES.items():
            self.lang_dropdown.addItem(name, code)
        lang_index = self.lang_dropdown.findData(i18n.get_current_language())
        if lang_index >= 0:
            self.lang_dropdown.setCurrentIndex(lang_index)
        self.lang_dropdown.currentIndexChanged.connect(self.language_changed)

        lang_layout.addWidget(lang_label)
        lang_layout.addStretch()
        lang_layout.addWidget(self.lang_dropdown)
        layout.addLayout(lang_layout)

        # MIDI INPUT
        midi_header = QHBoxLayout()
        midi_label = QLabel(tr("MIDI Input Device:"))
        self.midi_status = QLabel("")
        self.midi_status.setStyleSheet("color: #cc3333;")
        midi_header.addWidget(midi_label)
        midi_header.addStretch()
        midi_header.addWidget(self.midi_status)

        midi_layout = QHBoxLayout()

        self.midi_dropdown = QComboBox()
        self.populate_midi_devices()
        self.midi_dropdown.currentIndexChanged.connect(self.midi_device_changed)

        refresh_btn = QPushButton()
        refresh_btn.setToolTip(tr("Refresh MIDI device list"))
        refresh_btn.setIcon(create_refresh_icon())
        refresh_btn.setFixedSize(30, 30)
        refresh_btn.setIconSize(refresh_btn.size() * 0.7)
        refresh_btn.clicked.connect(self.refresh_midi_devices)

        midi_layout.addWidget(self.midi_dropdown, 1)
        midi_layout.addWidget(refresh_btn)

        layout.addLayout(midi_header)
        layout.addLayout(midi_layout)

        # HIGHLIGHT COLOR
        color_layout = QHBoxLayout()
        color_label = QLabel(tr("Highlight Color"))

        self.color_preview = QPushButton()
        self.color_preview.setFixedSize(30, 30)
        self.color_preview.clicked.connect(self.choose_color)
        self.update_color_preview(self.main_window.piano.highlight_color)

        color_layout.addWidget(color_label)
        color_layout.addStretch()
        color_layout.addWidget(self.color_preview)

        layout.addLayout(color_layout)

        # UI SCALE
        scale_layout = QHBoxLayout()
        scale_label = QLabel(tr("UI Scale"))

        self.scale_dropdown = QComboBox()
        scale_values = [0.50, 0.75, 1.0, 1.25, 1.50, 1.75, 2.0]
        for val in scale_values:
            self.scale_dropdown.addItem(f"{int(val * 100)}%", val)

        index = self.scale_dropdown.findData(constants.UI_SCALE_FACTOR)
        if index >= 0:
            self.scale_dropdown.setCurrentIndex(index)

        self.scale_dropdown.currentIndexChanged.connect(self.scale_changed)

        scale_layout.addWidget(scale_label)
        scale_layout.addStretch()
        scale_layout.addWidget(self.scale_dropdown)
        layout.addLayout(scale_layout)

        # SEPARATOR
        layout.addSpacing(10)

        # SHOW OCTAVE NUMBERS
        self.octave_numbers_checkbox = QCheckBox(tr("Show Octave Numbers"))
        self.octave_numbers_checkbox.setChecked(self.main_window.show_octave_numbers)
        self.octave_numbers_checkbox.stateChanged.connect(self.toggle_octave_numbers)
        layout.addWidget(self.octave_numbers_checkbox)

        # WHITE KEY NAMES
        self.white_key_names_checkbox = QCheckBox(tr("Show White Key Names"))
        self.white_key_names_checkbox.setChecked(self.main_window.show_white_key_names)
        self.white_key_names_checkbox.stateChanged.connect(self.toggle_white_key_names)
        layout.addWidget(self.white_key_names_checkbox)

        # BLACK KEY NAMES
        self.black_key_names_checkbox = QCheckBox(tr("Show Black Key Names"))
        self.black_key_names_checkbox.setChecked(self.main_window.show_black_key_names)
        self.black_key_names_checkbox.stateChanged.connect(self.toggle_black_key_names)
        layout.addWidget(self.black_key_names_checkbox)

        # BLACK KEY NOTATION DROPDOWN
        notation_layout = QHBoxLayout()
        notation_layout.setContentsMargins(20, 0, 0, 0)

        self.black_key_notation_dropdown = QComboBox()
        self.black_key_notation_dropdown.addItem(tr("♭ Flats"), "Flats")
        self.black_key_notation_dropdown.addItem(tr("♯ Sharps"), "Sharps")
        self.black_key_notation_dropdown.addItem(tr("Both"), "Both")

        current_notation = self.main_window.black_key_notation
        index = self.black_key_notation_dropdown.findData(current_notation)
        if index >= 0:
            self.black_key_notation_dropdown.setCurrentIndex(index)

        self.black_key_notation_dropdown.currentIndexChanged.connect(self.notation_changed)
        self.black_key_notation_dropdown.setEnabled(self.main_window.show_black_key_names)

        notation_layout.addWidget(self.black_key_notation_dropdown)
        layout.addLayout(notation_layout)

        # SHOW ONLY WHEN PRESSED
        self.names_when_pressed_checkbox = QCheckBox(tr("Show note names only when pressed"))
        self.names_when_pressed_checkbox.setChecked(self.main_window.show_names_when_pressed)
        self.names_when_pressed_checkbox.stateChanged.connect(self.toggle_names_when_pressed)
        names_enabled = self.main_window.show_white_key_names or self.main_window.show_black_key_names
        self.names_when_pressed_checkbox.setEnabled(names_enabled)
        layout.addWidget(self.names_when_pressed_checkbox)

        # SEPARATOR
        layout.addSpacing(10)

        # SHOW VELOCITY
        self.velocity_checkbox = QCheckBox(tr("Show Velocity"))
        self.velocity_checkbox.setChecked(self.main_window.show_velocity)
        self.velocity_checkbox.stateChanged.connect(self.toggle_velocity)
        layout.addWidget(self.velocity_checkbox)

        # BUILT-IN SOUND
        if _SOUND_AVAILABLE:
            layout.addSpacing(10)
            self.sound_checkbox = QCheckBox(tr("Built-in Sound"))
            self.sound_checkbox.setToolTip(tr("Simple test tones — not a replacement for a piano library"))
            self.sound_checkbox.setChecked(self.main_window.sound_enabled)
            self.sound_checkbox.stateChanged.connect(self.toggle_sound)
            layout.addWidget(self.sound_checkbox)

        # VERSION + CHECK FOR UPDATES
        layout.addStretch()
        version_row = QHBoxLayout()
        self.version_label = QLabel(tr("Version {}").format(VERSION))
        self.version_label.setTextFormat(Qt.TextFormat.RichText)
        self.version_label.linkActivated.connect(self._open_url)
        self.version_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        version_row.addWidget(self.version_label, 1)
        self.update_button = QPushButton(tr("Check for Updates"))
        self.update_button.setFixedWidth(self.update_button.sizeHint().width())
        self.update_button.clicked.connect(self.check_for_updates)
        version_row.addWidget(self.update_button, 0)
        layout.addLayout(version_row)

        # INFO LINK
        info_label = QLabel()
        info_label.setText(f'<a href="https://codeberg.org/skoomabwoy/piano-midi-viewer" style="color: #5094d4;">{tr("Project Info & Source Code")}</a>')
        info_label.linkActivated.connect(self._open_url)
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setTextFormat(Qt.TextFormat.RichText)
        info_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        layout.addWidget(info_label)

        # CLOSE BUTTON
        close_button = QPushButton(tr("Close"))
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

        self.setLayout(layout)

        self.adjustSize()
        self.setFixedSize(self.size())

    def populate_midi_devices(self):
        self.midi_dropdown.blockSignals(True)
        self.midi_dropdown.clear()
        devices = self.main_window.get_midi_devices()

        if not devices:
            self.midi_dropdown.addItem(tr("No MIDI devices found"))
        else:
            for device_name in devices:
                self.midi_dropdown.addItem(device_name)

        if self.main_window.current_midi_device:
            index = self.midi_dropdown.findText(self.main_window.current_midi_device)
            if index >= 0:
                self.midi_dropdown.setCurrentIndex(index)
        self.midi_dropdown.blockSignals(False)

    def refresh_midi_devices(self):
        self.populate_midi_devices()

    def midi_device_changed(self, index):
        device_name = self.midi_dropdown.currentText()
        if device_name and device_name != tr("No MIDI devices found"):
            if self.main_window.connect_midi_device(device_name):
                self.midi_status.setText("")
            else:
                self.midi_status.setText(tr("Device not found"))
                QTimer.singleShot(3000, lambda: self.midi_status.setText(""))
                self.populate_midi_devices()

    def choose_color(self):
        color = QColorDialog.getColor(
            self.main_window.piano.highlight_color,
            self,
            tr("Choose Highlight Color")
        )
        if color.isValid():
            self.main_window.piano.highlight_color = color
            self.update_color_preview(color)
            self.main_window.piano.update()
            self.main_window.update_sustain_button_visual()
            self.main_window.update_pencil_button_visual()
            if self.main_window.piano.glow_left_plus:
                self.main_window.apply_button_glow(self.main_window.left_plus_btn, True)
            if self.main_window.piano.glow_right_plus:
                self.main_window.apply_button_glow(self.main_window.right_plus_btn, True)
            self.main_window.save_settings()

    def update_color_preview(self, color):
        radius = 15
        self.color_preview.setStyleSheet(
            f"background-color: {color.name()}; border: 1px solid #999; border-radius: {radius}px;"
        )

    def scale_changed(self, index):
        new_scale = self.scale_dropdown.currentData()
        if new_scale != constants.UI_SCALE_FACTOR:
            self.close()
            self.main_window.apply_scale(new_scale)
            self.main_window.open_settings()

    def language_changed(self, index):
        new_lang = self.lang_dropdown.currentData()
        if new_lang != i18n.get_current_language():
            self.close()
            self.main_window.apply_language(new_lang)
            self.main_window.open_settings()

    def toggle_octave_numbers(self, state):
        self.main_window.show_octave_numbers = (state == Qt.CheckState.Checked.value)
        self.main_window.piano.update()
        self.main_window.save_settings()

    def toggle_white_key_names(self, state):
        self.main_window.show_white_key_names = (state == Qt.CheckState.Checked.value)
        names_enabled = self.main_window.show_white_key_names or self.main_window.show_black_key_names
        self.names_when_pressed_checkbox.setEnabled(names_enabled)
        self.main_window.piano.update()
        self.main_window.save_settings()

    def toggle_black_key_names(self, state):
        self.main_window.show_black_key_names = (state == Qt.CheckState.Checked.value)
        self.black_key_notation_dropdown.setEnabled(self.main_window.show_black_key_names)
        names_enabled = self.main_window.show_white_key_names or self.main_window.show_black_key_names
        self.names_when_pressed_checkbox.setEnabled(names_enabled)
        self.main_window.piano.update()
        self.main_window.save_settings()

    def notation_changed(self, index):
        notation = self.black_key_notation_dropdown.currentData()
        self.main_window.black_key_notation = notation
        self.main_window.piano.update()
        self.main_window.save_settings()

    def toggle_names_when_pressed(self, state):
        self.main_window.show_names_when_pressed = (state == Qt.CheckState.Checked.value)
        self.main_window.piano.update()
        self.main_window.save_settings()

    def toggle_velocity(self, state):
        self.main_window.show_velocity = (state == Qt.CheckState.Checked.value)
        self.main_window.piano.update()
        self.main_window.save_settings()

    def toggle_sound(self, state):
        enabled = (state == Qt.CheckState.Checked.value)
        self.main_window.sound_enabled = enabled
        if self.main_window.synth:
            if enabled:
                self.main_window.synth.start()
            else:
                self.main_window.synth.stop()
        self.main_window.save_settings()

    def check_for_updates(self):
        self.update_button.setEnabled(False)
        self.update_button.setText(tr("Checking..."))
        self._update_checker = UpdateChecker()
        self._update_checker.result.connect(self._on_update_result)
        self._update_checker.start()

    def _on_update_result(self, text, url):
        self.update_button.setEnabled(True)
        self.update_button.setText(tr("Check for Updates"))
        if url:
            self.version_label.setText(f'<a href="{url}" style="color: #5094d4;">{text}</a>')
        else:
            self.version_label.setText(text)
            QTimer.singleShot(constants.STATUS_MESSAGE_DURATION, self._restore_version_label)

    def _restore_version_label(self):
        self.version_label.setText(tr("Version {}").format(VERSION))

    def _open_url(self, url):
        """Opens a URL in the default browser, stripping bundled env vars."""
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(('LD_', 'QT_', 'QML', 'PYTHON'))
               and k not in ('APPIMAGE', 'APPDIR', 'ARGV0', 'OWD')}
        try:
            subprocess.Popen(['xdg-open', url], env=env)
        except FileNotFoundError:
            webbrowser.open(url)
