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

from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

from .widgets.window import SheetMusicWindow


APP_ID = "com.pulpoff.midiplayer"
_RESOURCE_DIR = os.path.join(os.path.dirname(__file__), "resources")

_BaseApp = Adw.Application if _USE_ADW else Gtk.Application

# Store file to open (passed via argv before GTK takes over)
_pending_file: str | None = None


class MidiPlayerApp(_BaseApp):
    def __init__(self) -> None:
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.NON_UNIQUE,
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
        global _pending_file
        window = self._ensure_window()
        if _pending_file is not None:
            path = _pending_file
            _pending_file = None
            window.open_midi_file(path)
        window.present()

    def _ensure_window(self) -> SheetMusicWindow:
        if self._window is None:
            self._window = SheetMusicWindow(self)
        return self._window


def main(argv: List[str] | None = None) -> int:
    global _pending_file
    if argv is None:
        argv = sys.argv

    # Extract MIDI file from args before GTK sees them
    # (GTK strips its own args but doesn't know about our files)
    for arg in argv[1:]:
        if not arg.startswith("-") and (arg.endswith(".mid") or arg.endswith(".midi")):
            if os.path.isfile(arg):
                _pending_file = os.path.abspath(arg)
                break

    try:
        app = MidiPlayerApp()
        # Only pass argv[0] to GTK — we handle file args ourselves
        return app.run([argv[0]] if argv else [])
    except Exception:
        import traceback
        log_dir = os.path.join(
            os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state")),
            "midiplayer",
        )
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "crash.log")
        with open(log_path, "w") as f:
            traceback.print_exc(file=f)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
