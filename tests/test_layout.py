"""Tests for the letterbox keyboard fitting (fit_keyboard_box).

Pure geometry — the proportion limits are enforced here instead of by
programmatically resizing the window, so this math is what guarantees keys
never look too stretched or too squat.
"""

import pytest

from piano_viewer.helpers import fit_keyboard_box
from piano_viewer.constants import (
    KEYBOARD_CANVAS_MARGIN, MIN_HEIGHT_RATIO, MAX_HEIGHT_RATIO,
)

N = 21  # white keys in the default 3-octave range
M = KEYBOARD_CANVAS_MARGIN


def ratio(box):
    _, _, _, _, white_w, white_h = box
    return white_h / white_w


def test_within_limits_fills_area_exactly():
    """A well-proportioned area letterboxes nothing — canvas == area."""
    w, h = 2 * M + N * 40, 2 * M + 40 * 4.5  # ratio 4.5, inside [3, 6]
    box = fit_keyboard_box(w, h, N)
    cx, cy, cw, ch, white_w, white_h = box
    assert (cx, cy) == (0, 0)
    assert (cw, ch) == (w, h)
    assert white_w == pytest.approx(40)
    assert white_h == pytest.approx(40 * 4.5)


def test_too_tall_clamps_height_and_centers_vertically():
    w, h = 2 * M + N * 40, 2 * M + 40 * 12  # ratio 12 >> max
    box = fit_keyboard_box(w, h, N)
    cx, cy, cw, ch, white_w, white_h = box
    assert ratio(box) == pytest.approx(MAX_HEIGHT_RATIO)
    assert white_w == pytest.approx(40)          # width untouched
    assert cw == pytest.approx(w) and cx == pytest.approx(0)
    assert ch < h
    assert cy == pytest.approx((h - ch) / 2)     # vertical slack split evenly


def test_too_squat_clamps_width_and_centers_horizontally():
    w, h = 2 * M + N * 100, 2 * M + 100  # ratio 1 << min
    box = fit_keyboard_box(w, h, N)
    cx, cy, cw, ch, white_w, white_h = box
    assert ratio(box) == pytest.approx(MIN_HEIGHT_RATIO)
    assert white_h == pytest.approx(100)         # height untouched
    assert ch == pytest.approx(h) and cy == pytest.approx(0)
    assert cw < w
    assert cx == pytest.approx((w - cw) / 2)     # horizontal slack split evenly


def test_exact_limits_are_not_letterboxed():
    for r in (MIN_HEIGHT_RATIO, MAX_HEIGHT_RATIO):
        w, h = 2 * M + N * 30, 2 * M + 30 * r
        cx, cy, cw, ch, _, _ = fit_keyboard_box(w, h, N)
        assert (cw, ch) == (pytest.approx(w), pytest.approx(h))


def test_degenerate_areas_return_none():
    assert fit_keyboard_box(0, 0, N) is None
    assert fit_keyboard_box(2 * M, 100, N) is None    # no inner width
    assert fit_keyboard_box(100, 2 * M, N) is None    # no inner height
    assert fit_keyboard_box(500, 200, 0) is None      # no keys


def test_ratio_always_within_limits():
    """Property check over a grid of window shapes."""
    for w in range(80, 2000, 173):
        for h in range(60, 1200, 97):
            box = fit_keyboard_box(w, h, N)
            if box is None:
                continue
            assert MIN_HEIGHT_RATIO - 1e-9 <= ratio(box) <= MAX_HEIGHT_RATIO + 1e-9
            cx, cy, cw, ch, _, _ = box
            # canvas stays inside the area
            assert cx >= -1e-9 and cy >= -1e-9
            assert cx + cw <= w + 1e-9 and cy + ch <= h + 1e-9
