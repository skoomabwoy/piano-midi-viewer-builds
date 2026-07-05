"""MIDI input transport — device scanning, connection, polling, and parsing.

Owns the rtmidi handles and the poll/scan timers. Knows nothing about the
piano, the glow buttons, or the synth: it turns raw MIDI bytes into semantic
events (note on/off, sustain) and delivers them through callbacks supplied at
construction. This keeps the main window free of transport details and makes
the MIDI parsing testable in isolation.

Callbacks (all required unless noted):
    on_note_on(note, velocity)  — Note On with velocity > 0
    on_note_off(note)           — Note Off (or Note On with velocity 0)
    on_sustain(active)          — CC 64 crossed the 64 threshold
    on_disconnect(device_name)  — active device vanished or errored
    on_connect(device_name)     — auto-(re)connected during a background scan
    on_status(text)             — short user-facing status/toast text
    on_error(title, details)    — a failure worth a dialog
    on_devices_changed()        — optional; the available-device list changed
                                  (fires after any connect/disconnect handling,
                                  so UI reading transport state sees the result)
"""

import rtmidi
from PyQt6.QtCore import QTimer

from piano_viewer import log
from piano_viewer.i18n import tr
from piano_viewer.constants import MIDI_POLL_INTERVAL, MIDI_SCAN_INTERVAL


