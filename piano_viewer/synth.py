"""Built-in wavetable synthesizer (optional, requires sounddevice).

Provides simple piano-like tones using additive synthesis with per-range
wavetables. The feature is entirely optional — if sounddevice is not
installed, nothing in this module runs.
"""

import math
import array
import random
import threading

from piano_viewer import _SOUND_AVAILABLE, log
from piano_viewer.constants import (
    MIDI_NOTE_MIN, MIDI_NOTE_MAX, LOUDNESS_BY_NOTE,
)

if _SOUND_AVAILABLE:
    import sounddevice as _sd


# Envelope timing (seconds). A short attack + brief decay to a sustain floor
# turns the flat "organ hold" into a tone with a little bloom, and the attack
# ramp (plus the fast release used when a voice is stolen or retriggered)
# removes the onset and voice-steal clicks.
#
# The attack is linear; decay and release are exponential (one-pole), which
# sounds natural where linear ramps have an audible "corner" — amplitude
# perception is logarithmic. _DECAY_TIME is time-to-settle at the sustain
# level (within 1%); the release times are time to fall 60 dB.
_ATTACK_TIME = 0.008
_DECAY_TIME = 0.30
_RELEASE_TIME = 0.10
_FAST_RELEASE_TIME = 0.006
_SUSTAIN_RATIO = 0.7   # sustain level as a fraction of the attack peak
_DONE_LEVEL = 5e-4     # release ends below this level (inaudible, < -66 dB)


class _Voice:
    """A single synthesizer voice: phase accumulator + ADSR-lite envelope.

    Envelope stages: attack -> decay -> sustain -> release -> done. The short
    attack ramp (and the fast release used when a voice is stolen or retriggered)
    keep note onsets and cutoffs click-free; the brief decay to a sustain floor
    gives the tone a bit of life instead of a dead-flat organ hold.
    """
    __slots__ = ('phase', 'phase_inc', 'amplitude', 'wavetable', 'wavetable2',
                 'blend', 'env_stage', 'env_level', 'peak', 'sustain_level',
                 'attack_rate', 'decay_coef', 'decay_floor',
                 'release_coef', 'fast_release_coef')

    def __init__(self, freq, level, wavetable, sample_rate, loudness=1.0,
                 wavetable2=None, blend=0.0):
        # Random start phase: chord voices launched together would otherwise
        # be phase-locked, making simple-ratio intervals (octaves, fifths)
        # sound arbitrarily louder or thinner depending on fixed alignment.
        # Randomizing evens out chord loudness and lowers worst-case peaks.
        self.phase = random.random()
        self.phase_inc = freq / sample_rate
        self.amplitude = 0.15 * loudness
        # Crossfaded pair: the rendered sample interpolates between the two
        # neighboring profile wavetables by `blend`, which is equivalent to
        # interpolating the harmonic amplitudes themselves (mixing is linear).
        self.wavetable = wavetable
        self.wavetable2 = wavetable2 if wavetable2 is not None else wavetable
        self.blend = blend

        self.peak = level
        self.sustain_level = level * _SUSTAIN_RATIO
        self.env_stage = 'attack'
        self.env_level = 0.0

        self.attack_rate = self.peak / (_ATTACK_TIME * sample_rate)
        # One-pole coefficients: level approaches its target by this factor
        # per sample. 0.01 ** (1/n) settles within 1% over n samples;
        # 1e-3 ** (1/n) falls 60 dB over n samples.
        self.decay_coef = 0.01 ** (1.0 / (_DECAY_TIME * sample_rate))
        self.decay_floor = 0.01 * (self.peak - self.sustain_level)
        self.release_coef = 1e-3 ** (1.0 / (_RELEASE_TIME * sample_rate))
        self.fast_release_coef = 1e-3 ** (1.0 / (_FAST_RELEASE_TIME * sample_rate))

    def release(self, fast=False):
        """Begin the release stage. `fast` ramps out in a few ms (steal/retrigger)."""
        if fast:
            self.release_coef = self.fast_release_coef
        self.env_stage = 'release'

    def is_finished(self):
        return self.env_stage == 'done'


