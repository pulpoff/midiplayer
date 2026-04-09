"""Port of SheetMusic.cs — the layout engine.

Takes a parsed MidiFile + MidiOptions and produces a list of ``Staff``
objects ready for rendering. Also hosts the per-track chord colour map
and the zoom factor.

The GTK4 widget wrapper lives in ``widgets.sheet_music_widget`` — this
module is toolkit-agnostic and only depends on Cairo at draw time.
"""

from __future__ import annotations

from typing import List, Optional

from . import sheet_constants as SC
from .chord_symbol import ChordSymbol
from .clef_measures import ClefMeasures
from .key_signature import KeySignature
from .midi_file import MidiFile
from .midi_options import MidiOptions
from .music_theory import Clef, NoteDuration, NoteScale, TimeSignature
from .staff import Staff
from .symbol_widths import SymbolWidths
from .symbols import (
    AccidSymbol,
    BarSymbol,
    BlankSymbol,
    ClefSymbol,
    LyricSymbol,
    MusicSymbol,
    RestSymbol,
    TimeSigSymbol,
)


class SheetMusic:
    """The complete laid-out sheet music for a MidiFile + MidiOptions."""

    def __init__(self, midifile: MidiFile, options: Optional[MidiOptions] = None):
        if options is None:
            options = MidiOptions(midifile)

        self.filename = midifile.FileName
        self.zoom = 1.0
        self.scrollVert = options.scrollVert
        self.showNoteLetters = options.showNoteLetters
        self.shade_color = options.shadeColor
        self.shade2_color = options.shade2Color

        # Per-notescale color array (defaults to black)
        self.note_colors = list(options.colors) if options.colors else [(0, 0, 0)] * 12

        SC.set_note_size(options.largeNoteSize)

        tracks = midifile.change_midi_notes(options)
        time = options.time if options.time is not None else midifile.Time
        if options.key == -1:
            self.mainkey = self._guess_key_signature(tracks)
        else:
            self.mainkey = KeySignature.from_notescale(options.key)

        self.numtracks = len(tracks)
        self._timesig = time
        self._total_pulses = midifile.TotalPulses
        last_start = midifile.end_time() + options.shifttime

        # Create all symbols per track
        symbols: List[List[MusicSymbol]] = []
        for track in tracks:
            clefs = ClefMeasures(track.Notes, time.Measure)
            chords = self._create_chords(track.Notes, self.mainkey, time, clefs)
            symbols.append(self._create_symbols(chords, clefs, time, last_start))

        lyrics: Optional[List[Optional[List[LyricSymbol]]]] = None
        if options.showLyrics:
            lyrics = SheetMusic._get_lyrics(tracks)

        widths = SymbolWidths(symbols, lyrics)
        SheetMusic._align_symbols(symbols, widths, options)

        self.staffs = self._create_staffs(symbols, self.mainkey, options, time.Measure)
        SheetMusic._create_all_beamed_chords(symbols, time)
        if lyrics is not None:
            for staff in self.staffs:
                staff.add_lyrics(lyrics[staff.Track])
        for staff in self.staffs:
            staff.calculate_height()

        self._compute_bounds()

    # C# property aliases ---------------------------------------------------

    @property
    def MainKey(self) -> KeySignature:
        return self.mainkey

    @property
    def ShowNoteLetters(self) -> int:
        return self.showNoteLetters

    def note_color(self, number: int) -> tuple:
        return self.note_colors[NoteScale.from_number(number)]

    # ----------------------------------------------------------------------

    def _guess_key_signature(self, tracks) -> KeySignature:
        notenums = [n.Number for t in tracks for n in t.Notes]
        return KeySignature.guess(notenums)

    def _create_chords(
        self, midinotes, key: KeySignature, time: TimeSignature, clefs: ClefMeasures
    ) -> List[ChordSymbol]:
        chords: List[ChordSymbol] = []
        i = 0
        while i < len(midinotes):
            starttime = midinotes[i].StartTime
            clef = clefs.get_clef(starttime)
            group = [midinotes[i]]
            i += 1
            while i < len(midinotes) and midinotes[i].StartTime == starttime:
                group.append(midinotes[i])
                i += 1
            chords.append(ChordSymbol(group, key, time, clef, self))
        return chords

    def _create_symbols(
        self,
        chords: List[ChordSymbol],
        clefs: ClefMeasures,
        time: TimeSignature,
        last_start: int,
    ) -> List[MusicSymbol]:
        symbols = self._add_bars(chords, time, last_start)
        symbols = self._add_rests(symbols, time)
        symbols = self._add_clef_changes(symbols, clefs, time)
        return symbols

    def _add_bars(
        self,
        chords: List[ChordSymbol],
        time: TimeSignature,
        last_start: int,
    ) -> List[MusicSymbol]:
        symbols: List[MusicSymbol] = [TimeSigSymbol(time.Numerator, time.Denominator)]
        measuretime = 0
        i = 0
        while i < len(chords):
            if measuretime <= chords[i].StartTime:
                symbols.append(BarSymbol(measuretime))
                measuretime += time.Measure
            else:
                symbols.append(chords[i])
                i += 1
        while measuretime < last_start:
            symbols.append(BarSymbol(measuretime))
            measuretime += time.Measure
        symbols.append(BarSymbol(measuretime))
        return symbols

    def _add_rests(
        self, symbols: List[MusicSymbol], time: TimeSignature
    ) -> List[MusicSymbol]:
        prevtime = 0
        result: List[MusicSymbol] = []
        for symbol in symbols:
            starttime = symbol.StartTime
            rests = self._get_rests(time, prevtime, starttime)
            if rests:
                result.extend(rests)
            result.append(symbol)
            if isinstance(symbol, ChordSymbol):
                prevtime = max(symbol.EndTime, prevtime)
            else:
                prevtime = max(starttime, prevtime)
        return result

    def _get_rests(
        self, time: TimeSignature, start: int, end: int
    ) -> Optional[List[RestSymbol]]:
        if end - start < 0:
            return None
        dur = time.get_note_duration(end - start)
        if dur in (
            NoteDuration.Whole,
            NoteDuration.Half,
            NoteDuration.Quarter,
            NoteDuration.Eighth,
        ):
            return [RestSymbol(start, dur)]
        if dur == NoteDuration.DottedHalf:
            return [
                RestSymbol(start, NoteDuration.Half),
                RestSymbol(start + time.Quarter * 2, NoteDuration.Quarter),
            ]
        if dur == NoteDuration.DottedQuarter:
            return [
                RestSymbol(start, NoteDuration.Quarter),
                RestSymbol(start + time.Quarter, NoteDuration.Eighth),
            ]
        if dur == NoteDuration.DottedEighth:
            return [
                RestSymbol(start, NoteDuration.Eighth),
                RestSymbol(start + time.Quarter // 2, NoteDuration.Sixteenth),
            ]
        return None

    def _add_clef_changes(
        self,
        symbols: List[MusicSymbol],
        clefs: ClefMeasures,
        time: TimeSignature,
    ) -> List[MusicSymbol]:
        result: List[MusicSymbol] = []
        prevclef = clefs.get_clef(0)
        for symbol in symbols:
            if isinstance(symbol, BarSymbol):
                clef = clefs.get_clef(symbol.StartTime)
                if clef != prevclef:
                    result.append(ClefSymbol(clef, symbol.StartTime - 1, True))
                prevclef = clef
            result.append(symbol)
        return result

    # ----------------------------------------------------------------------

    @staticmethod
    def _align_symbols(
        allsymbols: List[List[MusicSymbol]],
        widths: SymbolWidths,
        options: MidiOptions,
    ) -> None:
        if options.showMeasures:
            for symbols in allsymbols:
                for sym in symbols:
                    if isinstance(sym, BarSymbol):
                        sym.Width = sym.Width + SC.NoteWidth

        for track in range(len(allsymbols)):
            symbols = allsymbols[track]
            result: List[MusicSymbol] = []
            i = 0
            for start in widths.StartTimes:
                while (
                    i < len(symbols)
                    and isinstance(symbols[i], BarSymbol)
                    and symbols[i].StartTime <= start
                ):
                    result.append(symbols[i])
                    i += 1
                if i < len(symbols) and symbols[i].StartTime == start:
                    while i < len(symbols) and symbols[i].StartTime == start:
                        result.append(symbols[i])
                        i += 1
                else:
                    result.append(BlankSymbol(start, 0))

            j = 0
            while j < len(result):
                if isinstance(result[j], BarSymbol):
                    j += 1
                    continue
                start = result[j].StartTime
                extra = widths.get_extra_width(track, start)
                result[j].Width = result[j].Width + extra
                while j < len(result) and result[j].StartTime == start:
                    j += 1
            allsymbols[track] = result

    @staticmethod
    def _find_consecutive_chords(
        symbols: List[MusicSymbol],
        time: TimeSignature,
        start_index: int,
        num_chords: int,
    ):
        i = start_index
        while True:
            horiz_distance = 0
            while i < len(symbols) - num_chords:
                if isinstance(symbols[i], ChordSymbol):
                    if symbols[i].Stem is not None:
                        break
                i += 1
            if i >= len(symbols) - num_chords:
                return None
            chord_indexes = [0] * num_chords
            chord_indexes[0] = i
            found = True
            for chord_index in range(1, num_chords):
                i += 1
                remaining = num_chords - 1 - chord_index
                while i < len(symbols) - remaining and isinstance(
                    symbols[i], BlankSymbol
                ):
                    horiz_distance += symbols[i].Width
                    i += 1
                if i >= len(symbols) - remaining:
                    return None
                if not isinstance(symbols[i], ChordSymbol):
                    found = False
                    break
                chord_indexes[chord_index] = i
                horiz_distance += symbols[i].Width
            if found:
                return chord_indexes, horiz_distance

    @staticmethod
    def _create_beamed_chords(
        allsymbols: List[List[MusicSymbol]],
        time: TimeSignature,
        num_chords: int,
        start_beat: bool,
    ) -> None:
        for symbols in allsymbols:
            start_index = 0
            while True:
                found = SheetMusic._find_consecutive_chords(
                    symbols, time, start_index, num_chords
                )
                if found is None:
                    break
                chord_indexes, horiz_distance = found
                chords = [symbols[idx] for idx in chord_indexes]
                if ChordSymbol.can_create_beam(chords, time, start_beat):
                    ChordSymbol.create_beam(chords, horiz_distance)
                    start_index = chord_indexes[-1] + 1
                else:
                    start_index = chord_indexes[0] + 1

    @staticmethod
    def _create_all_beamed_chords(
        allsymbols: List[List[MusicSymbol]], time: TimeSignature
    ) -> None:
        if (
            (time.Numerator == 3 and time.Denominator == 4)
            or (time.Numerator == 6 and time.Denominator == 8)
            or (time.Numerator == 6 and time.Denominator == 4)
        ):
            SheetMusic._create_beamed_chords(allsymbols, time, 6, True)
        SheetMusic._create_beamed_chords(allsymbols, time, 3, True)
        SheetMusic._create_beamed_chords(allsymbols, time, 4, True)
        SheetMusic._create_beamed_chords(allsymbols, time, 2, True)
        SheetMusic._create_beamed_chords(allsymbols, time, 2, False)

    # ----------------------------------------------------------------------

    @staticmethod
    def key_signature_width(key: KeySignature) -> int:
        clefsym = ClefSymbol(Clef.Treble, 0, False)
        result = clefsym.MinWidth
        keys = key.get_symbols(Clef.Treble)
        for symbol in keys:
            result += symbol.MinWidth
        return result + SC.LeftMargin + 5

    def _create_staffs_for_track(
        self,
        symbols: List[MusicSymbol],
        measurelen: int,
        key: KeySignature,
        options: MidiOptions,
        track: int,
        totaltracks: int,
    ) -> List[Staff]:
        keysig_width = SheetMusic.key_signature_width(key)
        start_index = 0
        thestaffs: List[Staff] = []

        while start_index < len(symbols):
            end_index = start_index
            width = keysig_width
            maxwidth = SC.PageWidth if self.scrollVert else 2_000_000

            while (
                end_index < len(symbols)
                and width + symbols[end_index].Width < maxwidth
            ):
                width += symbols[end_index].Width
                end_index += 1
            end_index -= 1

            if end_index == len(symbols) - 1:
                pass
            elif (
                symbols[start_index].StartTime // measurelen
                == symbols[end_index].StartTime // measurelen
            ):
                pass
            else:
                end_measure = symbols[end_index + 1].StartTime // measurelen
                while symbols[end_index].StartTime // measurelen == end_measure:
                    end_index -= 1

            count = end_index + 1 - start_index
            if count <= 0:
                break
            slice_ = symbols[start_index : start_index + count]
            staff = Staff(slice_, key, options, track, totaltracks)
            thestaffs.append(staff)
            start_index = end_index + 1
        return thestaffs

    def _create_staffs(
        self,
        allsymbols: List[List[MusicSymbol]],
        key: KeySignature,
        options: MidiOptions,
        measurelen: int,
    ) -> List[Staff]:
        trackstaffs: List[List[Staff]] = []
        totaltracks = len(allsymbols)
        for track in range(totaltracks):
            trackstaffs.append(
                self._create_staffs_for_track(
                    allsymbols[track], measurelen, key, options, track, totaltracks
                )
            )

        # Update each staff's EndTime so playback auto-scroll works
        for lst in trackstaffs:
            for i in range(len(lst) - 1):
                lst[i].EndTime = lst[i + 1].StartTime

        # Interleave: row 0 = Staff0 of each track, row 1 = Staff1 of each track, ...
        maxstaffs = max((len(lst) for lst in trackstaffs), default=0)
        result: List[Staff] = []
        for i in range(maxstaffs):
            for lst in trackstaffs:
                if i < len(lst):
                    result.append(lst[i])
        return result

    @staticmethod
    def _get_lyrics(tracks) -> Optional[List[Optional[List[LyricSymbol]]]]:
        has_lyrics = False
        result: List[Optional[List[LyricSymbol]]] = [None] * len(tracks)
        for tracknum, track in enumerate(tracks):
            if track.Lyrics is None:
                continue
            has_lyrics = True
            lyrics: List[LyricSymbol] = []
            for ev in track.Lyrics:
                try:
                    text = ev.Value.decode("utf-8", errors="replace")
                except Exception:
                    text = ""
                lyrics.append(LyricSymbol(ev.StartTime, text))
            result[tracknum] = lyrics
        return result if has_lyrics else None

    # ----------------------------------------------------------------------

    def _compute_bounds(self) -> None:
        width = 0
        height = 0
        for staff in self.staffs:
            width = max(width, int(staff.Width * self.zoom))
            height += int(staff.Height * self.zoom)
        self.total_width = width + 2
        self.total_height = height + SC.LeftMargin

    def set_zoom(self, value: float) -> None:
        self.zoom = value
        self._compute_bounds()

    # ----------------------------------------------------------------------
    # Drawing
    # ----------------------------------------------------------------------

    def _get_time_marker_pulses(self, interval_sec: float = 30.0) -> List[int]:
        """Return pulse times for every ``interval_sec`` seconds."""
        if not self.staffs or self._timesig is None:
            return []
        sec_per_pulse = (self._timesig.Tempo / 1_000_000.0) / self._timesig.Quarter
        if sec_per_pulse <= 0:
            return []
        pulses_per_interval = int(interval_sec / sec_per_pulse)
        if pulses_per_interval <= 0:
            return []
        result = []
        pulse = pulses_per_interval
        total = self._total_pulses
        while pulse < total:
            result.append(pulse)
            pulse += pulses_per_interval
        return result

    def draw(self, cr, clip_x: int, clip_y: int, clip_w: int, clip_h: int) -> None:
        cr.save()
        cr.scale(self.zoom, self.zoom)
        cr.set_source_rgb(1, 1, 1)
        cr.paint()
        cr.set_source_rgb(0, 0, 0)

        ypos = 0
        total_height = 0
        scaled_y = clip_y / self.zoom
        scaled_h = clip_h / self.zoom
        for staff in self.staffs:
            if ypos + staff.Height < scaled_y or ypos > scaled_y + scaled_h:
                pass
            else:
                cr.translate(0, ypos)
                staff.draw(cr, int(clip_x / self.zoom), int(clip_w / self.zoom))
                cr.translate(0, -ypos)
            ypos += staff.Height
            total_height = ypos

        # Draw 30-second time marker lines in light green
        marker_pulses = self._get_time_marker_pulses(30.0)
        if marker_pulses and self.staffs:
            # Use the first staff to map pulse -> x pixel
            first_staff = self.staffs[0]
            for pulse in marker_pulses:
                x = first_staff.x_for_pulse(pulse)
                if x > 0:
                    cr.set_source_rgba(0.4, 0.8, 0.4, 0.5)  # light green, semi-transparent
                    cr.set_line_width(1)
                    cr.move_to(x + 0.5, 0)
                    cr.line_to(x + 0.5, total_height)
                    cr.stroke()

        cr.restore()

    def shade_notes(self, cr, current_pulse: int, prev_pulse: int) -> tuple:
        """Shade notes at current_pulse and un-shade at prev_pulse.

        Returns (x_shade, y_shade) for the caller to use for auto-scroll.
        """
        cr.save()
        cr.scale(self.zoom, self.zoom)
        cr.set_source_rgb(0, 0, 0)

        ypos = 0
        x_shade = 0
        y_shade = 0
        for staff in self.staffs:
            cr.translate(0, ypos)
            x_shade = staff.shade_notes(
                cr, self.shade_color, current_pulse, prev_pulse, x_shade
            )
            cr.translate(0, -ypos)
            ypos += staff.Height
            if current_pulse >= staff.EndTime:
                y_shade += staff.Height
        cr.restore()
        return (int(x_shade * self.zoom), int((y_shade - SC.NoteHeight) * self.zoom))

    def pulse_time_for_point(self, x: int, y: int) -> int:
        """Return the pulse time corresponding to a (scaled) point."""
        sx = x / self.zoom
        sy = y / self.zoom
        yoff = 0
        for staff in self.staffs:
            if yoff <= sy <= yoff + staff.Height:
                return staff.pulse_time_for_point(int(sx))
            yoff += staff.Height
        return -1
