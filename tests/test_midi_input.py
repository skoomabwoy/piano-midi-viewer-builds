"""Tests for the MidiInput transport — parsing, scanning, and reconnect logic.

No timers are started and no real rtmidi ports are opened: the scanner and
connect() are stubbed, and _scan()/_parse() are driven directly.
"""

import pytest

from piano_viewer.midi_input import MidiInput


class Recorder:
    """Collects every transport callback for assertions."""

    def __init__(self):
        self.note_ons = []
        self.note_offs = []
        self.sustains = []
        self.disconnects = []
        self.connects = []
        self.statuses = []
        self.errors = []
        self.devices_changed = 0


def make_midi(recorder):
    return MidiInput(
        on_note_on=lambda n, v: recorder.note_ons.append((n, v)),
        on_note_off=recorder.note_offs.append,
        on_sustain=recorder.sustains.append,
        on_disconnect=recorder.disconnects.append,
        on_connect=recorder.connects.append,
        on_status=recorder.statuses.append,
        on_error=lambda title, details: recorder.errors.append((title, details)),
        on_devices_changed=lambda: setattr(
            recorder, 'devices_changed', recorder.devices_changed + 1),
    )


@pytest.fixture
def rec():
    return Recorder()


@pytest.fixture
def midi(rec):
    return make_midi(rec)


class FakePort:
    def __init__(self):
        self.closed = False

    def close_port(self):
        self.closed = True


# ---- parsing ----

class TestParse:
    def test_note_on(self, midi, rec):
        midi._parse([0x90, 60, 100])
        assert rec.note_ons == [(60, 100)]

    def test_note_on_any_channel(self, midi, rec):
        midi._parse([0x95, 60, 100])  # channel 6
        assert rec.note_ons == [(60, 100)]

    def test_note_off(self, midi, rec):
        midi._parse([0x80, 60, 0])
        assert rec.note_offs == [60]

    def test_note_on_velocity_zero_is_note_off(self, midi, rec):
        midi._parse([0x90, 60, 0])
        assert rec.note_ons == []
        assert rec.note_offs == [60]

    def test_sustain_threshold(self, midi, rec):
        midi._parse([0xB0, 64, 64])
        midi._parse([0xB0, 64, 63])
        assert rec.sustains == [True, False]

    def test_other_cc_ignored(self, midi, rec):
        midi._parse([0xB0, 1, 100])  # mod wheel
        assert rec.sustains == []

    def test_short_message_ignored(self, midi, rec):
        midi._parse([0xC0, 5])  # program change
        assert rec.note_ons == [] and rec.note_offs == []


# ---- virtual port filtering ----

class TestVirtualFilter:
    def test_known_virtual_ports_filtered(self):
        devices = [
            "Midi Through 14:0",
            "VirMIDI 2-0 24:0",
            "IAC Driver Bus 1",
            "Roland FP-30 28:0",
        ]
        assert MidiInput._filter_virtual(devices) == ["Roland FP-30 28:0"]


# ---- hot-plug scanning ----

def scan_with(midi, ports):
    """Runs one scan tick against a fixed port list."""
    midi.get_devices = lambda: ports
    midi._scan()


class TestScan:
    def test_active_device_unplugged_disconnects(self, midi, rec):
        midi.known_devices = ["KeyA"]
        midi.current_device = "KeyA"
        midi._midi_in = FakePort()
        scan_with(midi, [])
        assert rec.disconnects == ["KeyA"]
        assert midi._midi_in is None
        assert midi.current_device == "KeyA"  # kept for reconnect

    def test_previous_device_reappearing_reconnects(self, midi, rec):
        midi.known_devices = []
        midi.current_device = "KeyA"
        midi.connect = lambda name: name == "KeyA"
        scan_with(midi, ["KeyA", "KeyB"])
        assert rec.connects == ["KeyA"]

    def test_single_new_real_device_autoconnects(self, midi, rec):
        midi.known_devices = ["Midi Through 14:0"]
        midi.connect = lambda name: True
        scan_with(midi, ["Midi Through 14:0", "KeyA"])
        assert rec.connects == ["KeyA"]

    def test_multiple_new_devices_do_not_autoconnect(self, midi, rec):
        midi.known_devices = []
        midi.connect = lambda name: pytest.fail("must not connect")
        scan_with(midi, ["KeyA", "KeyB"])
        assert rec.connects == []

    def test_new_virtual_port_does_not_autoconnect(self, midi, rec):
        midi.known_devices = []
        midi.connect = lambda name: pytest.fail("must not connect")
        scan_with(midi, ["IAC Driver Bus 1"])
        assert rec.connects == []

    def test_devices_changed_fires_only_on_change(self, midi, rec):
        midi.known_devices = ["KeyA"]
        scan_with(midi, ["KeyA"])
        assert rec.devices_changed == 0
        scan_with(midi, ["KeyA", "KeyB"])
        assert rec.devices_changed == 1


# ---- scan failure handling ----

class BrokenScanner:
    def get_ports(self):
        raise RuntimeError("backend gone")


class TestScanFailure:
    def test_error_dialog_latches_per_failure_streak(self, midi, rec):
        midi._scanner = BrokenScanner()
        midi.get_devices()
        midi._scanner = BrokenScanner()  # get_devices dropped the handle
        midi.get_devices()
        assert len(rec.errors) == 1  # one dialog, not one per tick

        # Recovery resets the latch; the next failure reports again.
        midi._scanner = None
        midi.get_devices = MidiInput.get_devices.__get__(midi)
        working = type("S", (), {"get_ports": lambda self: []})()
        midi._scanner = working
        midi.get_devices()
        assert not midi._scan_failed

    def test_scan_failure_is_not_treated_as_unplug(self, midi, rec):
        midi.known_devices = ["KeyA"]
        midi.current_device = "KeyA"
        midi._midi_in = FakePort()
        midi._scanner = BrokenScanner()
        midi._scan()
        assert rec.disconnects == []
        assert midi._midi_in is not None
        assert midi.known_devices == ["KeyA"]  # kept until scanning recovers