# Harmonic profiles per pitch range: (highest MIDI note, partial amplitudes).
#
# Voiced for clarity on any speaker rather than piano realism:
# - Bottom ranges use "missing fundamental" voicing — the fundamental is cut
#   and the energy moved into partials 2..10, which small speakers can actually
#   reproduce (a laptop speaker is near-silent below ~250 Hz). The ear
#   reconstructs the pitch from the harmonic spacing, so the note reads the
#   same but is far more audible — and less subby on full-range speakers.
# - The fundamental fades back in gradually toward the midrange; adjacent
#   bands are shaped to match at the boundary so neighboring semitones never
#   jump in brightness (important when comparing notes by ear).
# - Top ranges keep a 2nd partial: the octave harmonic anchors pitch identity
#   where a bare sine would sound glassy.
#
# Profiles are anchor points, not bands: each note's timbre is interpolated
# between the two neighboring profiles (voices crossfade their wavetables),
# so the harmonic balance changes smoothly per semitone. Discrete bands put
# an audible timbre step between adjacent notes at each boundary — with the
# missing-fundamental voicing, E1->F1 sounded like a resolution because F1's
# band suddenly had 50% more fundamental.
#
# Per-note loudness lives in constants.LOUDNESS_BY_NOTE (see
# tools/generate_loudness_table.py) — regenerate it after editing these.
_HARMONIC_PROFILES = [
    (28,  [0.30, 1.0, 0.95, 0.85, 0.72, 0.62, 0.54, 0.48, 0.42, 0.38]),
    (34,  [0.45, 1.0, 0.88, 0.72, 0.58, 0.48, 0.40, 0.34]),
    (40,  [0.65, 1.0, 0.75, 0.58, 0.46, 0.38]),
    (46,  [0.85, 0.85, 0.60, 0.47, 0.38]),
    (52,  [1.0, 0.62, 0.46, 0.36, 0.29]),
    (60,  [1.0, 0.52, 0.35, 0.26, 0.20]),
    (72,  [1.0, 0.50, 0.33, 0.25]),
    (84,  [1.0, 0.48, 0.28, 0.15]),
    (96,  [1.0, 0.45, 0.20]),
    (MIDI_NOTE_MAX, [1.0, 0.40, 0.15]),
]


def band_blend(note):
    """Returns (low_band, high_band, t) to interpolate profiles at `note`.

    Each profile is anchored at its max_note; between anchors t ramps 0..1.
    Notes at or below the first anchor (or above the last) use one profile
    unblended. Shared by note_on (wavetable crossfade weights) and
    tools/generate_loudness_table.py (so loudness matches the heard timbre).
    """
    anchors = [m for m, _ in _HARMONIC_PROFILES]
    if note <= anchors[0]:
        return 0, 0, 0.0
    for i in range(len(anchors) - 1):
        if note <= anchors[i + 1]:
            t = (note - anchors[i]) / (anchors[i + 1] - anchors[i])
            return i, i + 1, t
    last = len(anchors) - 1
    return last, last, 0.0


