"""Tests for the wavetable synthesizer (pure logic — no audio stream)."""

import math

import pytest

from piano_viewer.synth import PianoSynthesizer, _HARMONIC_PROFILES, band_blend
from piano_viewer.constants import LOUDNESS_BY_NOTE, MIDI_NOTE_MIN, MIDI_NOTE_MAX


@pytest.fixture
def synth():
    s = PianoSynthesizer()
    s._wavetables = s._build_wavetables()
    s._stream = object()  # pretend the stream is open so note_on works
    return s


def test_loudness_table_covers_full_range():
    assert len(LOUDNESS_BY_NOTE) == MIDI_NOTE_MAX - MIDI_NOTE_MIN + 1


def test_profiles_cover_full_range_in_order():
    max_notes = [m for m, _ in _HARMONIC_PROFILES]
    assert max_notes == sorted(max_notes)
    assert max_notes[-1] == MIDI_NOTE_MAX


def test_no_profile_aliases():
    """The top partial of the highest note in each band stays below Nyquist."""
    for max_note, harmonics in _HARMONIC_PROFILES:
        f0 = 440.0 * 2 ** ((max_note - 69) / 12)
        assert f0 * len(harmonics) < PianoSynthesizer.SAMPLE_RATE / 2


def _effective_spectrum(note):
    """Normalized partial amplitudes as heard: the profile crossfade."""
    low, high, t = band_blend(note)
    a_low = _HARMONIC_PROFILES[low][1]
    a_high = _HARMONIC_PROFILES[high][1]
    n_low, n_high = sum(a_low), sum(a_high)
    length = max(len(a_low), len(a_high))
    return [(1 - t) * (a_low[h] / n_low if h < len(a_low) else 0.0)
            + t * (a_high[h] / n_high if h < len(a_high) else 0.0)
            for h in range(length)]


def test_band_blend_bounds():
    assert band_blend(MIDI_NOTE_MIN) == (0, 0, 0.0)
    assert band_blend(MIDI_NOTE_MAX)[2] in (0.0, 1.0)
    for note in range(MIDI_NOTE_MIN, MIDI_NOTE_MAX + 1):
        low, high, t = band_blend(note)
        assert 0.0 <= t <= 1.0
        assert high in (low, low + 1)


def test_timbre_changes_smoothly_between_adjacent_notes():
    """No audible spectrum step between neighboring semitones (the E1->F1
    band seam used to make the transition sound like a resolution)."""
    for note in range(MIDI_NOTE_MIN, MIDI_NOTE_MAX):
        a = _effective_spectrum(note)
        b = _effective_spectrum(note + 1)
        length = max(len(a), len(b))
        step = max(abs((a[h] if h < len(a) else 0.0) - (b[h] if h < len(b) else 0.0))
                   for h in range(length))
        assert step < 0.03, f"partial amplitude jump {step:.3f} at {note}->{note + 1}"


def test_wavetables_normalized(synth):
    """Sum-normalization keeps every table's peak below 1."""
    assert len(synth._wavetables) == len(_HARMONIC_PROFILES)
    for table in synth._wavetables:
        assert max(abs(x) for x in table) < 1.0


def test_note_on_out_of_88_key_range_is_clamped(synth):
    """MIDI allows notes 0..127; gains outside A0..C8 clamp, not crash."""
    synth.note_on(0)
    synth.note_on(127)
    assert 0 in synth._voices and 127 in synth._voices


def test_voice_stealing_caps_polyphony(synth):
    for note in range(21, 21 + PianoSynthesizer.MAX_VOICES + 3):
        synth.note_on(note)
    assert len(synth._voices) == PianoSynthesizer.MAX_VOICES
    assert 21 not in synth._voices  # oldest voices were stolen


def test_all_notes_off_releases_everything(synth):
    synth.note_on(60)
    synth.note_on(64)
    synth.set_sustain(True)
    synth.note_off(60)  # held by the pedal
    synth.all_notes_off()
    assert not synth._sustained
    assert all(v.env_stage == 'release' for v in synth._voices.values())


def _render(synth, buffers=1, frames=256):
    out = bytearray(frames * 4)
    for _ in range(buffers):
        synth._callback(out, frames, None, None)
    return out


def test_released_voice_reaches_done_and_is_reaped(synth):
    synth.note_on(60)
    synth.note_off(60)
    # 100 ms release at 44.1 kHz is ~4410 samples; render well past it.
    _render(synth, buffers=40)
    assert 60 not in synth._voices
    assert not synth._dying


def test_render_output_is_finite_and_bounded(synth):
    for note in (21, 24, 28, 31, 36, 40, 43, 48, 60, 72, 84, 96):
        synth.note_on(note)
    out = _render(synth, buffers=20)
    import array
    samples = array.array('f', bytes(out))
    assert all(math.isfinite(x) for x in samples)
    assert max(abs(x) for x in samples) <= 1.0
