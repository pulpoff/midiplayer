"""GTK4 toolbar: transport buttons + compact speed/volume popovers + timeline.

Layout:  [<<] [>||] [Stop] [>>]  Speed:100%  |=====>---------|  0:32 / 2:15  [Vol]
"""

from __future__ import annotations

from typing import Callable, Optional

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402

from ..audio_player import AudioPlayer


class PlayerWidget(Gtk.Box):
    def __init__(self, audio: AudioPlayer) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.audio = audio
        self.set_margin_start(8)
        self.set_margin_end(8)
        self.set_margin_top(4)
        self.set_margin_bottom(4)

        self._on_pulse_changed: Optional[Callable[[float], None]] = None

        # Transport buttons
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

        # Speed button with popover vertical slider
        self.speed_button = Gtk.MenuButton()
        self.speed_button.set_icon_name("preferences-system-time-symbolic")
        self.speed_button.set_tooltip_text("Playback speed: 100%")
        speed_pop = Gtk.Popover()
        speed_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        speed_box.set_margin_top(8)
        speed_box.set_margin_bottom(8)
        speed_box.set_margin_start(8)
        speed_box.set_margin_end(8)
        self.speed_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.VERTICAL, 1, 150, 1
        )
        self.speed_scale.set_inverted(True)
        self.speed_scale.set_value(100)
        self.speed_scale.set_size_request(-1, 180)
        self.speed_scale.set_draw_value(True)
        self.speed_scale.set_value_pos(Gtk.PositionType.BOTTOM)
        self.speed_scale.connect("value-changed", self._on_speed_changed)
        for v in (25, 50, 75, 100, 125, 150):
            self.speed_scale.add_mark(v, Gtk.PositionType.RIGHT, str(v) if v % 50 == 0 else None)
        speed_box.append(Gtk.Label(label="Speed %"))
        speed_box.append(self.speed_scale)
        speed_pop.set_child(speed_box)
        self.speed_button.set_popover(speed_pop)
        self.append(self.speed_button)

        # Timeline progress bar (in the middle, expands)
        self.progress = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 1, 0.001)
        self.progress.set_draw_value(False)
        self.progress.set_hexpand(True)
        # Guard: only react to user-initiated drags, not programmatic updates
        self._programmatic_update = False
        self.progress.connect("value-changed", self._on_progress_changed)
        self.append(self.progress)

        # Time label  "0:00 / 0:00"
        self.time_label = Gtk.Label(label="0:00 / 0:00")
        self.time_label.set_margin_start(4)
        self.time_label.add_css_class("monospace")
        self.append(self.time_label)

        # Volume button with popover vertical slider — on the RIGHT after timeline
        self.volume_button = Gtk.MenuButton()
        self.volume_button.set_icon_name("audio-volume-high-symbolic")
        self.volume_button.set_tooltip_text("Volume")
        self.volume_button.set_margin_start(4)
        vol_pop = Gtk.Popover()
        vol_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        vol_box.set_margin_top(8)
        vol_box.set_margin_bottom(8)
        vol_box.set_margin_start(8)
        vol_box.set_margin_end(8)
        self.volume_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.VERTICAL, 0, 100, 1
        )
        self.volume_scale.set_inverted(True)
        self.volume_scale.set_value(100)
        self.volume_scale.set_size_request(-1, 180)
        self.volume_scale.set_draw_value(True)
        self.volume_scale.set_value_pos(Gtk.PositionType.BOTTOM)
        self.volume_scale.connect("value-changed", self._on_volume_changed)
        for v in (0, 25, 50, 75, 100):
            self.volume_scale.add_mark(v, Gtk.PositionType.RIGHT, str(v) if v % 50 == 0 else None)
        vol_box.append(Gtk.Label(label="Volume"))
        vol_box.append(self.volume_scale)
        vol_pop.set_child(vol_box)
        self.volume_button.set_popover(vol_pop)
        self.append(self.volume_button)

        # Timer
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
        self._update_progress(0.0)

    def set_total_pulses(self, total: int) -> None:
        """Called when a new file is loaded to configure the timeline."""
        self._programmatic_update = True
        self.progress.set_range(0, max(1, total))
        self._programmatic_update = False

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
        self._update_progress(0.0)
        if self._on_pulse_changed is not None:
            self._on_pulse_changed(-10)

    def _on_rewind(self, _button) -> None:
        self.audio.rewind()

    def _on_fast_forward(self, _button) -> None:
        self.audio.fast_forward()

    def _on_speed_changed(self, scale) -> None:
        value = int(scale.get_value())
        self.speed_button.set_tooltip_text(f"Playback speed: {value}%")
        self.audio.set_speed(value)

    def _on_volume_changed(self, scale) -> None:
        value = int(scale.get_value())
        self.audio.set_volume(value)
        if value == 0:
            self.volume_button.set_icon_name("audio-volume-muted-symbolic")
        elif value < 33:
            self.volume_button.set_icon_name("audio-volume-low-symbolic")
        elif value < 66:
            self.volume_button.set_icon_name("audio-volume-medium-symbolic")
        else:
            self.volume_button.set_icon_name("audio-volume-high-symbolic")

    def _on_progress_changed(self, scale) -> None:
        """Handle timeline slider value-changed.

        Only act on user-initiated changes. Programmatic updates from the
        timer set ``_programmatic_update`` to suppress re-seeking.
        """
        if self._programmatic_update:
            return
        pulse = scale.get_value()
        self.audio.seek_to(pulse)
        self._update_time_label(pulse)
        if self._on_pulse_changed is not None:
            self._on_pulse_changed(pulse)

    # ----------------------------------------------------------------------

    def _update_progress(self, pulse: float) -> None:
        """Update the timeline slider and time label without triggering seek."""
        self._programmatic_update = True
        self.progress.set_value(pulse)
        self._programmatic_update = False
        self._update_time_label(pulse)

    def _update_time_label(self, pulse: float) -> None:
        total_pulses = self.audio.total_pulses
        if total_pulses > 0 and self.audio._midifile is not None:
            timesig = self.audio._midifile.Time
            sec_per_pulse = (timesig.Tempo / 1_000_000.0) / timesig.Quarter
            cur_sec = pulse * sec_per_pulse
            tot_sec = total_pulses * sec_per_pulse
            cur_m, cur_s = divmod(int(cur_sec), 60)
            tot_m, tot_s = divmod(int(tot_sec), 60)
            self.time_label.set_text(f"{cur_m}:{cur_s:02d} / {tot_m}:{tot_s:02d}")
        else:
            self.time_label.set_text("0:00 / 0:00")

    def _start_timer(self) -> None:
        if self._timer_id == 0:
            self._timer_id = GLib.timeout_add(50, self._on_timer_tick)

    def _stop_timer(self) -> None:
        if self._timer_id != 0:
            GLib.source_remove(self._timer_id)
            self._timer_id = 0

    def _on_timer_tick(self) -> bool:
        pulse = self.audio.current_pulse
        self._update_progress(pulse)
        if self._on_pulse_changed is not None:
            self._on_pulse_changed(pulse)
        if self.audio.state != AudioPlayer.STATE_PLAYING:
            self._timer_id = 0
            self.play_button.get_child().set_from_icon_name("media-playback-start-symbolic")
            self.play_button.set_tooltip_text("Play")
            return False
        return True

    def _on_audio_pulse(self, pulse: float) -> None:
        pass