class PianoSynthesizer:
    """Wavetable synthesizer with polyphony and sustain pedal support."""
    SAMPLE_RATE = 44100
    WAVETABLE_SIZE = 4096
    MAX_VOICES = 12

    def __init__(self):
        self._voices = {}      # note -> active voice (attack/decay/sustain/release)
        self._dying = []       # voices detached from a key, finishing a fast release
        self._sustained = set()
        self.sustain_active = False
        self._lock = threading.Lock()
        self._stream = None
        self._smooth_gain = 1.0
        # Built lazily on first start() — ~100 ms we shouldn't spend at app
        # startup when sound is disabled (the synth object always exists).
        self._wavetables = None

    def _build_wavetables(self):
        """Pre-compute one wavetable per harmonic profile.

        Tables are stored as `array('f')` (packed float32) rather than Python
        lists: ~8x less memory and faster indexing in the per-sample audio loop,
        with precision that's far beyond what the output needs.
        """
        tables = []
        two_pi = 2.0 * math.pi
        for _, harmonics in _HARMONIC_PROFILES:
            table = array.array('f', bytes(self.WAVETABLE_SIZE * 4))
            norm = sum(harmonics)
            for i in range(self.WAVETABLE_SIZE):
                t = i / self.WAVETABLE_SIZE
                sample = 0.0
                for h, amp in enumerate(harmonics, 1):
                    sample += amp * math.sin(two_pi * h * t)
                table[i] = sample / norm
            tables.append(table)
        return tables

    def _wavetables_for_note(self, note):
        """Returns (table_low, table_high, blend) for the note's crossfade."""
        low, high, t = band_blend(note)
        return self._wavetables[low], self._wavetables[high], t

    def start(self):
        """Opens the audio stream (and builds the wavetables on first use)."""
        if self._stream is not None:
            return
        if self._wavetables is None:
            self._wavetables = self._build_wavetables()
        try:
            self._stream = _sd.RawOutputStream(
                samplerate=self.SAMPLE_RATE,
                channels=1,
                dtype='float32',
                callback=self._callback,
                blocksize=256,
            )
            self._stream.start()
            log.info("Built-in sound: audio stream started")
        except Exception as e:
            log.error(f"Built-in sound: failed to start audio stream: {e}")
            self._stream = None

    def stop(self):
        """Closes the audio stream."""
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
            log.info("Built-in sound: audio stream stopped")
        with self._lock:
            self._voices.clear()
            self._dying.clear()
            self._sustained.clear()
            self._smooth_gain = 1.0

    def note_on(self, note, velocity_scale=1.0):
        """Starts a new voice for the given MIDI note number."""
        if self._stream is None:
            return
        freq = 440.0 * (2.0 ** ((note - 69) / 12.0))
        # Clamp so MIDI notes outside the 88-key range reuse the nearest
        # voiced note's gain and timbre instead of indexing out of the table.
        clamped = min(max(note, MIDI_NOTE_MIN), MIDI_NOTE_MAX)
        wt, wt2, blend = self._wavetables_for_note(clamped)
        loudness = LOUDNESS_BY_NOTE[clamped - MIDI_NOTE_MIN]
        voice = _Voice(freq, velocity_scale, wt, self.SAMPLE_RATE, loudness,
                       wavetable2=wt2, blend=blend)
        with self._lock:
            self._sustained.discard(note)

            # Retiring (not deleting) the displaced voice lets it fade out over a
            # few ms instead of cutting mid-cycle, which would click.
            existing = self._voices.pop(note, None)
            if existing is not None:
                existing.release(fast=True)
                self._dying.append(existing)

            if len(self._voices) >= self.MAX_VOICES:
                # Steal the oldest voice — dict preserves insertion order (Python
                # 3.7+), so the first key started playing earliest.
                oldest_key = next(iter(self._voices))
                stolen = self._voices.pop(oldest_key)
                stolen.release(fast=True)
                self._dying.append(stolen)

            self._voices[note] = voice

    def note_off(self, note):
        """Handles key release — respects sustain pedal state."""
        with self._lock:
            if self.sustain_active:
                self._sustained.add(note)
            elif note in self._voices:
                self._voices[note].release()

    def all_notes_off(self):
        """Releases every active voice, ignoring the sustain pedal (panic).

        Used when note-off events will never arrive for currently sounding
        voices — e.g. the MIDI device unplugged mid-note, or the app switched
        into pencil mode (which swallows note-offs).
        """
        with self._lock:
            for voice in self._voices.values():
                voice.release()
            self._sustained.clear()

    def set_sustain(self, active):
        """Updates sustain pedal state. Releases held notes when pedal lifts."""
        with self._lock:
            self.sustain_active = active
        if not active:
            with self._lock:
                for note in self._sustained:
                    if note in self._voices:
                        self._voices[note].release()
                self._sustained.clear()

    def _render_voice(self, v, mix, frames):
        """Renders one voice into the float mix buffer.

        All per-sample state lives in locals for the duration of the loop (and
        the envelope is inlined) — attribute lookups and a method call per
        sample are what made the old sample-major loop expensive. Safe because
        the caller holds `self._lock`, so nothing mutates the voice mid-render.
        """
        stage = v.env_stage
        if stage == 'done':
            return

        wt = v.wavetable
        wt2 = v.wavetable2
        blend = v.blend
        wt_size = self.WAVETABLE_SIZE
        # Work in wavetable units so indexing is a plain int() per sample
        # (phase stays in [0, wt_size), no multiply or modulo needed).
        phase = v.phase * wt_size
        phase_inc = v.phase_inc * wt_size
        amp = v.amplitude
        level = v.env_level
        peak = v.peak
        sustain = v.sustain_level
        attack = v.attack_rate
        decay_coef = v.decay_coef
        decay_floor = v.decay_floor
        release_coef = v.release_coef
        scaled_level = level * amp  # constant while sustaining

        for i in range(frames):
            idx = int(phase)
            sample = wt[idx]
            mix[i] += (sample + (wt2[idx] - sample) * blend) * scaled_level
            phase += phase_inc
            if phase >= wt_size:
                phase -= wt_size

            if stage == 'sustain':
                continue
            if stage == 'attack':
                level += attack
                if level >= peak:
                    level = peak
                    stage = 'decay'
            elif stage == 'decay':
                level = sustain + (level - sustain) * decay_coef
                if level - sustain <= decay_floor:
                    level = sustain
                    stage = 'sustain'
            else:  # release
                level *= release_coef
                if level <= _DONE_LEVEL:
                    level = 0.0
                    stage = 'done'
                    break  # silent for the rest of the buffer
            scaled_level = level * amp

        v.phase = phase / wt_size
        v.env_level = level
        v.env_stage = stage

    def _callback(self, outdata, frames, time_info, status):
        """Audio callback — runs in a separate thread by sounddevice.

        The whole render holds `self._lock`, so it is fully serialized against
        note_on/note_off/set_sustain on the main thread. Those methods mutate
        voice envelope state in place (e.g. release()), so the lock — not a
        snapshot — is what keeps that state consistent. The voice-major render
        keeps the loop cheap, so the main thread never blocks for long.
        """
        with self._lock:
            # Active (keyed) voices plus voices fading out after a steal/retrigger.
            voices = list(self._voices.values()) + self._dying

            # Mix gain: 1/sqrt(n) attenuation prevents clipping when many voices
            # play. Interpolated smoothly across the buffer to avoid audible
            # clicks when the voice count changes between callbacks.
            voice_count = len(voices)
            target_gain = 1.0 / math.sqrt(voice_count) if voice_count > 1 else 1.0
            gain = self._smooth_gain
            gain_step = (target_gain - gain) / frames if frames > 0 else 0.0

            # Accumulate voices in float64, convert to float32 once at the end.
            mix = [0.0] * frames
            for v in voices:
                self._render_voice(v, mix, frames)

            buf = array.array('f', bytes(frames * 4))
            for i in range(frames):
                gain += gain_step
                sample = mix[i] * gain
                # Soft clip: linear below 0.85, smooth compression above.
                # Realistic chords never reach it; a dozen fortissimo bass
                # notes squash gently instead of cracking at the DAC.
                if sample > 0.85:
                    sample = 0.85 + 0.15 * math.tanh((sample - 0.85) / 0.15)
                elif sample < -0.85:
                    sample = -0.85 - 0.15 * math.tanh((-sample - 0.85) / 0.15)
                buf[i] = sample

            self._smooth_gain = target_gain

            # Drop finished voices from both pools.
            self._voices = {n: v for n, v in self._voices.items() if not v.is_finished()}
            self._dying = [v for v in self._dying if not v.is_finished()]

        outdata[:] = buf.tobytes()
