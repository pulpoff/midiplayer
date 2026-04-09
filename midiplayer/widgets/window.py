"""GTK4 ApplicationWindow — the main midiplayer window.

Layout matches the original MidiSheetMusic screenshot:
- Menu bar across the top: File / View / Color / Tracks / Notes / Help
- Player toolbar row: transport buttons + compact speed/volume + timeline
- Piano panel (always visible)
- Scrollable sheet music area (hidden when no MIDI loaded)
"""

from __future__ import annotations

import os
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from ..audio_player import AudioPlayer
from ..midi_file import MidiFile
from ..midi_file_reader import MidiFileException
from ..midi_options import MidiOptions
from ..sheet_music import SheetMusic
from .piano_widget import PianoWidget
from .player_widget import PlayerWidget
from .sheet_music_widget import SheetMusicWidget


class SheetMusicWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application) -> None:
        super().__init__(application=app, title="Midi Sheet Music")
        self.set_default_size(980, 720)

        self.midifile: Optional[MidiFile] = None
        self.options: Optional[MidiOptions] = None
        self.sheet: Optional[SheetMusic] = None
        self.audio = AudioPlayer()

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(root)

        # Menu bar
        self._install_actions(app)
        root.append(self._build_menu_bar())

        # Player toolbar row
        self.player = PlayerWidget(self.audio)
        self.player.set_pulse_handler(self._on_player_pulse)
        root.append(self.player)

        root.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # Piano panel — always visible, centered
        piano_wrap = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        piano_wrap.set_halign(Gtk.Align.CENTER)
        piano_wrap.set_margin_top(4)
        piano_wrap.set_margin_bottom(4)
        self.piano = PianoWidget(white_key_width=14)
        piano_wrap.append(self.piano)
        root.append(piano_wrap)

        self._sheet_separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        root.append(self._sheet_separator)

        # Scrollable sheet music area — hidden until a file is loaded
        self.scroller = Gtk.ScrolledWindow()
        self.scroller.set_hexpand(True)
        self.scroller.set_vexpand(True)
        self.sheet_widget = SheetMusicWidget()
        self.sheet_widget.set_seek_handler(self._on_sheet_click)
        self.scroller.set_child(self.sheet_widget)
        root.append(self.scroller)

        # Placeholder label shown when no MIDI is loaded
        self._placeholder = Gtk.Label(label="Use the menu File > Open to select a MIDI file")
        self._placeholder.set_vexpand(True)
        self._placeholder.set_valign(Gtk.Align.START)
        self._placeholder.set_margin_top(20)
        self._placeholder.set_margin_start(20)
        root.append(self._placeholder)

        # Start with sheet area hidden
        self._set_sheet_visible(False)
        self._update_title()

    def _set_sheet_visible(self, visible: bool) -> None:
        self.scroller.set_visible(visible)
        self._sheet_separator.set_visible(visible)
        self._placeholder.set_visible(not visible)

    # ----------------------------------------------------------------------
    # Actions + menu
    # ----------------------------------------------------------------------

    def _install_actions(self, app: Gtk.Application) -> None:
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

    def _build_menu_bar(self) -> Gtk.Widget:
        menu = Gio.Menu()

        file_menu = Gio.Menu()
        file_menu.append("Open...", "win.open")
        file_menu.append("Close", "win.close")
        file_menu.append("Quit", "win.quit")
        menu.append_submenu("File", file_menu)

        view_menu = Gio.Menu()
        view_menu.append("Zoom In", "win.zoom_in")
        view_menu.append("Zoom Out", "win.zoom_out")
        view_menu.append("Zoom 100%", "win.zoom_reset")
        scroll_menu = Gio.Menu()
        scroll_menu.append("Scroll Vertically", "win.scroll_vertical")
        scroll_menu.append("Scroll Horizontally", "win.scroll_horizontal")
        view_menu.append_section(None, scroll_menu)
        size_menu = Gio.Menu()
        size_menu.append("Large Notes", "win.large_notes")
        size_menu.append("Show Measure Numbers", "win.show_measures")
        view_menu.append_section(None, size_menu)
        menu.append_submenu("View", view_menu)

        tracks_menu = Gio.Menu()
        tracks_menu.append("Combine Into Two Staffs", "win.two_staffs")
        menu.append_submenu("Tracks", tracks_menu)

        notes_menu = Gio.Menu()
        notes_menu.append("Show Note Letters", "win.show_note_letters")
        notes_menu.append("Show Lyrics", "win.show_lyrics")
        menu.append_submenu("Notes", notes_menu)

        help_menu = Gio.Menu()
        help_menu.append("About", "win.about")
        menu.append_submenu("Help", help_menu)

        return Gtk.PopoverMenuBar.new_from_model(menu)

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
        about = Gtk.AboutDialog(
            transient_for=self,
            modal=True,
            program_name="Midi Sheet Music",
            version="0.1.0",
            comments=(
                "A modern GTK4 MIDI sheet music player for Linux.\n"
                "Based on MidiSheetMusic 2.6 by Madhav Vaidyanathan.\n"
                "Ported to Python / GTK4 / Cairo / FluidSynth."
            ),
            website="https://github.com/pulpoff/midiplayer",
            license_type=Gtk.License.GPL_2_0,
        )
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

    def open_midi_file(self, path: str) -> None:
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

    def _reload_sheet(self) -> None:
        if self.midifile is None or self.options is None:
            return
        self.sheet = SheetMusic(self.midifile, self.options)
        self.sheet_widget.set_sheet(self.sheet)
        self.piano.set_shade_colors(self.options.shadeColor, self.options.shade2Color)
        self.piano.set_midi_file(self.midifile, self.options)

    def _update_title(self) -> None:
        if self.midifile is None:
            self.set_title("Midi Sheet Music")
        else:
            self.set_title(
                f"{os.path.basename(self.midifile.FileName)} - Midi Sheet Music"
            )

    def _show_error(self, message: str) -> None:
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
