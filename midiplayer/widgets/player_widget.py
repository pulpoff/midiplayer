"""GTK4 toolbar row with Rewind / Play / Stop / FastForward + speed + volume.

Matches the original MidiSheetMusic player panel exactly: four round
buttons, a "Speed: 100%" label followed by a slider, a volume speaker
icon followed by a second slider. The buttons use standard GNOME symbolic
icons so they pick up the current theme.
"""

from __future__ import annotations

from typing import Callable, Optional

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402

from ..audio_player import AudioPlayer


class PlayerWidget(Gtk.Box):
    def __init__(self, audio: AudioPlayer) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.audio = audio
        self.set_margin_start(8)
        self.set_margin_end(8)
        self.set_margin_top(6)
        self.set_margin_bottom(6)

        self._on_pulse_changed: Optional[Callable[[float], None]] = None

        # Buttons
        self.rewind_button = self._mk_button(
            "media-seek-backward-symbolic", "Rewind one measure", self._on_rewind
        )
        self.play_button = self._mk_button(
            "media-playback-start-symbolic", "Play", self._on_play_pause
        )
        self.stop_button = self._mk_button(
            "media-playback-stop-symbolic", "Stop", self._on_stop
        )
        self.ff_button = self._mk_button(
            "media-seek-forward-symbolic", "Fast forward one measure", self._on_fast_forward
        )
        self.append(self.rewind_button)
        self.append(self.play_button)
        self.append(self.stop_button)
        self.append(self.ff_button)

        # Speed label + slider
        self.speed_label = Gtk.Label(label="Speed: 100%")
        self.speed_label.set_margin_start(16)
        self.append(self.speed_label)
        self.speed_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 1, 150, 1
        )
        self.speed_scale.set_value(100)
        self.speed_scale.set_hexpand(True)
        self.speed_scale.set_draw_value(False)
        self.speed_scale.connect("value-changed", self._on_speed_changed)
        self.append(self.speed_scale)

        # Volume icon + slider
        volume_icon = Gtk.Image.new_from_icon_name("audio-volume-high-symbolic")
        volume_icon.set_margin_start(16)
        self.append(volume_icon)
        self.volume_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0, 100, 1
        )
        self.volume_scale.set_value(100)
        self.volume_scale.set_hexpand(True)
        self.volume_scale.set_draw_value(False)
        self.volume_scale.connect("value-changed", self._on_volume_changed)
        self.append(self.volume_scale)

        # Timer: 50ms tick while playing to update highlighting
        self._timer_id = 0
        self.audio.set_pulse_callback(self._on_audio_pulse)

    # ----------------------------------------------------------------------

    def _mk_button(self, icon_name: str, tooltip: str, callback) -> Gtk.Button:
        button = Gtk.Button()
        button.set_child(Gtk.Image.new_from_icon_name(icon_name))
        button.set_tooltip_text(tooltip)
        button.connect("clicked", callback)
        return button

    def set_pulse_handler(self, callback: Callable[[float], None]) -> None:
        self._on_pulse_changed = callback

    def reset(self) -> None:
        self.audio.stop()
        self.play_button.get_child().set_from_icon_name("media-playback-start-symbolic")
        self.play_button.set_tooltip_text("Play")

    # ----------------------------------------------------------------------

    def _on_play_pause(self, _button) -> None:
        state = self.audio.state
        if state == AudioPlayer.STATE_PLAYING:
            self.audio.pause()
            self.play_button.get_child().set_from_icon_name("media-playback-start-symbolic")
            self.play_button.set_tooltip_text("Play")
            self._stop_timer()
        else:
            self.audio.play()
            self.play_button.get_child().set_from_icon_name("media-playback-pause-symbolic")
            self.play_button.set_tooltip_text("Pause")
            self._start_timer()

    def _on_stop(self, _button) -> None:
        self.audio.stop()
        self.play_button.get_child().set_from_icon_name("media-playback-start-symbolic")
        self.play_button.set_tooltip_text("Play")
        self._stop_timer()
        if self._on_pulse_changed is not None:
            self._on_pulse_changed(-10)

    def _on_rewind(self, _button) -> None:
        self.audio.rewind()

    def _on_fast_forward(self, _button) -> None:
        self.audio.fast_forward()

    def _on_speed_changed(self, scale) -> None:
        value = int(scale.get_value())
        self.speed_label.set_text(f"Speed: {value}%")
        self.audio.set_speed(value)

    def _on_volume_changed(self, scale) -> None:
        self.audio.set_volume(int(scale.get_value()))

    # ----------------------------------------------------------------------

    def _start_timer(self) -> None:
        if self._timer_id == 0:
            self._timer_id = GLib.timeout_add(50, self._on_timer_tick)

    def _stop_timer(self) -> None:
        if self._timer_id != 0:
            GLib.source_remove(self._timer_id)
            self._timer_id = 0

    def _on_timer_tick(self) -> bool:
        if self._on_pulse_changed is not None:
            self._on_pulse_changed(self.audio.current_pulse)
        if self.audio.state != AudioPlayer.STATE_PLAYING:
            self._timer_id = 0
            self.play_button.get_child().set_from_icon_name("media-playback-start-symbolic")
            self.play_button.set_tooltip_text("Play")
            return False
        return True

    def _on_audio_pulse(self, pulse: float) -> None:
        # Called from the audio thread — just wake the main loop.
        # The real update happens in the timer tick which runs on the main loop.
        pass
