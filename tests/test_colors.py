"""Tests for color utility functions.

These tests need a QApplication instance (provided by the qapp fixture)
because they work with QColor objects.
"""
import pytest
from PyQt6.QtGui import QColor

from piano_viewer import get_text_color_for_highlight, blend_colors


# ---- get_text_color_for_highlight ----

class TestGetTextColorForHighlight:
    """Test luminance-based text contrast calculation."""

    def test_white_background_gives_black_text(self, qapp):
        result = get_text_color_for_highlight(QColor(255, 255, 255))
        assert result.red() == 0 and result.green() == 0 and result.blue() == 0

    def test_black_background_gives_white_text(self, qapp):
        result = get_text_color_for_highlight(QColor(0, 0, 0))
        assert result.red() == 255 and result.green() == 255 and result.blue() == 255

    def test_bright_yellow_gives_black_text(self, qapp):
        # Yellow (255, 255, 0) is very bright
        result = get_text_color_for_highlight(QColor(255, 255, 0))
        assert result.red() == 0  # black text

    def test_dark_blue_gives_white_text(self, qapp):
        # Dark blue (0, 0, 128) is dark
        result = get_text_color_for_highlight(QColor(0, 0, 128))
        assert result.red() == 255  # white text

    def test_arch_blue_default_highlight(self, qapp):
        # Arch Blue #5094d4 = (80, 148, 212) — medium brightness
        result = get_text_color_for_highlight(QColor(80, 148, 212))
        # Luminance = (0.299*80 + 0.587*148 + 0.114*212) / 255 ≈ 0.53
        # Just above 0.5, so black text
        assert result.red() == 0  # black text

    def test_pure_red(self, qapp):
        # Pure red (255, 0, 0) luminance = 0.299 → dark → white text
        result = get_text_color_for_highlight(QColor(255, 0, 0))
        assert result.red() == 255  # white text

    def test_pure_green(self, qapp):
        # Pure green (0, 255, 0) luminance = 0.587 → bright → black text
        result = get_text_color_for_highlight(QColor(0, 255, 0))
        assert result.red() == 0  # black text


# ---- blend_colors ----

class TestBlendColors:
    """Test linear color interpolation."""

    def test_factor_zero_returns_base(self, qapp):
        base = QColor(100, 100, 100)
        target = QColor(200, 200, 200)
        result = blend_colors(base, target, 0.0)
        assert result.red() == 100
        assert result.green() == 100
        assert result.blue() == 100

    def test_factor_one_returns_target(self, qapp):
        base = QColor(100, 100, 100)
        target = QColor(200, 200, 200)
        result = blend_colors(base, target, 1.0)
        assert result.red() == 200
        assert result.green() == 200
        assert result.blue() == 200

    def test_factor_half_returns_midpoint(self, qapp):
        base = QColor(0, 0, 0)
        target = QColor(200, 100, 50)
        result = blend_colors(base, target, 0.5)
        assert result.red() == 100
        assert result.green() == 50
        assert result.blue() == 25

    def test_black_to_white_halfway(self, qapp):
        result = blend_colors(QColor(0, 0, 0), QColor(255, 255, 255), 0.5)
        # int(127.5) = 127
        assert result.red() == 127

    def test_velocity_minimum_factor(self, qapp):
        # Minimum velocity factor in the app is 0.3
        base = QColor(252, 252, 252)  # white key color
        target = QColor(80, 148, 212)  # arch blue
        result = blend_colors(base, target, 0.3)
        # Should be visibly tinted but still mostly white
        assert result.red() < 252
        assert result.red() > target.red()

    def test_same_color_any_factor(self, qapp):
        color = QColor(128, 128, 128)
        result = blend_colors(color, color, 0.7)
        assert result.red() == 128
        assert result.green() == 128
        assert result.blue() == 128
