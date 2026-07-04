"""Regenerates LOUDNESS_BY_NOTE in piano_viewer/constants.py.

The synth equalizes perceived loudness across the keyboard using a per-note
gain table derived from a psychoacoustic model:

- A-weighting (IEC 61672) approximates how loud each partial actually sounds.
- A 12 dB/oct high-pass below 250 Hz models a cheap laptop/classroom speaker.
- Each note's gain is chosen so the small-speaker perceived level follows the
  target curve below, then capped so the same note is never louder than
  FULLRANGE_CAP_DB on full-range speakers (keeps the bass from booming on
  good hardware).

Run after changing _HARMONIC_PROFILES in piano_viewer/synth.py, then paste the
printed table into constants.py:

    python tools/generate_loudness_table.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from piano_viewer.synth import _HARMONIC_PROFILES  # noqa: E402
from piano_viewer.constants import MIDI_NOTE_MIN, MIDI_NOTE_MAX  # noqa: E402

BASE_AMPLITUDE = 0.15        # must match _Voice's base amplitude in synth.py
SPEAKER_KNEE_HZ = 250.0      # small-speaker high-pass corner
FULLRANGE_CAP_DB = -24.0     # loudness ceiling on full-range speakers
MID_TARGET_DB = -26.0        # perceived level for the flat teaching range


def target_db(note):
    """Desired small-speaker perceived level per note.

    Flat through the main teaching range; the bottom tapers off gently
    (physics limits what a small speaker can do at 30 Hz) and the top rolls
    off so high notes never pierce.
    """
    if note < 48:
        return MID_TARGET_DB - (48 - note) * (7.0 / 27)   # -33 dB at A0
    if note <= 92:
        return MID_TARGET_DB
    return MID_TARGET_DB - (note - 92) * (8.0 / 16)       # -34 dB at C8


def a_weight(f):
    """Linear-scale A-weighting factor, normalized to 1.0 at 1 kHz."""
    f2 = f * f
    num = (12194 ** 2) * f2 * f2
    den = ((f2 + 20.6 ** 2) * math.sqrt((f2 + 107.7 ** 2) * (f2 + 737.9 ** 2))
           * (f2 + 12194 ** 2))
    return (num / den) / 0.7943


def speaker(f):
    """Cheap-speaker rolloff: 12 dB/oct high-pass below the knee."""
    return 1.0 if f >= SPEAKER_KNEE_HZ else (f / SPEAKER_KNEE_HZ) ** 2


def profile_for(note):
    for max_note, harmonics in _HARMONIC_PROFILES:
        if note <= max_note:
            return harmonics
    return _HARMONIC_PROFILES[-1][1]


def shape_rms(note, small_speaker):
    """Perceived RMS of a note's sum-normalized wavetable at unit gain."""
    f0 = 440.0 * 2 ** ((note - 69) / 12)
    harmonics = profile_for(note)
    norm = sum(harmonics)
    return math.sqrt(sum(
        (amp / norm * a_weight(h * f0) * (speaker(h * f0) if small_speaker else 1.0)) ** 2
        for h, amp in enumerate(harmonics, 1)) / 2)


def main():
    gains = []
    for note in range(MIDI_NOTE_MIN, MIDI_NOTE_MAX + 1):
        g_small = 10 ** (target_db(note) / 20) / (BASE_AMPLITUDE * shape_rms(note, True))
        g_cap = 10 ** (FULLRANGE_CAP_DB / 20) / (BASE_AMPLITUDE * shape_rms(note, False))
        gains.append(min(g_small, g_cap))

    # Light 3-point smoothing in dB to iron out steps at profile boundaries.
    db = [20 * math.log10(g) for g in gains]
    smoothed = [db[0]] + [(db[i - 1] + db[i] + db[i + 1]) / 3
                          for i in range(1, len(db) - 1)] + [db[-1]]
    gains = [10 ** (d / 20) for d in smoothed]

    small = [20 * math.log10(BASE_AMPLITUDE * g * shape_rms(n, True))
             for n, g in zip(range(MIDI_NOTE_MIN, MIDI_NOTE_MAX + 1), gains)]
    jumps = max(abs(b - a) for a, b in zip(small, small[1:]))
    print(f"# small-speaker spread: {max(small) - min(small):.1f} dB, "
          f"worst adjacent jump: {jumps:.2f} dB")
    print("LOUDNESS_BY_NOTE = [")
    for i in range(0, len(gains), 8):
        print("    " + ", ".join(f"{g:.3f}" for g in gains[i:i + 8]) + ",")
    print("]")


if __name__ == "__main__":
    main()
