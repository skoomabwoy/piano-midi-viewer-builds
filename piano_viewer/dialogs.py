"""Error dialog with copy-to-clipboard support."""

from datetime import datetime

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QPlainTextEdit,
    QApplication,
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import QTimer

from piano_viewer import VERSION
import piano_viewer.constants as constants
from piano_viewer.constants import scaled
from piano_viewer.i18n import tr
from piano_viewer.helpers import make_button_style


def apply_dialog_scale(dialog):
    """Scales a dialog's base font by the app UI scale factor.

    The main window scales through explicit pixel math; dialogs are regular
    layouts, so scaling the font (which children inherit) is what makes them
    follow — pixel sizes inside each dialog go through scaled() individually.
    """
    if constants.UI_SCALE_FACTOR != 1.0:
        font = dialog.font()
        font.setPointSizeF(font.pointSizeF() * constants.UI_SCALE_FACTOR)
        dialog.setFont(font)


class ErrorDialog(QDialog):
    """Dialog for displaying errors with copy-to-clipboard support."""

    def __init__(self, title, details, parent=None, reset_callback=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        apply_dialog_scale(self)
        self.setMinimumWidth(scaled(450))
        self.setMinimumHeight(scaled(250))
        self.reset_callback = reset_callback

        layout = QVBoxLayout()
        layout.setSpacing(scaled(10))

        header = QLabel(tr("Something went wrong. You can copy the details "
                        "below and report this issue."))
        header.setWordWrap(True)
        layout.addWidget(header)

        report_lines = [
            f"Piano MIDI Viewer v{VERSION}",
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"",
            f"Error: {details}",
        ]
        self.report_text = "\n".join(report_lines)

        self.text_area = QPlainTextEdit()
        self.text_area.setPlainText(self.report_text)
        self.text_area.setReadOnly(True)
        self.text_area.setFont(QFont("monospace", max(7, scaled(10))))
        layout.addWidget(self.text_area)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        if reset_callback:
            reset_btn = QPushButton(tr("Reset Settings"))
            reset_btn.setFixedHeight(scaled(32))
            reset_btn.setStyleSheet(make_button_style())
            reset_btn.clicked.connect(self._reset_settings)
            button_layout.addWidget(reset_btn)

        self.copy_btn = QPushButton(tr("Copy to Clipboard"))
        self.copy_btn.setFixedHeight(scaled(32))
        self.copy_btn.setStyleSheet(make_button_style())
        self.copy_btn.clicked.connect(self._copy_to_clipboard)

        close_btn = QPushButton(tr("Close"))
        close_btn.setFixedHeight(scaled(32))
        close_btn.setStyleSheet(make_button_style())
        close_btn.clicked.connect(self.close)

        button_layout.addWidget(self.copy_btn)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def _copy_to_clipboard(self):
        QApplication.clipboard().setText(self.report_text)
        self.copy_btn.setText(tr("Copied!"))
        QTimer.singleShot(1500, lambda: self.copy_btn.setText(tr("Copy to Clipboard")))

    def _reset_settings(self):
        if self.reset_callback:
            self.reset_callback()
        self.close()
