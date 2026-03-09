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
    MIDI_NOTE_MIN, MIDI_NOTE_MAX, LOUDNESS_MULT_LOW, LOUDNESS_MULT_HIGH,
)

if _SOUND_AVAILABLE:
    import sounddevice as _sd


class _Voice:
    """A single synthesizer voice with phase accumulator and ASR envelope."""
    __slots__ = ('phase', 'phase_inc', 'amplitude', 'env_stage', 'env_level',
                 'sustain_level', 'release_rate', 'wavetable')

    def __init__(self, freq, sustain_level, wavetable, sample_rate, loudness=1.0):
        self.phase = 0.0
        self.phase_inc = freq / sample_rate
        self.amplitude = 0.15 * loudness
        self.wavetable = wavetable
        self.env_stage = 'sustain'
        self.env_level = sustain_level
        self.sustain_level = sustain_level
        release_time = 0.05
        self.release_rate = max(self.sustain_level, 0.01) / (release_time * sample_rate)

    def release(self):
        self.env_stage = 'release'

    def is_finished(self):
        return self.env_stage == 'done'


# Harmonic profiles for different pitch ranges.
# Uses 1/n amplitude rolloff (organ pipe harmonic series).
_HARMONIC_PROFILES = [
    (40,  [1.0, 1/2, 1/3, 1/4, 1/5, 1/6, 1/7, 1/8]),
    (60,  [1.0, 1/2, 1/3, 1/4, 1/5, 1/6]),
    (84,  [1.0, 1/2, 1/3, 1/4]),
    (MIDI_NOTE_MAX, [1.0, 1/3]),
]


class PianoSynthesizer:
    """Wavetable synthesizer with polyphony and sustain pedal support."""
    SAMPLE_RATE = 44100
    WAVETABLE_SIZE = 4096
    MAX_VOICES = 12

    def __init__(self):
        self._voices = {}
        self._sustained = set()
        self.sustain_active = False
        self._lock = threading.Lock()
        self._stream = None
        self._smooth_gain = 1.0
        self._wavetables = self._build_wavetables()

    def _build_wavetables(self):
        """Pre-compute one wavetable per harmonic profile."""
        tables = []
        two_pi = 2.0 * math.pi
        for _, harmonics in _HARMONIC_PROFILES:
            table = []
            norm = sum(harmonics)
            for i in range(self.WAVETABLE_SIZE):
                t = i / self.WAVETABLE_SIZE
                sample = 0.0
                for h, amp in enumerate(harmonics, 1):
                    sample += amp * math.sin(two_pi * h * t)
                table.append(sample / norm)
            tables.append(table)
        return tables

    def _wavetable_for_note(self, note):
        """Returns the wavetable matching the note's pitch range."""
        for i, (max_note, _) in enumerate(_HARMONIC_PROFILES):
            if note <= max_note:
                return self._wavetables[i]
        return self._wavetables[-1]

    def start(self):
        """Opens the audio stream."""
        if self._stream is not None:
            return
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
            self._sustained.clear()
            self._smooth_gain = 1.0

    def note_on(self, note, velocity_scale=1.0):
        """Starts a new voice for the given MIDI note number."""
        if self._stream is None:
            return
        freq = 440.0 * (2.0 ** ((note - 69) / 12.0))
        wt = self._wavetable_for_note(note)
        t = (note - MIDI_NOTE_MIN) / (MIDI_NOTE_MAX - MIDI_NOTE_MIN)
        loudness = LOUDNESS_MULT_LOW + t * (LOUDNESS_MULT_HIGH - LOUDNESS_MULT_LOW)
        voice = _Voice(freq, velocity_scale, wt, self.SAMPLE_RATE, loudness)
        with self._lock:
            self._sustained.discard(note)
            if len(self._voices) >= self.MAX_VOICES and note not in self._voices:
                # Steal the oldest voice — dict preserves insertion order (Python 3.7+),
                # so the first key is always the note that started playing earliest.
                oldest_key = next(iter(self._voices))
                del self._voices[oldest_key]
            self._voices[note] = voice

    def note_off(self, note):
        """Handles key release — respects sustain pedal state."""
        with self._lock:
            if self.sustain_active:
                self._sustained.add(note)
            elif note in self._voices:
                self._voices[note].release()

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

    def _callback(self, outdata, frames, time_info, status):
        """Audio callback — runs in a separate thread by sounddevice.

        Takes a snapshot of current voices under the lock, then renders samples
        without holding it. Voice phase/envelope mutations here are safe because
        each voice object is only accessed by this callback (main thread creates
        new voice objects, never mutates existing ones in-place).
        """
        wt_size = self.WAVETABLE_SIZE
        buf = array.array('f', bytes(frames * 4))

        with self._lock:
            voices = list(self._voices.values())

        # Mix gain: 1/sqrt(n) attenuation prevents clipping when many voices play.
        # Interpolated smoothly across the buffer to avoid audible clicks when
        # the voice count changes between callbacks.
        voice_count = len(voices)
        target_gain = 1.0 / math.sqrt(voice_count) if voice_count > 1 else 1.0
        gain = self._smooth_gain
        gain_step = (target_gain - gain) / frames if frames > 0 else 0.0

        for i in range(frames):
            sample = 0.0
            for v in voices:
                wt = v.wavetable
                idx = int(v.phase * wt_size) % wt_size
                sample += wt[idx] * v.env_level * v.amplitude

                v.phase += v.phase_inc
                if v.phase >= 1.0:
                    v.phase -= 1.0

                if v.env_stage == 'release':
                    v.env_level -= v.release_rate
                    if v.env_level <= 0.0:
                        v.env_level = 0.0
                        v.env_stage = 'done'

            gain += gain_step
            buf[i] = sample * gain

        self._smooth_gain = target_gain

        with self._lock:
            finished = [n for n, v in self._voices.items() if v.is_finished()]
            for n in finished:
                del self._voices[n]

        outdata[:] = buf.tobytes()
