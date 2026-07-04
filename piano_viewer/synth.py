"""Built-in wavetable synthesizer (optional, requires sounddevice).

Provides simple piano-like tones using additive synthesis with per-range
wavetables. The feature is entirely optional — if sounddevice is not
installed, nothing in this module runs.
"""

import math
import array
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
_ATTACK_TIME = 0.008
_DECAY_TIME = 0.30
_RELEASE_TIME = 0.10
_FAST_RELEASE_TIME = 0.006
_SUSTAIN_RATIO = 0.7   # sustain level as a fraction of the attack peak


class _Voice:
    """A single synthesizer voice: phase accumulator + ADSR-lite envelope.

    Envelope stages: attack -> decay -> sustain -> release -> done. The short
    attack ramp (and the fast release used when a voice is stolen or retriggered)
    keep note onsets and cutoffs click-free; the brief decay to a sustain floor
    gives the tone a bit of life instead of a dead-flat organ hold.
    """
    __slots__ = ('phase', 'phase_inc', 'amplitude', 'wavetable',
                 'env_stage', 'env_level', 'peak', 'sustain_level',
                 'attack_rate', 'decay_rate', 'release_rate', 'fast_release_rate')

    def __init__(self, freq, level, wavetable, sample_rate, loudness=1.0):
        self.phase = 0.0
        self.phase_inc = freq / sample_rate
        self.amplitude = 0.15 * loudness
        self.wavetable = wavetable

        self.peak = level
        self.sustain_level = level * _SUSTAIN_RATIO
        self.env_stage = 'attack'
        self.env_level = 0.0

        self.attack_rate = self.peak / (_ATTACK_TIME * sample_rate)
        self.decay_rate = (self.peak - self.sustain_level) / (_DECAY_TIME * sample_rate)
        self.release_rate = max(self.peak, 0.01) / (_RELEASE_TIME * sample_rate)
        self.fast_release_rate = max(self.peak, 0.01) / (_FAST_RELEASE_TIME * sample_rate)

    def release(self, fast=False):
        """Begin the release stage. `fast` ramps out in a few ms (steal/retrigger)."""
        if fast:
            self.release_rate = self.fast_release_rate
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

    def _wavetable_for_note(self, note):
        """Returns the wavetable matching the note's pitch range."""
        for i, (max_note, _) in enumerate(_HARMONIC_PROFILES):
            if note <= max_note:
                return self._wavetables[i]
        return self._wavetables[-1]

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
        wt = self._wavetable_for_note(note)
        # Clamp so MIDI notes outside the 88-key range reuse the nearest
        # voiced note's gain instead of indexing out of the table.
        clamped = min(max(note, MIDI_NOTE_MIN), MIDI_NOTE_MAX)
        loudness = LOUDNESS_BY_NOTE[clamped - MIDI_NOTE_MIN]
        voice = _Voice(freq, velocity_scale, wt, self.SAMPLE_RATE, loudness)
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
        decay = v.decay_rate
        release = v.release_rate
        scaled_level = level * amp  # constant while sustaining

        for i in range(frames):
            mix[i] += wt[int(phase)] * scaled_level
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
                level -= decay
                if level <= sustain:
                    level = sustain
                    stage = 'sustain'
            else:  # release
                level -= release
                if level <= 0.0:
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
