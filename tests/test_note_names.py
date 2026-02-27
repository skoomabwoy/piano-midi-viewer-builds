"""Tests for note naming and octave number functions."""
from piano_viewer import get_note_name, get_octave_number, get_black_key_name


# ---- get_note_name ----

class TestGetNoteName:
    """Test MIDI note to note name conversion."""

    def test_middle_c(self):
        assert get_note_name(60) == 'C'

    def test_all_white_notes_in_octave(self):
        expected = {60: 'C', 62: 'D', 64: 'E', 65: 'F', 67: 'G', 69: 'A', 71: 'B'}
        for midi, name in expected.items():
            assert get_note_name(midi) == name, f"MIDI {midi} should be {name}"

    def test_black_keys_return_empty_string(self):
        black_notes = [61, 63, 66, 68, 70]  # C#, D#, F#, G#, A# in octave 4
        for note in black_notes:
            assert get_note_name(note) == '', f"MIDI {note} (black key) should return ''"

    def test_a0_lowest_piano_key(self):
        assert get_note_name(21) == 'A'

    def test_c8_highest_piano_key(self):
        assert get_note_name(108) == 'C'

    def test_same_name_across_octaves(self):
        # All C notes should return 'C'
        for c_note in [24, 36, 48, 60, 72, 84, 96]:
            assert get_note_name(c_note) == 'C'


# ---- get_octave_number ----

class TestGetOctaveNumber:
    """Test MIDI note to octave number conversion."""

    def test_middle_c_is_octave_4(self):
        assert get_octave_number(60) == 4

    def test_a0(self):
        # A0 = MIDI 21, octave 0
        assert get_octave_number(21) == 0

    def test_c8(self):
        # C8 = MIDI 108, octave 8
        assert get_octave_number(108) == 8

    def test_octave_boundary(self):
        # B3 = MIDI 59 (octave 3), C4 = MIDI 60 (octave 4)
        assert get_octave_number(59) == 3
        assert get_octave_number(60) == 4

    def test_midi_zero(self):
        # MIDI 0 = C-1
        assert get_octave_number(0) == -1

    def test_all_notes_in_octave_same_number(self):
        # C4 through B4 (60-71) should all be octave 4
        for note in range(60, 72):
            assert get_octave_number(note) == 4


# ---- get_black_key_name ----

class TestGetBlackKeyName:
    """Test black key naming with different notation types."""

    def test_c_sharp_sharps_notation(self):
        sharp, flat = get_black_key_name(61, "Sharps")
        assert sharp == 'C♯'
        assert flat is None

    def test_c_sharp_flats_notation(self):
        sharp, flat = get_black_key_name(61, "Flats")
        assert sharp == 'D♭'
        assert flat is None

    def test_c_sharp_both_notation(self):
        sharp, flat = get_black_key_name(61, "Both")
        assert sharp == 'C♯'
        assert flat == 'D♭'

    def test_all_black_keys_sharps(self):
        expected = {
            61: 'C♯', 63: 'D♯', 66: 'F♯', 68: 'G♯', 70: 'A♯'
        }
        for midi, name in expected.items():
            sharp, flat = get_black_key_name(midi, "Sharps")
            assert sharp == name, f"MIDI {midi} sharp should be {name}"

    def test_all_black_keys_flats(self):
        expected = {
            61: 'D♭', 63: 'E♭', 66: 'G♭', 68: 'A♭', 70: 'B♭'
        }
        for midi, name in expected.items():
            sharp, flat = get_black_key_name(midi, "Flats")
            assert sharp == name, f"MIDI {midi} flat should be {name}"

    def test_white_key_returns_none_none(self):
        assert get_black_key_name(60, "Sharps") == (None, None)

    def test_white_key_any_notation(self):
        for notation in ["Sharps", "Flats", "Both"]:
            assert get_black_key_name(60, notation) == (None, None)

    def test_same_name_across_octaves(self):
        # C#4 (61) and C#5 (73) should have the same name
        assert get_black_key_name(61, "Sharps") == get_black_key_name(73, "Sharps")
