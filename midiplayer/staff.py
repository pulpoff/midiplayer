"""Port of Staff.cs.

A Staff is one horizontal row of the sheet music. It owns a slice of the
track's symbol list plus a clef + key signature drawn at the left side.
"""

from __future__ import annotations

from typing import List, Optional

from . import sheet_constants as SC
from .chord_symbol import ChordSymbol
from .key_signature import KeySignature
from .midi_options import MidiOptions
from .music_theory import Clef
from .symbols import (
    AccidSymbol,
    BarSymbol,
    ClefSymbol,
    LyricSymbol,
    MusicSymbol,
    _draw_line,
    _fill_rect,
    _set_black,
)


class Staff:
    def __init__(
        self,
        symbols: List[MusicSymbol],
        key: KeySignature,
        options: MidiOptions,
        tracknum: int,
        totaltracks: int,
    ):
        from .sheet_music import SheetMusic  # late import

        self._keysig_width = SheetMusic.key_signature_width(key)
        self.tracknum = tracknum
        self.totaltracks = totaltracks
        self.show_measures = options.showMeasures and tracknum == 0
        self.measure_length = options.time.Measure if options.time else 0
        clef = Staff._find_clef(symbols)

        self.clefsym = ClefSymbol(clef, 0, False)
        self.keys = key.get_symbols(clef)
        self.symbols = symbols
        self.lyrics: Optional[List[LyricSymbol]] = None

        self._width = 0
        self._height = 0
        self._ytop = 0
        self._starttime = 0
        self._endtime = 0

        self._calculate_width(options.scrollVert)
        self.calculate_height()
        self._calculate_start_end_time()
        self._full_justify()

    # C# property aliases ---------------------------------------------------

    @property
    def Width(self) -> int:
        return self._width

    @property
    def Height(self) -> int:
        return self._height

    @property
    def Track(self) -> int:
        return self.tracknum

    @property
    def StartTime(self) -> int:
        return self._starttime

    @property
    def EndTime(self) -> int:
        return self._endtime

    @EndTime.setter
    def EndTime(self, value: int) -> None:
        self._endtime = value

    # ----------------------------------------------------------------------

    @staticmethod
    def _find_clef(symbols: List[MusicSymbol]) -> Clef:
        for m in symbols:
            if isinstance(m, ChordSymbol):
                return m.Clef
        return Clef.Treble

    def calculate_height(self) -> None:
        above = 0
        below = 0
        for s in self.symbols:
            above = max(above, s.AboveStaff)
            below = max(below, s.BelowStaff)
        above = max(above, self.clefsym.AboveStaff)
        below = max(below, self.clefsym.BelowStaff)
        if self.show_measures:
            above = max(above, SC.NoteHeight * 3)
        self._ytop = above + SC.NoteHeight
        self._height = SC.NoteHeight * 5 + self._ytop + below
        if self.lyrics is not None:
            self._height += 12
        if self.tracknum == self.totaltracks - 1:
            self._height += SC.NoteHeight * 3

    def _calculate_width(self, scroll_vert: bool) -> None:
        if scroll_vert:
            self._width = SC.PageWidth
            return
        self._width = self._keysig_width
        for s in self.symbols:
            self._width += s.Width

    def _calculate_start_end_time(self) -> None:
        if not self.symbols:
            return
        self._starttime = self.symbols[0].StartTime
        self._endtime = self.symbols[0].StartTime
        for m in self.symbols:
            if self._endtime < m.StartTime:
                self._endtime = m.StartTime
            if isinstance(m, ChordSymbol):
                if self._endtime < m.EndTime:
                    self._endtime = m.EndTime

    def _full_justify(self) -> None:
        if self._width != SC.PageWidth:
            return
        totalwidth = self._keysig_width
        totalsymbols = 0
        i = 0
        while i < len(self.symbols):
            start = self.symbols[i].StartTime
            totalsymbols += 1
            totalwidth += self.symbols[i].Width
            i += 1
            while i < len(self.symbols) and self.symbols[i].StartTime == start:
                totalwidth += self.symbols[i].Width
                i += 1

        if totalsymbols == 0:
            return
        extrawidth = (SC.PageWidth - totalwidth - 1) // totalsymbols
        if extrawidth > SC.NoteHeight * 2:
            extrawidth = SC.NoteHeight * 2
        if extrawidth < 0:
            extrawidth = 0

        i = 0
        while i < len(self.symbols):
            start = self.symbols[i].StartTime
            self.symbols[i].Width += extrawidth
            i += 1
            while i < len(self.symbols) and self.symbols[i].StartTime == start:
                i += 1

    def add_lyrics(self, tracklyrics: Optional[List[LyricSymbol]]) -> None:
        if tracklyrics is None:
            return
        self.lyrics = []
        xpos = 0
        symbolindex = 0
        for lyric in tracklyrics:
            if lyric.StartTime < self._starttime:
                continue
            if lyric.StartTime > self._endtime:
                break
            while (
                symbolindex < len(self.symbols)
                and self.symbols[symbolindex].StartTime < lyric.StartTime
            ):
                xpos += self.symbols[symbolindex].Width
                symbolindex += 1
            lyric.X = xpos
            if symbolindex < len(self.symbols) and isinstance(
                self.symbols[symbolindex], BarSymbol
            ):
                lyric.X += SC.NoteWidth
            self.lyrics.append(lyric)
        if not self.lyrics:
            self.lyrics = None

    # ----------------------------------------------------------------------
    # Drawing
    # ----------------------------------------------------------------------

    def draw(self, cr, clip_x: int, clip_w: int) -> None:
        _set_black(cr)

        xpos = SC.LeftMargin + 5

        cr.translate(xpos, 0)
        self.clefsym.draw(cr, self._ytop)
        cr.translate(-xpos, 0)
        xpos += self.clefsym.Width

        for a in self.keys:
            cr.translate(xpos, 0)
            a.draw(cr, self._ytop)
            cr.translate(-xpos, 0)
            xpos += a.Width

        for s in self.symbols:
            # Simple culling: only draw symbols inside clip range
            if xpos <= clip_x + clip_w + 50 and xpos + s.Width + 50 >= clip_x:
                cr.translate(xpos, 0)
                s.draw(cr, self._ytop)
                cr.translate(-xpos, 0)
            xpos += s.Width

        self._draw_horiz_lines(cr)
        self._draw_end_lines(cr)

        if self.show_measures:
            self._draw_measure_numbers(cr)
        if self.lyrics is not None:
            self._draw_lyrics(cr)

    def _draw_horiz_lines(self, cr) -> None:
        _set_black(cr)
        y = self._ytop - SC.LineWidth
        for _ in range(5):
            _draw_line(cr, SC.LeftMargin, y, self._width - 1, y, 1)
            y += SC.LineWidth + SC.LineSpace

    def _draw_end_lines(self, cr) -> None:
        _set_black(cr)
        if self.tracknum == 0:
            ystart = self._ytop - SC.LineWidth
        else:
            ystart = 0
        if self.tracknum == self.totaltracks - 1:
            yend = self._ytop + 4 * SC.NoteHeight
        else:
            yend = self._height
        _draw_line(cr, SC.LeftMargin, ystart, SC.LeftMargin, yend, 1)
        _draw_line(cr, self._width - 1, ystart, self._width - 1, yend, 1)

    def _draw_measure_numbers(self, cr) -> None:
        _set_black(cr)
        xpos = self._keysig_width
        ypos = self._ytop - SC.NoteHeight * 3
        for s in self.symbols:
            if isinstance(s, BarSymbol):
                measure = 1 + s.StartTime // self.measure_length
                cr.save()
                cr.set_font_size(10)
                cr.move_to(xpos + SC.NoteWidth // 2, ypos + 10)
                cr.show_text(str(measure))
                cr.restore()
            xpos += s.Width

    def _draw_lyrics(self, cr) -> None:
        if self.lyrics is None:
            return
        _set_black(cr)
        xpos = self._keysig_width
        ypos = self._height - 12
        cr.save()
        cr.set_font_size(10)
        for lyric in self.lyrics:
            cr.move_to(xpos + lyric.X, ypos + 10)
            cr.show_text(lyric.Text)
        cr.restore()

    # ----------------------------------------------------------------------
    # Playback shading
    # ----------------------------------------------------------------------

    def shade_notes(
        self,
        cr,
        shade_color: tuple,
        current_pulse: int,
        prev_pulse: int,
        x_shade: int,
    ) -> int:
        """Shade the chord at ``current_pulse`` and un-shade the one at ``prev_pulse``.

        Returns the updated ``x_shade`` (x pixel of the currently shaded note),
        which the window uses for auto-scroll.
        """
        if (
            (self._starttime > prev_pulse or self._endtime < prev_pulse)
            and (self._starttime > current_pulse or self._endtime < current_pulse)
        ):
            return x_shade

        xpos = self._keysig_width

        for i, curr in enumerate(self.symbols):
            if isinstance(curr, BarSymbol):
                xpos += curr.Width
                continue

            start = curr.StartTime
            if i + 2 < len(self.symbols) and isinstance(
                self.symbols[i + 1], BarSymbol
            ):
                end = self.symbols[i + 2].StartTime
            elif i + 1 < len(self.symbols):
                end = self.symbols[i + 1].StartTime
            else:
                end = self._endtime

            if start > prev_pulse and start > current_pulse:
                if x_shade == 0:
                    x_shade = xpos
                return x_shade

            if (
                start <= current_pulse < end
                and start <= prev_pulse < end
            ):
                x_shade = xpos
                return x_shade

            if start <= prev_pulse < end:
                # Erase previous shade with white background, redraw symbol
                cr.save()
                cr.set_source_rgb(1, 1, 1)
                _fill_rect(cr, xpos - 2, -2, curr.Width + 4, self._height + 4)
                cr.restore()
                cr.translate(xpos, 0)
                _set_black(cr)
                curr.draw(cr, self._ytop)
                cr.translate(-xpos, 0)
                self._redraw_staff_lines_near(cr, xpos, curr.Width)

            if start <= current_pulse < end:
                x_shade = xpos
                cr.save()
                r, g, b = shade_color
                cr.set_source_rgb(r / 255.0, g / 255.0, b / 255.0)
                _fill_rect(cr, xpos, 0, curr.Width, self._height)
                cr.restore()
                cr.translate(xpos, 0)
                _set_black(cr)
                curr.draw(cr, self._ytop)
                cr.translate(-xpos, 0)
                self._redraw_staff_lines_near(cr, xpos, curr.Width)

            xpos += curr.Width
        return x_shade

    def _redraw_staff_lines_near(self, cr, xpos: int, width: int) -> None:
        _set_black(cr)
        y = self._ytop - SC.LineWidth
        for _ in range(5):
            _draw_line(cr, xpos - 2, y, xpos + width + 2, y, 1)
            y += SC.LineWidth + SC.LineSpace

    def pulse_time_for_point(self, x: int) -> int:
        xpos = self._keysig_width
        pulse_time = self._starttime
        for sym in self.symbols:
            pulse_time = sym.StartTime
            if x <= xpos + sym.Width:
                return pulse_time
            xpos += sym.Width
        return pulse_time
