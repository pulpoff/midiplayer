"""GTK4 application entry point."""

from __future__ import annotations

import os
import sys
from typing import List

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gio, Gtk  # noqa: E402

from .widgets.window import SheetMusicWindow


APP_ID = "com.pulpoff.midiplayer"
_RESOURCE_DIR = os.path.join(os.path.dirname(__file__), "resources")


class MidiPlayerApp(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.HANDLES_OPEN,
        )
        self._window: SheetMusicWindow | None = None

    def do_startup(self) -> None:
        Gtk.Application.do_startup(self)
        # Set the app icon from the bundled SVG
        icon_path = os.path.join(_RESOURCE_DIR, "midiplayer.svg")
        if os.path.exists(icon_path):
            display = Gdk.Display.get_default()
            if display is not None:
                theme = Gtk.IconTheme.get_for_display(display)
                theme.add_search_path(_RESOURCE_DIR)

    def do_activate(self) -> None:
        self._ensure_window().present()

    def do_open(self, files, n_files, hint) -> None:
        window = self._ensure_window()
        if n_files > 0:
            path = files[0].get_path()
            if path:
                window.open_midi_file(path)
        window.present()

    def _ensure_window(self) -> SheetMusicWindow:
        if self._window is None:
            self._window = SheetMusicWindow(self)
        return self._window


def main(argv: List[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv
    app = MidiPlayerApp()
    return app.run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
