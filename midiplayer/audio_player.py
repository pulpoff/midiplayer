"""FluidSynth-based MIDI playback backend.

Replaces the original C# player's ``timidity`` subprocess. Instead of
rewriting a temp MIDI file and spawning an external process, we feed
events directly into a ``fluidsynth.Synth`` on a background thread and
apply volume / instrument / transpose / mute live.

The backend talks to PipeWire / PulseAudio / ALSA through the FluidSynth
driver selection — no extra configuration is needed on a modern
Debian/Ubuntu desktop.

This module does not import GTK. The window wraps it with a ``GLib``
timer for the highlight callbacks.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, List, Optional

from .midi_file import MidiFile
from .midi_options import MidiOptions


class AudioPlayer:
    """Plays a MidiFile via FluidSynth with options applied live."""

    STATE_STOPPED = 1
    STATE_PLAYING = 2
    STATE_PAUSED = 3

    def __init__(self, soundfont_path: Optional[str] = None):
        self._synth = None
        self._sfid = None
        self._soundfont_path = soundfont_path or self._default_soundfont()
        self._driver_name: Optional[str] = None

        self._midifile: Optional[MidiFile] = None
        self._options: Optional[MidiOptions] = None
        self._events: List = []
        self._thread: Optional[threading.Thread] = None
        self._stop_flag = threading.Event()
        self._state = AudioPlayer.STATE_STOPPED
        self._current_pulse: float = 0.0
        self._speed_percent: int = 100
        self._volume_percent: int = 100
        self._pause_pulse: float = 0.0
        self._lock = threading.Lock()
        self._on_pulse_changed: Optional[Callable[[float], None]] = None
        self._total_pulses: int = 0

    # ----------------------------------------------------------------------
    # Lifecycle
    # ----------------------------------------------------------------------

    @staticmethod
    def _default_soundfont() -> Optional[str]:
        """Find a General MIDI soundfont installed on a typical Debian/Ubuntu."""
        import os
        candidates = [
            "/usr/share/sounds/sf2/FluidR3_GM.sf2",
            "/usr/share/sounds/sf2/FluidR3_GS.sf2",
            "/usr/share/sounds/sf2/default-GM.sf2",
            "/usr/share/sounds/sf2/TimGM6mb.sf2",
            "/usr/share/soundfonts/FluidR3_GM.sf2",
            "/usr/share/soundfonts/default.sf2",
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        return None

    def _ensure_synth(self) -> bool:
        if self._synth is not None:
            return True
        try:
            import fluidsynth  # type: ignore
        except ImportError:
            print("midiplayer: pyfluidsynth not installed — no audio")
            return False

        # Create synth with generous polyphony and gain
        self._synth = fluidsynth.Synth(gain=1.0, samplerate=44100)
        self._synth.setting("synth.polyphony", 512)

        # Try audio drivers in preference order.
        # PipeWire exposes a PulseAudio compat layer, so 'pulseaudio' works
        # on both PipeWire and plain PulseAudio systems. Direct 'pipewire'
        # driver often fails with missing SPA_PLUGIN_DIR.
        for driver in ("pulseaudio", "alsa", "pipewire"):
            try:
                self._synth.start(driver=driver)
                self._driver_name = driver
                break
            except Exception:
                continue
        if self._driver_name is None:
            try:
                self._synth.start()
                self._driver_name = "default"
            except Exception:
                print("midiplayer: could not start any FluidSynth audio driver")
                self._synth.delete()
                self._synth = None
                return False

        print(f"midiplayer: FluidSynth using driver '{self._driver_name}'"
              f", soundfont: {self._soundfont_path}")

        if self._soundfont_path:
            try:
                self._sfid = self._synth.sfload(self._soundfont_path)
                for ch in range(16):
                    self._synth.program_select(ch, self._sfid, 0, 0)
            except Exception as e:
                print(f"midiplayer: could not load soundfont: {e}")
        else:
            print("midiplayer: no soundfont found — audio will be silent")
        return True

    def close(self) -> None:
        self.stop()
        if self._synth is not None:
            try:
                self._synth.delete()
            except Exception:
                pass
            self._synth = None

    # ----------------------------------------------------------------------
    # Input + options
    # ----------------------------------------------------------------------

    def set_midi_file(self, midifile: MidiFile, options: MidiOptions) -> None:
        self.stop()
        self._midifile = midifile
        self._options = options
        self._total_pulses = midifile.TotalPulses
        self._rebuild_event_schedule()

    def _rebuild_event_schedule(self) -> None:
        """Flatten all NoteOn/NoteOff events into a single sorted schedule."""
        if self._midifile is None or self._options is None:
            self._events = []
            return

        events: List = []
        for tracknum, track in enumerate(self._midifile.Tracks):
            if tracknum < len(self._options.mute) and self._options.mute[tracknum]:
                continue
            channel = tracknum % 16
            if channel == 9:
                channel = 9  # percussion stays on 9
            instr = (
                self._options.instruments[tracknum]
                if tracknum < len(self._options.instruments)
                else track.Instrument
            )
            transpose = self._options.transpose
            for note in track.Notes:
                number = max(0, min(127, note.Number + transpose))
                start = note.StartTime
                end = note.StartTime + max(1, note.Duration)
                events.append((start, "on", channel, number, 100, instr))
                events.append((end, "off", channel, number, 0, instr))
        events.sort(key=lambda e: (e[0], 0 if e[1] == "off" else 1))
        self._events = events

    def set_volume(self, percent: int) -> None:
        self._volume_percent = max(0, min(100, percent))
        if self._synth is not None:
            try:
                # Map 0-100% to gain 0.0-2.0
                self._synth.setting("synth.gain", self._volume_percent / 100.0 * 2.0)
            except Exception:
                pass

    def set_speed(self, percent: int) -> None:
        self._speed_percent = max(1, min(200, percent))

    @property
    def total_pulses(self) -> int:
        return self._total_pulses

    # ----------------------------------------------------------------------
    # Transport
    # ----------------------------------------------------------------------

    def play(self) -> None:
        if self._midifile is None or not self._events:
            return
        if self._state == AudioPlayer.STATE_PLAYING:
            return
        if not self._ensure_synth():
            return

        self._stop_flag.clear()
        self._state = AudioPlayer.STATE_PLAYING
        self._thread = threading.Thread(
            target=self._play_loop, name="midiplayer-audio", daemon=True
        )
        self._thread.start()

    def pause(self) -> None:
        if self._state != AudioPlayer.STATE_PLAYING:
            return
        self._state = AudioPlayer.STATE_PAUSED
        self._stop_flag.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        self._pause_pulse = self._current_pulse
        self._all_notes_off()

    def stop(self) -> None:
        self._stop_flag.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        if self._synth is not None:
            self._all_notes_off()
        self._state = AudioPlayer.STATE_STOPPED
        self._current_pulse = 0.0
        self._pause_pulse = 0.0
        if self._on_pulse_changed:
            self._on_pulse_changed(0.0)

    def rewind(self) -> None:
        if self._midifile is None or self._options is None:
            return
        measure = self._midifile.Time.Measure
        self._current_pulse = max(0.0, self._current_pulse - measure)
        self._pause_pulse = self._current_pulse
        if self._on_pulse_changed:
            self._on_pulse_changed(self._current_pulse)

    def fast_forward(self) -> None:
        if self._midifile is None or self._options is None:
            return
        measure = self._midifile.Time.Measure
        self._current_pulse += measure
        if self._current_pulse > self._midifile.TotalPulses:
            self._current_pulse -= measure
        self._pause_pulse = self._current_pulse
        if self._on_pulse_changed:
            self._on_pulse_changed(self._current_pulse)

    def seek_to(self, pulse: float) -> None:
        """Seek to a specific pulse position.

        If currently playing, restarts playback from the new position.
        """
        was_playing = (self._state == AudioPlayer.STATE_PLAYING)
        if was_playing:
            # Stop the current play loop without resetting position to 0
            self._stop_flag.set()
            if self._thread is not None:
                self._thread.join(timeout=1.0)
                self._thread = None
            if self._synth is not None:
                self._all_notes_off()

        self._current_pulse = max(0.0, pulse)
        self._pause_pulse = self._current_pulse

        if was_playing:
            # Restart from the new position
            self._state = AudioPlayer.STATE_PLAYING
            self._stop_flag.clear()
            self._thread = threading.Thread(
                target=self._play_loop, name="midiplayer-audio", daemon=True
            )
            self._thread.start()

        if self._on_pulse_changed:
            self._on_pulse_changed(self._current_pulse)

    @property
    def state(self) -> int:
        return self._state

    @property
    def current_pulse(self) -> float:
        return self._current_pulse

    def set_pulse_callback(self, callback: Optional[Callable[[float], None]]) -> None:
        self._on_pulse_changed = callback

    # ----------------------------------------------------------------------
    # Internal
    # ----------------------------------------------------------------------

    def _all_notes_off(self) -> None:
        if self._synth is None:
            return
        for ch in range(16):
            try:
                self._synth.cc(ch, 123, 0)  # All Notes Off
                self._synth.cc(ch, 120, 0)  # All Sound Off
            except Exception:
                pass

    def _pulse_to_seconds(self, pulses: float) -> float:
        if self._midifile is None:
            return 0.0
        timesig = self._midifile.Time
        sec_per_pulse = (timesig.Tempo / 1_000_000.0) / timesig.Quarter
        return pulses * sec_per_pulse * (100.0 / self._speed_percent)

    def _play_loop(self) -> None:
        # Apply instruments before starting
        if self._options is not None and self._synth is not None and self._sfid is not None:
            for tracknum, instr in enumerate(self._options.instruments):
                ch = tracknum % 16
                if ch == 9:
                    continue
                try:
                    self._synth.program_select(ch, self._sfid, 0, instr)
                except Exception:
                    pass

        self.set_volume(self._volume_percent)

        start_wall = time.monotonic()
        start_pulse = self._current_pulse
        i = 0
        # Skip events that occur before the current pulse
        while i < len(self._events) and self._events[i][0] < start_pulse:
            i += 1

        while i < len(self._events) and not self._stop_flag.is_set():
            event = self._events[i]
            target_pulse = event[0]
            target_sec = self._pulse_to_seconds(target_pulse - start_pulse)
            now_sec = time.monotonic() - start_wall
            sleep_sec = target_sec - now_sec
            if sleep_sec > 0:
                end_time = time.monotonic() + sleep_sec
                while not self._stop_flag.is_set():
                    remaining = end_time - time.monotonic()
                    if remaining <= 0:
                        break
                    time.sleep(min(0.02, remaining))
            if self._stop_flag.is_set():
                break

            kind, channel, note, vel, _instr = event[1], event[2], event[3], event[4], event[5]
            if self._synth is not None:
                try:
                    if kind == "on":
                        self._synth.noteon(channel, note, vel)
                    else:
                        self._synth.noteoff(channel, note)
                except Exception:
                    pass

            self._current_pulse = target_pulse
            if self._on_pulse_changed:
                self._on_pulse_changed(self._current_pulse)
            i += 1

        self._all_notes_off()
        if not self._stop_flag.is_set():
            self._state = AudioPlayer.STATE_STOPPED
            self._current_pulse = 0.0
            self._pause_pulse = 0.0
            if self._on_pulse_changed:
                self._on_pulse_changed(0.0)
