"""GTK4 DrawingArea wrapping the SheetMusic layout engine."""

from __future__ import annotations

from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from ..sheet_music import SheetMusic


class SheetMusicWidget(Gtk.DrawingArea):
    """Scrollable Cairo widget that renders a SheetMusic object."""

    def __init__(self) -> None:
        super().__init__()
        self.sheet: Optional[SheetMusic] = None
        self._current_pulse = -10
        self._prev_pulse = -10
        self._shade_x = 0
        self.set_draw_func(self._on_draw)
        self.set_hexpand(True)
        self.set_vexpand(False)

        click = Gtk.GestureClick()
        click.connect("pressed", self._on_click)
        self.add_controller(click)
        self._on_seek = None
        self._scroller: Optional[Gtk.ScrolledWindow] = None
        self._manual_zoom = False
        self._last_fit_width = 0

        # Scroll zoom
        scroll = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.VERTICAL
        )
        scroll.connect("scroll", self._on_scroll)
        self.add_controller(scroll)

    def set_scroller(self, scroller: Gtk.ScrolledWindow) -> None:
        self._scroller = scroller

    def set_sheet(self, sheet: Optional[SheetMusic]) -> None:
        self.sheet = sheet
        self._manual_zoom = False
        self._last_fit_width = 0
        self._current_pulse = -10
        self._prev_pulse = -10
        self._shade_x = 0
        if sheet is not None:
            # Set initial content size; _on_draw will auto-fit once we
            # know the actual viewport width.
            self.set_content_width(sheet.total_width)
            self.set_content_height(sheet.total_height)
        self.queue_draw()

    def set_seek_handler(self, callback) -> None:
        self._on_seek = callback

    def set_current_pulse(self, pulse: float) -> None:
        self._prev_pulse = self._current_pulse
        self._current_pulse = int(pulse)
        self.queue_draw()
        if self._scroller is not None and self.sheet is not None and self._shade_x > 0:
            self._auto_scroll()

    def _auto_scroll(self) -> None:
        hadj = self._scroller.get_hadjustment()
        if hadj is None:
            return

        viewport_w = hadj.get_page_size()
        current_scroll = hadj.get_value()

        if self.sheet and not self.sheet.scrollVert:
            target_x = self._shade_x - viewport_w * 0.4
            target_x = max(0, min(target_x, hadj.get_upper() - viewport_w))
            diff = target_x - current_scroll
            if abs(diff) > 2:
                step = diff * 0.3
                if abs(step) < 2:
                    step = 2 if diff > 0 else -2
                hadj.set_value(current_scroll + step)
            else:
                hadj.set_value(target_x)

    def _get_viewport_width(self) -> int:
        """Get the actual viewport width from the scroller or the window."""
        if self._scroller is not None:
            hadj = self._scroller.get_hadjustment()
            if hadj is not None:
                pw = hadj.get_page_size()
                if pw > 100:
                    return int(pw)
            # Fallback: scroller's allocated width
            w = self._scroller.get_width()
            if w > 100:
                return w
        # Fallback: window width
        root = self.get_root()
        if root is not None:
            return max(400, root.get_width() - 20)
        return 980

    def _on_draw(self, area, cr, width, height) -> None:
        if self.sheet is None:
            cr.set_source_rgb(1, 1, 1)
            cr.paint()
            return

        # Auto-fit: zoom sheet to fill the viewport width
        viewport_w = self._get_viewport_width()
        if not self._manual_zoom and viewport_w > 100:
            if viewport_w != self._last_fit_width:
                self._last_fit_width = viewport_w
                base_width = self.sheet.total_width / self.sheet.zoom if self.sheet.zoom > 0 else self.sheet.total_width
                if base_width > 0:
                    new_zoom = max(0.3, min(4.0, viewport_w / base_width))
                    if abs(new_zoom - self.sheet.zoom) > 0.01:
                        self.sheet.set_zoom(new_zoom)
                        self.set_content_width(self.sheet.total_width)
                        self.set_content_height(self.sheet.total_height)
                        # Resize window to fit new content height
                        root = self.get_root()
                        if root is not None and hasattr(root, "set_default_size"):
                            root.set_default_size(root.get_width(), -1)
                            GLib.idle_add(root.queue_resize)

        self.sheet.draw(cr, 0, 0, width, height)
        if self._current_pulse >= 0:
            x_shade, y_shade = self.sheet.shade_notes(
                cr, self._current_pulse, self._prev_pulse
            )
            if x_shade > 0:
                self._shade_x = x_shade

    def _on_scroll(self, controller, dx, dy) -> bool:
        if self.sheet is None:
            return False
        self._manual_zoom = True
        if dy < 0:
            self.sheet.set_zoom(min(4.0, self.sheet.zoom + 0.1))
        elif dy > 0:
            self.sheet.set_zoom(max(0.3, self.sheet.zoom - 0.1))
        else:
            return False
        self.set_content_width(self.sheet.total_width)
        self.set_content_height(self.sheet.total_height)
        self.queue_draw()

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
