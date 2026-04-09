"""GTK4 DrawingArea wrapping the SheetMusic layout engine."""

from __future__ import annotations

from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from ..sheet_music import SheetMusic


class SheetMusicWidget(Gtk.DrawingArea):
    """Scrollable Cairo widget that renders a SheetMusic object."""

    def __init__(self) -> None:
        super().__init__()
        self.sheet: Optional[SheetMusic] = None
        self._current_pulse = -10
        self._prev_pulse = -10
        self.set_draw_func(self._on_draw)
        self.set_hexpand(True)
        self.set_vexpand(True)
        # Click handler so the user can seek by clicking a note
        click = Gtk.GestureClick()
        click.connect("pressed", self._on_click)
        self.add_controller(click)
        self._on_seek = None

    def set_sheet(self, sheet: Optional[SheetMusic]) -> None:
        self.sheet = sheet
        if sheet is not None:
            self.set_content_width(sheet.total_width)
            self.set_content_height(sheet.total_height)
        self._current_pulse = -10
        self._prev_pulse = -10
        self.queue_draw()

    def set_seek_handler(self, callback) -> None:
        self._on_seek = callback

    def set_current_pulse(self, pulse: float) -> None:
        self._prev_pulse = self._current_pulse
        self._current_pulse = int(pulse)
        self.queue_draw()

    def _on_draw(self, area, cr, width, height) -> None:
        if self.sheet is None:
            cr.set_source_rgb(1, 1, 1)
            cr.paint()
            cr.set_source_rgb(0, 0, 0)
            cr.move_to(20, 30)
            cr.set_font_size(14)
            cr.show_text("Use the menu File > Open to select a MIDI file")
            return
        self.sheet.draw(cr, 0, 0, width, height)
        if self._current_pulse >= 0:
            self.sheet.shade_notes(cr, self._current_pulse, self._prev_pulse)

    def _on_click(self, gesture, n_press, x, y) -> None:
        if self.sheet is None or self._on_seek is None:
            return
        pulse = self.sheet.pulse_time_for_point(int(x), int(y))
        if pulse >= 0:
            self._on_seek(pulse)
