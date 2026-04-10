"""GTK4 + libadwaita ApplicationWindow — the main midiplayer window.

Uses Adw.ApplicationWindow with Adw.HeaderBar for proper GNOME theme
integration (dark mode, rounded corners, CSD). Falls back to plain
Gtk.ApplicationWindow + PopoverMenuBar if libadwaita is absent.
"""

from __future__ import annotations

import json
import os
from typing import List, Optional

import gi

gi.require_version("Gtk", "4.0")

_USE_ADW = False
try:
    gi.require_version("Adw", "1")
    from gi.repository import Adw  # noqa: E402
    _USE_ADW = True
except (ValueError, ImportError):
    pass

from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

from ..audio_player import AudioPlayer
from ..midi_file import MidiFile
from ..midi_file_reader import MidiFileException
from ..midi_options import MidiOptions
from ..sheet_music import SheetMusic
from .piano_widget import PianoWidget
from .player_widget import PlayerWidget
from .sheet_music_widget import SheetMusicWidget


_BaseWindow = Adw.ApplicationWindow if _USE_ADW else Gtk.ApplicationWindow


class SheetMusicWindow(_BaseWindow):
    def __init__(self, app) -> None:
        super().__init__(application=app, title="MIDI player")
        # Width only — height will be determined by content (no empty space)
        self.set_default_size(980, -1)
        self.set_icon_name("midiplayer")

        self.midifile: Optional[MidiFile] = None
        self.options: Optional[MidiOptions] = None
        self.sheet: Optional[SheetMusic] = None
        self.audio = AudioPlayer()

        # Recent files (persisted in ~/.config/midiplayer/recent.json)
        self._recent_files: List[str] = self._load_recent_files()
        self._recent_menu: Optional[Gio.Menu] = None

        self._install_actions(app)

        # Build the menu model
        menu_model = self._build_menu_model()

        # Main content box
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        if _USE_ADW:
            # Use Adw.HeaderBar with a menu button for native GNOME look
            header = Adw.HeaderBar()
            header.set_title_widget(Adw.WindowTitle(title="MIDI player", subtitle=""))
            self._window_title = header.get_title_widget()

            # Primary menu button (hamburger)
            menu_button = Gtk.MenuButton()
            menu_button.set_icon_name("open-menu-symbolic")
            menu_button.set_menu_model(menu_model)
            header.pack_end(menu_button)

            # Open button on the left
            open_button = Gtk.Button(icon_name="document-open-symbolic")
            open_button.set_tooltip_text("Open MIDI file")
            open_button.connect("clicked", lambda b: self._action_open(None, None))
            header.pack_start(open_button)

            toolbar_view = Adw.ToolbarView()
            toolbar_view.add_top_bar(header)
            toolbar_view.set_content(content)
            self.set_content(toolbar_view)
        else:
            # Fallback: plain menu bar
            content.append(Gtk.PopoverMenuBar.new_from_model(menu_model))
            self.set_child(content)

        # Player toolbar row
        self.player = PlayerWidget(self.audio)
        self.player.set_pulse_handler(self._on_player_pulse)
        content.append(self.player)

        content.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # Piano panel — always visible, scales to fill width
        self.piano = PianoWidget(white_key_width=14)
        self.piano.set_margin_top(4)
        self.piano.set_margin_bottom(4)
        content.append(self.piano)

        self._sheet_separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        content.append(self._sheet_separator)

        # Scrollable sheet music area — hidden until a file is loaded
        self.scroller = Gtk.ScrolledWindow()
        self.scroller.set_hexpand(True)
        self.scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self.sheet_widget = SheetMusicWidget()
        self.sheet_widget.set_seek_handler(self._on_sheet_click)
        self.sheet_widget.set_scroller(self.scroller)
        self.scroller.set_child(self.sheet_widget)
        content.append(self.scroller)

        # Placeholder label shown when no MIDI is loaded (no vexpand — no empty space)
        self._placeholder = Gtk.Label(label="Use the menu or Ctrl+O to open a MIDI file")
        self._placeholder.set_margin_top(12)
        self._placeholder.set_margin_bottom(12)
        self._placeholder.add_css_class("dim-label")
        content.append(self._placeholder)

        # Start with sheet area hidden
        self._set_sheet_visible(False)
        self._update_title()

        # Keyboard shortcuts
        app.set_accels_for_action("win.zoom_in", ["plus", "equal", "KP_Add", "<Control>plus", "<Control>equal"])
        app.set_accels_for_action("win.zoom_out", ["minus", "KP_Subtract", "<Control>minus"])
        app.set_accels_for_action("win.zoom_reset", ["0", "<Control>0"])
        app.set_accels_for_action("win.open", ["<Control>o"])
        app.set_accels_for_action("win.quit", ["<Control>q"])
        app.set_accels_for_action("win.close", ["<Control>w"])

    def _set_sheet_visible(self, visible: bool) -> None:
        self.scroller.set_visible(visible)
        self._sheet_separator.set_visible(visible)
        self._placeholder.set_visible(not visible)

    # ----------------------------------------------------------------------
    # Actions + menu
    # ----------------------------------------------------------------------

    def _install_actions(self, app) -> None:
        simple_actions = {
            "open": self._action_open,
            "close": self._action_close,
            "quit": self._action_quit,
            "about": self._action_about,
            "zoom_in": self._action_zoom_in,
            "zoom_out": self._action_zoom_out,
            "zoom_reset": self._action_zoom_reset,
            "scroll_horizontal": self._action_scroll_horizontal,
            "scroll_vertical": self._action_scroll_vertical,
            "show_note_letters": self._action_show_note_letters,
            "show_lyrics": self._action_show_lyrics,
            "show_measures": self._action_show_measures,
            "large_notes": self._action_large_notes,
            "two_staffs": self._action_two_staffs,
        }
        for name, cb in simple_actions.items():
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", cb)
            self.add_action(action)

        # Recent file actions (recent0..recent3)
        for i in range(4):
            action = Gio.SimpleAction.new(f"recent{i}", None)
            action.connect("activate", self._make_recent_handler(i))
            self.add_action(action)

    def _make_recent_handler(self, index: int):
        def handler(_action, _param):
            if index < len(self._recent_files):
                path = self._recent_files[index]
                if os.path.exists(path):
                    self.open_midi_file(path)
        return handler

    def _build_menu_model(self) -> Gio.Menu:
        menu = Gio.Menu()

        # File section
        file_section = Gio.Menu()
        file_section.append("Open...", "win.open")

        self._recent_menu = Gio.Menu()
        self._rebuild_recent_menu()
        file_section.append_section(None, self._recent_menu)

        close_section = Gio.Menu()
        close_section.append("Close", "win.close")
        close_section.append("Quit", "win.quit")
        file_section.append_section(None, close_section)
        menu.append_submenu("File", file_section)

        # View
        view_menu = Gio.Menu()
        view_menu.append("Zoom In", "win.zoom_in")
        view_menu.append("Zoom Out", "win.zoom_out")
        view_menu.append("Zoom 100%", "win.zoom_reset")
        scroll_section = Gio.Menu()
        scroll_section.append("Scroll Vertically", "win.scroll_vertical")
        scroll_section.append("Scroll Horizontally", "win.scroll_horizontal")
        view_menu.append_section(None, scroll_section)
        size_section = Gio.Menu()
        size_section.append("Large Notes", "win.large_notes")
        size_section.append("Show Measure Numbers", "win.show_measures")
        view_menu.append_section(None, size_section)
        menu.append_submenu("View", view_menu)

        # Help
        help_menu = Gio.Menu()
        help_menu.append("About", "win.about")
        menu.append_submenu("Help", help_menu)

        return menu

    # ----------------------------------------------------------------------
    # Action handlers
    # ----------------------------------------------------------------------

    def _action_open(self, _action, _param) -> None:
        dialog = Gtk.FileDialog.new()
        dialog.set_title("Open MIDI file")
        midi_filter = Gtk.FileFilter()
        midi_filter.set_name("MIDI files")
        midi_filter.add_pattern("*.mid")
        midi_filter.add_pattern("*.midi")
        dialog.set_default_filter(midi_filter)
        dialog.open(self, None, self._on_open_response)

    def _on_open_response(self, dialog, result) -> None:
        try:
            gfile = dialog.open_finish(result)
        except GLib.Error:
            return
        if gfile is None:
            return
        path = gfile.get_path()
        if path:
            self.open_midi_file(path)

    def _action_close(self, _action, _param) -> None:
        self.audio.stop()
        self.midifile = None
        self.options = None
        self.sheet = None
        self.sheet_widget.set_sheet(None)
        self.piano.set_midi_file(None, None)
        self._set_sheet_visible(False)
        self._update_title()

    def _action_quit(self, _action, _param) -> None:
        self.audio.close()
        self.destroy()

    def _action_about(self, _action, _param) -> None:
        icon_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "resources", "midiplayer.svg"
        )
        logo = None
        try:
            from gi.repository import GdkPixbuf  # noqa: E402
            logo = GdkPixbuf.Pixbuf.new_from_file_at_scale(icon_path, 128, 128, True)
            logo = Gdk.Texture.new_for_pixbuf(logo)
        except Exception:
            pass

        if _USE_ADW:
            about = Adw.AboutWindow(
                transient_for=self,
                application_name="MIDI player",
                application_icon="midiplayer",
                version="0.1.2",
                comments=(
                    "A native GNOME MIDI player with piano keyboard\n"
                    "and scrolling note sheet display.\n"
                    "Inspired by classic MIDI players from the Windows 3.11 era."
                ),
                website="https://github.com/pulpoff/midiplayer",
                issue_url="https://github.com/pulpoff/midiplayer/issues",
                license_type=Gtk.License.GPL_2_0,
                copyright="Pashkovsky Alexei, 2026",
            )
            about.present()
        else:
            about = Gtk.AboutDialog(
                transient_for=self,
                modal=True,
                program_name="MIDI player",
                version="0.1.2",
                comments=(
                    "A native GNOME MIDI player with piano keyboard\n"
                    "and scrolling note sheet display.\n"
                    "Inspired by classic MIDI players from the Windows 3.11 era."
                ),
                website="https://github.com/pulpoff/midiplayer",
                website_label="github.com/pulpoff/midiplayer",
                license_type=Gtk.License.GPL_2_0,
                copyright="Pashkovsky Alexei, 2026",
            )
            if logo is not None:
                about.set_logo(logo)
            about.present()

    def _action_zoom_in(self, _action, _param) -> None:
        if self.sheet is not None:
            self.sheet.set_zoom(min(4.0, self.sheet.zoom + 0.1))
            self.sheet_widget.set_sheet(self.sheet)

    def _action_zoom_out(self, _action, _param) -> None:
        if self.sheet is not None:
            self.sheet.set_zoom(max(0.3, self.sheet.zoom - 0.1))
            self.sheet_widget.set_sheet(self.sheet)

    def _action_zoom_reset(self, _action, _param) -> None:
        if self.sheet is not None:
            self.sheet.set_zoom(1.0)
            self.sheet_widget.set_sheet(self.sheet)

    def _action_scroll_horizontal(self, _action, _param) -> None:
        if self.options is not None:
            self.options.scrollVert = False
            self._reload_sheet()

    def _action_scroll_vertical(self, _action, _param) -> None:
        if self.options is not None:
            self.options.scrollVert = True
            self._reload_sheet()

    def _action_show_note_letters(self, _action, _param) -> None:
        if self.options is not None:
            self.options.showNoteLetters = (
                MidiOptions.NoteNameLetter
                if self.options.showNoteLetters == MidiOptions.NoteNameNone
                else MidiOptions.NoteNameNone
            )
            self._reload_sheet()

    def _action_show_lyrics(self, _action, _param) -> None:
        if self.options is not None:
            self.options.showLyrics = not self.options.showLyrics
            self._reload_sheet()

    def _action_show_measures(self, _action, _param) -> None:
        if self.options is not None:
            self.options.showMeasures = not self.options.showMeasures
            self._reload_sheet()

    def _action_large_notes(self, _action, _param) -> None:
        if self.options is not None:
            self.options.largeNoteSize = not self.options.largeNoteSize
            self._reload_sheet()

    def _action_two_staffs(self, _action, _param) -> None:
        if self.options is not None:
            self.options.twoStaffs = not self.options.twoStaffs
            self._reload_sheet()

    # ----------------------------------------------------------------------
    # File loading
    # ----------------------------------------------------------------------

    def open_midi_file(self, path: str, autoplay: bool = False) -> None:
        try:
            self.midifile = MidiFile(path)
        except MidiFileException as exc:
            self._show_error(f"Could not open {path}: {exc}")
            return
        self.options = MidiOptions(self.midifile)
        self.player.reset()
        self._reload_sheet()
        self.audio.set_midi_file(self.midifile, self.options)
        self.player.set_total_pulses(self.midifile.TotalPulses)
        self._set_sheet_visible(True)
        self._update_title()
        self._add_recent_file(path)
        if autoplay:
            self.player._on_play_pause(None)

    def _reload_sheet(self) -> None:
        if self.midifile is None or self.options is None:
            return
        self.sheet = SheetMusic(self.midifile, self.options)
        self.sheet_widget.set_sheet(self.sheet)
        self.piano.set_shade_colors(self.options.shadeColor, self.options.shade2Color)
        self.piano.set_midi_file(self.midifile, self.options)

    def _update_title(self) -> None:
        if _USE_ADW and hasattr(self, '_window_title'):
            if self.midifile is None:
                self._window_title.set_title("MIDI player")
                self._window_title.set_subtitle("")
            else:
                self._window_title.set_title("MIDI player")
                self._window_title.set_subtitle(os.path.basename(self.midifile.FileName))
        else:
            if self.midifile is None:
                self.set_title("MIDI player")
            else:
                self.set_title(
                    f"{os.path.basename(self.midifile.FileName)} - MIDI player"
                )

    def _show_error(self, message: str) -> None:
        if _USE_ADW:
            dialog = Adw.MessageDialog(
                transient_for=self,
                heading="Error",
                body=message,
            )
            dialog.add_response("ok", "OK")
            dialog.present()
        else:
            dialog = Gtk.MessageDialog(
                transient_for=self,
                modal=True,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text=message,
            )
            dialog.connect("response", lambda d, r: d.destroy())
            dialog.present()

    # ----------------------------------------------------------------------
    # Playback highlight callbacks
    # ----------------------------------------------------------------------

    def _on_player_pulse(self, pulse: float) -> None:
        self.sheet_widget.set_current_pulse(pulse)
        self.piano.set_current_pulse(pulse)

    def _on_sheet_click(self, pulse: int) -> None:
        self.audio.seek_to(pulse)
        self._on_player_pulse(pulse)

    # ----------------------------------------------------------------------
    # Recent files
    # ----------------------------------------------------------------------

    _MAX_RECENT = 4
    _CONFIG_DIR = os.path.join(
        os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
        "midiplayer",
    )
    _RECENT_PATH = os.path.join(_CONFIG_DIR, "recent.json")

    @staticmethod
    def _load_recent_files() -> List[str]:
        try:
            with open(SheetMusicWindow._RECENT_PATH) as f:
                data = json.load(f)
            if isinstance(data, list):
                return [p for p in data if isinstance(p, str)][:SheetMusicWindow._MAX_RECENT]
        except Exception:
            pass
        return []

    def _save_recent_files(self) -> None:
        try:
            os.makedirs(self._CONFIG_DIR, exist_ok=True)
            with open(self._RECENT_PATH, "w") as f:
                json.dump(self._recent_files, f)
        except Exception:
            pass

    def _add_recent_file(self, path: str) -> None:
        abspath = os.path.abspath(path)
        self._recent_files = [p for p in self._recent_files if p != abspath]
        self._recent_files.insert(0, abspath)
        self._recent_files = self._recent_files[: self._MAX_RECENT]
        self._save_recent_files()
        self._rebuild_recent_menu()

    def _rebuild_recent_menu(self) -> None:
        if self._recent_menu is None:
            return
        self._recent_menu.remove_all()
        for i, path in enumerate(self._recent_files):
            if i >= self._MAX_RECENT:
                break
            label = os.path.basename(path)
            self._recent_menu.append(label, f"win.recent{i}")