class MidiInput:
    """Polling-based MIDI input transport built on python-rtmidi."""

    # Known virtual/system MIDI port prefixes — never auto-selected, but always
    # returned by get_devices() so the user can connect to them manually.
    # Deliberately not listed: user-installed routers like loopMIDI — someone
    # who set one up as their only port probably wants it picked.
    _VIRTUAL_MIDI_PREFIXES = (
        "Midi Through",     # ALSA built-in virtual loopback
        "VirMIDI",          # ALSA snd-virmidi kernel module ports
        "IAC Driver",       # macOS built-in inter-application bus
    )

    def __init__(self, *, on_note_on, on_note_off, on_sustain,
                 on_disconnect, on_connect, on_status, on_error,
                 on_devices_changed=None):
        self._on_note_on = on_note_on
        self._on_note_off = on_note_off
        self._on_sustain = on_sustain
        self._on_disconnect = on_disconnect
        self._on_connect = on_connect
        self._on_status = on_status
        self._on_error = on_error
        self._on_devices_changed = on_devices_changed

        self._midi_in = None
        self._scanner = None
        self.current_device = None
        self.known_devices = []
        self._poll_timer = None
        self._scan_timer = None
        # True while device scanning is failing. Latches the error dialog so a
        # persistent failure reports once instead of once per 3-second scan,
        # and lets _scan() tell "scan broke" apart from "no devices".
        self._scan_failed = False

    # --- Lifecycle ---

    def start(self):
        """Begins polling for messages and scanning for device changes."""
        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._poll)
        self._poll_timer.start(MIDI_POLL_INTERVAL)

        self.known_devices = self.get_devices()
        self._scan_timer = QTimer()
        self._scan_timer.timeout.connect(self._scan)
        self._scan_timer.start(MIDI_SCAN_INTERVAL)

    def shutdown(self):
        """Stops timers and releases all rtmidi resources."""
        if self._poll_timer:
            self._poll_timer.stop()
        if self._scan_timer:
            self._scan_timer.stop()
        if self._midi_in:
            try:
                self._midi_in.close_port()
            except Exception:
                pass
            self._midi_in = None
        self._scanner = None

    @property
    def connected(self):
        """True while a device port is open."""
        return self._midi_in is not None

    # --- Device discovery ---

    @classmethod
    def _filter_virtual(cls, devices):
        """Returns devices that don't match known virtual/system port prefixes."""
        return [d for d in devices if not d.startswith(cls._VIRTUAL_MIDI_PREFIXES)]

    def real_devices(self):
        """Known devices excluding virtual/system ports (used for auto-select)."""
        return self._filter_virtual(self.known_devices)

    def get_devices(self):
        """Returns the list of available MIDI input device names.

        On failure returns [] and sets _scan_failed. The error dialog fires
        only on the first failure of a streak — this runs every 3 seconds
        from the scan timer, and a broken MIDI backend must not stack a new
        modal dialog per tick.
        """
        try:
            if not self._scanner:
                self._scanner = rtmidi.MidiIn()
            ports = self._scanner.get_ports()
            self._scan_failed = False
            return ports
        except Exception as e:
            log.error(f"Error scanning MIDI devices: {e}")
            # Drop the handle so the next attempt starts from a fresh one.
            self._scanner = None
            if not self._scan_failed:
                self._scan_failed = True
                self._on_error(tr("MIDI Error"),
                               tr("Could not scan for MIDI devices: {}").format(e))
            return []

    # --- Connection ---

    def connect(self, device_name):
        """Connects to a device by name. Returns True on success.

        Pure transport: emits on_status but does not persist anything. The caller
        decides whether a successful connection should be saved.
        """
        ports = self.get_devices()
        if device_name not in ports:
            log.warning(f"Device not found: {device_name}")
            self._on_status(tr("Not found: {}").format(device_name))
            return False

        try:
            new_in = rtmidi.MidiIn()
            new_in.open_port(ports.index(device_name))
        except Exception as e:
            log.error(f"Error connecting to MIDI device: {e}")
            self._on_status(tr("Connection failed: {}").format(device_name))
            return False

        if self._midi_in:
            try:
                self._midi_in.close_port()
            except Exception:
                pass

        self._midi_in = new_in
        self.current_device = device_name
        log.info(f"Connected to MIDI device: {device_name}")
        self._on_status(tr("Connected: {}").format(device_name))
        return True

    def _disconnect(self):
        """Closes the active port (keeps current_device for later reconnect)."""
        device_name = self.current_device or "Unknown device"
        if self._midi_in:
            try:
                self._midi_in.close_port()
            except Exception:
                pass
            self._midi_in = None
        self._on_disconnect(device_name)

    # --- Polling / parsing ---

    def _poll(self):
        """Drains pending MIDI messages (called every MIDI_POLL_INTERVAL ms)."""
        if not self._midi_in:
            return
        try:
            while True:
                message = self._midi_in.get_message()
                if message is None:
                    break
                midi_data, _ = message
                self._parse(midi_data)
        except Exception as e:
            log.error(f"Error polling MIDI: {e}")
            self._disconnect()

    def _parse(self, midi_data):
        """Turns a raw MIDI message into a semantic callback."""
        if len(midi_data) < 3:
            return

        message_type = midi_data[0] & 0xF0
        data1 = midi_data[1]
        data2 = midi_data[2]

        if message_type == 0xB0:
            if data1 == 64:  # Sustain pedal
                self._on_sustain(data2 >= 64)
        elif message_type == 0x90 and data2 > 0:
            self._on_note_on(data1, data2)
        elif message_type == 0x80 or (message_type == 0x90 and data2 == 0):
            self._on_note_off(data1)

    # --- Hot-plug scanning ---

    def _scan(self):
        """Checks for device changes (called every MIDI_SCAN_INTERVAL ms).

        - Active device disappeared: disconnect gracefully.
        - A device appeared while we have no connection: reconnect the previously
          used device if it came back, otherwise auto-connect only when exactly
          one real (non-virtual) device showed up. Successful auto-connects fire
          on_connect so the caller can persist the choice.
        """
        current_ports = self.get_devices()
        if self._scan_failed:
            # Transient scan failure — an empty result here means "couldn't
            # look", not "every device was unplugged". Keep the known list and
            # the active connection; we'll reconcile once scanning recovers.
            return

        previous = set(self.known_devices)
        current = set(current_ports)
        self.known_devices = list(current_ports)

        if current == previous:
            return

        appeared = current - previous
        disappeared = previous - current

        if self.current_device and self.current_device in disappeared:
            self._disconnect()

        if not self._midi_in and appeared:
            target = None
            if self.current_device in appeared:
                # Previously used device came back — reconnect regardless of filter.
                target = self.current_device
            else:
                real_appeared = self._filter_virtual(list(appeared))
                if len(real_appeared) == 1:
                    target = real_appeared[0]
            if target and self.connect(target):
                self._on_connect(target)

        # Fired last so listeners (e.g. the Settings device list) see the
        # final connection state, not the mid-scan one.
        if self._on_devices_changed is not None:
            self._on_devices_changed()
