"""GTK4 + libadwaita application entry point.

Uses Adw.Application for automatic GNOME theme (dark/light) integration.
Falls back to plain Gtk.Application if libadwaita is not installed.
"""

from __future__ import annotations

import os
import sys
from typing import List

import gi

gi.require_version("Gtk", "4.0")

# Try libadwaita for native GNOME theme support
_USE_ADW = False
try:
    gi.require_version("Adw", "1")
    from gi.repository import Adw  # noqa: E402
    _USE_ADW = True
except (ValueError, ImportError):
    pass

from gi.repository import Gdk, Gio, Gtk  # noqa: E402

from .widgets.window import SheetMusicWindow


APP_ID = "com.pulpoff.midiplayer"
_RESOURCE_DIR = os.path.join(os.path.dirname(__file__), "resources")


_BaseApp = Adw.Application if _USE_ADW else Gtk.Application


class MidiPlayerApp(_BaseApp):
    def __init__(self) -> None:
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.HANDLES_OPEN,
        )
        self._window: SheetMusicWindow | None = None

    def do_startup(self) -> None:
        _BaseApp.do_startup(self)

        # Register the icon search path
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
