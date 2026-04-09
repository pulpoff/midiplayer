"""GTK4 DrawingArea wrapping the SheetMusic layout engine."""

from __future__ import annotations

from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk  # noqa: E402

from ..sheet_music import SheetMusic


class SheetMusicWidget(Gtk.DrawingArea):
    """Scrollable Cairo widget that renders a SheetMusic object."""

    def __init__(self) -> None:
        super().__init__()
        self.sheet: Optional[SheetMusic] = None
        self._current_pulse = -10
        self._prev_pulse = -10
        self._shade_x = 0  # x pixel of the currently shaded note
        self.set_draw_func(self._on_draw)
        self.set_hexpand(True)
        self.set_vexpand(True)
        # Click handler so the user can seek by clicking a note
        click = Gtk.GestureClick()
        click.connect("pressed", self._on_click)
        self.add_controller(click)
        self._on_seek = None
        self._scroller: Optional[Gtk.ScrolledWindow] = None
        self._auto_zoom = True  # auto-fit zoom to window width
        self._manual_zoom = False  # set True after user scrolls to zoom

        # Scroll zoom
        scroll = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.VERTICAL
        )
        scroll.connect("scroll", self._on_scroll)
        self.add_controller(scroll)

    def set_scroller(self, scroller: Gtk.ScrolledWindow) -> None:
        """Store a reference to the parent ScrolledWindow for auto-scroll."""
        self._scroller = scroller
        # Watch for scroller width changes to auto-zoom
        scroller.connect("notify::default-width", lambda *a: self._fit_zoom())
        hadj = scroller.get_hadjustment()
        if hadj:
            hadj.connect("notify::page-size", lambda *a: self._fit_zoom())

    def set_sheet(self, sheet: Optional[SheetMusic]) -> None:
        self.sheet = sheet
        self._manual_zoom = False  # reset on new file
        if sheet is not None:
            self._fit_zoom()
        self._current_pulse = -10
        self._prev_pulse = -10
        self._shade_x = 0
        self.queue_draw()

    def set_seek_handler(self, callback) -> None:
        self._on_seek = callback

    def set_current_pulse(self, pulse: float) -> None:
        self._prev_pulse = self._current_pulse
        self._current_pulse = int(pulse)
        self.queue_draw()
        # Auto-scroll to keep the shaded note visible
        if self._scroller is not None and self.sheet is not None and self._shade_x > 0:
            self._auto_scroll()

    def _auto_scroll(self) -> None:
        """Smoothly scroll so the shaded note stays near the center."""
        hadj = self._scroller.get_hadjustment()
        vadj = self._scroller.get_vadjustment()
        if hadj is None:
            return

        viewport_w = hadj.get_page_size()
        current_scroll = hadj.get_value()

        if self.sheet and not self.sheet.scrollVert:
            # Horizontal layout: keep shade_x around 40% from the left
            target_x = self._shade_x - viewport_w * 0.4
            target_x = max(0, min(target_x, hadj.get_upper() - viewport_w))

            # Smooth scroll: move a fraction of the distance each tick
            diff = target_x - current_scroll
            if abs(diff) > 2:
                # Move faster when far away, gentle when close
                step = diff * 0.3
                if abs(step) < 2:
                    step = 2 if diff > 0 else -2
                hadj.set_value(current_scroll + step)
            else:
                hadj.set_value(target_x)

    def _on_draw(self, area, cr, width, height) -> None:
        if self.sheet is None:
            cr.set_source_rgb(1, 1, 1)
            cr.paint()
            return
        self.sheet.draw(cr, 0, 0, width, height)
        if self._current_pulse >= 0:
            x_shade, y_shade = self.sheet.shade_notes(
                cr, self._current_pulse, self._prev_pulse
            )
            if x_shade > 0:
                self._shade_x = x_shade

    def _fit_zoom(self) -> None:
        """Auto-zoom the sheet to fit the available scroller width."""
        if self.sheet is None or self._scroller is None or self._manual_zoom:
            return
        hadj = self._scroller.get_hadjustment()
        if hadj is None:
            return
        available = hadj.get_page_size()
        if available < 100:
            # Scroller not yet laid out
            return
        # Calculate zoom so the sheet's unzoomed width fits the viewport
        base_width = self.sheet.total_width / self.sheet.zoom if self.sheet.zoom > 0 else self.sheet.total_width
        if base_width <= 0:
            return
        new_zoom = max(0.3, min(4.0, available / base_width))
        self.sheet.set_zoom(new_zoom)
        self.set_content_width(self.sheet.total_width)
        self.set_content_height(self.sheet.total_height)
        self.queue_draw()

    def _on_scroll(self, controller, dx, dy) -> bool:
        """Mouse scroll on sheet music zooms in/out."""
        if self.sheet is None:
            return False
        self._manual_zoom = True  # user took control, stop auto-fitting
        if dy < 0:
            self.sheet.set_zoom(min(4.0, self.sheet.zoom + 0.1))
        elif dy > 0:
            self.sheet.set_zoom(max(0.3, self.sheet.zoom - 0.1))
        else:
            return False
        self.set_content_width(self.sheet.total_width)
        self.set_content_height(self.sheet.total_height)
        self.queue_draw()

        # Ask the window to shrink-to-fit when zooming out
        window = self.get_root()
        if window is not None and hasattr(window, "set_default_size"):
            window.set_default_size(980, -1)
            window.queue_resize()
        return True

    def _on_click(self, gesture, n_press, x, y) -> None:
        if self.sheet is None or self._on_seek is None:
            return
        pulse = self.sheet.pulse_time_for_point(int(x), int(y))
        if pulse >= 0:
            self._on_seek(pulse)
