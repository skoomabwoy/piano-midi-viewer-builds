"""Tests for MIDI note helper functions.

These are pure logic functions with no GUI dependencies.
"""
from piano_viewer import (
    is_black_key,
    count_white_keys,
    get_white_key_index,
    get_left_white_key,
)


# ---- is_black_key ----

class TestIsBlackKey:
    """Test MIDI note classification into black/white keys."""

    def test_c_is_white(self):
        # C4 (Middle C) = MIDI 60
        assert is_black_key(60) is False

    def test_all_white_keys_in_one_octave(self):
        # C=0, D=2, E=4, F=5, G=7, A=9, B=11 (relative to octave)
        # Using octave 4 (MIDI 60-71)
        white_notes = [60, 62, 64, 65, 67, 69, 71]
        for note in white_notes:
            assert is_black_key(note) is False, f"MIDI {note} should be white"

    def test_all_black_keys_in_one_octave(self):
        # C#=1, D#=3, F#=6, G#=8, A#=10 (relative to octave)
        # Using octave 4 (MIDI 60-71)
        black_notes = [61, 63, 66, 68, 70]
        for note in black_notes:
            assert is_black_key(note) is True, f"MIDI {note} should be black"

    def test_pattern_repeats_across_octaves(self):
        # C# should be black in every octave
        for octave_start in range(0, 120, 12):
            assert is_black_key(octave_start + 1) is True

    def test_lowest_piano_key_a0(self):
        # A0 = MIDI 21, white key
        assert is_black_key(21) is False

    def test_highest_piano_key_c8(self):
        # C8 = MIDI 108, white key
        assert is_black_key(108) is False

    def test_five_black_keys_per_octave(self):
        count = sum(1 for n in range(60, 72) if is_black_key(n))
        assert count == 5

    def test_seven_white_keys_per_octave(self):
        count = sum(1 for n in range(60, 72) if not is_black_key(n))
        assert count == 7


# ---- count_white_keys ----

class TestCountWhiteKeys:
    """Test white key counting across MIDI ranges."""

    def test_single_octave(self):
        # C4 to B4 (MIDI 60-71) = 7 white keys
        assert count_white_keys(60, 71) == 7

    def test_two_octaves(self):
        # C4 to B5 (MIDI 60-83) = 14 white keys
        assert count_white_keys(60, 83) == 14

    def test_single_white_key(self):
        # Just C4
        assert count_white_keys(60, 60) == 1

    def test_single_black_key(self):
        # Just C#4
        assert count_white_keys(61, 61) == 0

    def test_default_range(self):
        # Default: C3 to B5 (MIDI 48-83) = 3 octaves = 21 white keys
        assert count_white_keys(48, 83) == 21

    def test_full_piano_range(self):
        # A0 to C8 (MIDI 21-108)
        # A0-B0 = 2 white (A, B), then 7 full octaves (C1-B7) = 49, plus C8 = 1
        # Total = 52
        assert count_white_keys(21, 108) == 52

    def test_partial_octave(self):
        # C4 to E4 (MIDI 60-64) = 3 white keys (C, D, E)
        assert count_white_keys(60, 64) == 3


# ---- get_white_key_index ----

class TestGetWhiteKeyIndex:
    """Test white key position indexing."""

    def test_first_key_is_zero(self):
        # C4 starting from C4 = index 0
        assert get_white_key_index(60, 60) == 0

    def test_second_white_key(self):
        # D4 (MIDI 62) starting from C4 (MIDI 60) = index 1
        # Skips C#4 (61) which is black
        assert get_white_key_index(62, 60) == 1

    def test_e_is_third(self):
        # E4 (MIDI 64) starting from C4 = index 2
        assert get_white_key_index(64, 60) == 2

    def test_b_is_seventh(self):
        # B4 (MIDI 71) starting from C4 = index 6
        assert get_white_key_index(71, 60) == 6

    def test_across_octave(self):
        # C5 (MIDI 72) starting from C4 (MIDI 60) = index 7
        assert get_white_key_index(72, 60) == 7


# ---- get_left_white_key ----

class TestGetLeftWhiteKey:
    """Test finding the white key to the left of a black key."""

    def test_c_sharp_left_is_c(self):
        # C#4 (61) -> C4 (60)
        assert get_left_white_key(61, 48) == 60

    def test_d_sharp_left_is_d(self):
        # D#4 (63) -> D4 (62)
        assert get_left_white_key(63, 48) == 62

    def test_f_sharp_left_is_f(self):
        # F#4 (66) -> F4 (65)
        assert get_left_white_key(66, 48) == 65

    def test_g_sharp_left_is_g(self):
        # G#4 (68) -> G4 (67)
        assert get_left_white_key(68, 48) == 67

    def test_a_sharp_left_is_a(self):
        # A#4 (70) -> A4 (69)
        assert get_left_white_key(70, 48) == 69

    def test_at_start_boundary(self):
        # C#4 (61) with start_note=60 -> C4 (60)
        assert get_left_white_key(61, 60) == 60

    def test_returns_start_when_no_white_key_left(self):
        # C#4 (61) with start_note=61 -> returns start_note
        assert get_left_white_key(61, 61) == 61
