"""GTK4 DrawingArea wrapping the Piano renderer."""

from __future__ import annotations

from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from ..midi_file import MidiFile
from ..midi_options import MidiOptions
from ..piano import Piano


class PianoWidget(Gtk.DrawingArea):
    """Piano keyboard widget. Fixed size, scaled from a unit white key width."""

    def __init__(self, white_key_width: int = 14) -> None:
        super().__init__()
        self.piano = Piano(white_key_width)
        self.set_content_width(self.piano.width)
        self.set_content_height(self.piano.height)
        self.set_draw_func(self._on_draw)
        self._current_pulse = -10
        self._prev_pulse = -10

    def set_midi_file(
        self, midifile: Optional[MidiFile], options: Optional[MidiOptions]
    ) -> None:
        self.piano.set_midi_file(midifile, options)
        self._current_pulse = -10
        self._prev_pulse = -10
        self.queue_draw()

    def set_current_pulse(self, pulse: float) -> None:
        self._prev_pulse = self._current_pulse
        self._current_pulse = int(pulse)
        self.queue_draw()

    def set_shade_colors(self, c1: tuple, c2: tuple) -> None:
        self.piano.set_shade_colors(c1, c2)
        self.queue_draw()

    def _on_draw(self, area, cr, width, height) -> None:
        self.piano.draw(cr)
        if self._current_pulse >= 0:
            self.piano.shade_notes(cr, self._current_pulse, self._prev_pulse)
