"""Port of Stem.cs.

A Stem is owned by a ChordSymbol and draws the vertical stem plus any
flags or horizontal beams. The coordinate math is identical to the C#
source — everything is relative to ``ytop`` (the top of the staff) and
``topstaff`` (the WhiteNote at the top line of the staff).
"""

from __future__ import annotations

import math
from typing import Optional

from . import sheet_constants as SC
from .music_theory import NoteDuration, WhiteNote
from .symbols import _draw_bezier, _draw_line, _set_black


class Stem:
    Up = 1
    Down = 2
    LeftSide = 1
    RightSide = 2

    def __init__(
        self,
        bottom: WhiteNote,
        top: WhiteNote,
        duration: NoteDuration,
        direction: int,
        overlap: bool,
    ):
        self.top = top
        self.bottom = bottom
        self.duration = duration
        self.direction = direction
        self.notesoverlap = overlap
        if direction == Stem.Up or overlap:
            self.side = Stem.RightSide
        else:
            self.side = Stem.LeftSide
        self.end = self.calculate_end()
        self.pair: Optional["Stem"] = None
        self.width_to_pair = 0
        self.receiver_in_pair = False

    # C# property aliases ---------------------------------------------------

    @property
    def Direction(self) -> int:
        return self.direction

    @Direction.setter
    def Direction(self, value: int) -> None:
        self.change_direction(value)

    @property
    def Duration(self) -> NoteDuration:
        return self.duration

    @property
    def Top(self) -> WhiteNote:
        return self.top

    @property
    def Bottom(self) -> WhiteNote:
        return self.bottom

    @property
    def End(self) -> WhiteNote:
        return self.end

    @End.setter
    def End(self, value: WhiteNote) -> None:
        self.end = value

    @property
    def Receiver(self) -> bool:
        return self.receiver_in_pair

    @Receiver.setter
    def Receiver(self, value: bool) -> None:
        self.receiver_in_pair = value

    @property
    def isBeam(self) -> bool:
        return self.receiver_in_pair or (self.pair is not None)

    # ----------------------------------------------------------------------

    def calculate_end(self) -> WhiteNote:
        if self.direction == Stem.Up:
            w = self.top.add(6)
            if self.duration == NoteDuration.Sixteenth:
                w = w.add(2)
            elif self.duration == NoteDuration.ThirtySecond:
                w = w.add(4)
            return w
        if self.direction == Stem.Down:
            w = self.bottom.add(-6)
            if self.duration == NoteDuration.Sixteenth:
                w = w.add(-2)
            elif self.duration == NoteDuration.ThirtySecond:
                w = w.add(-4)
            return w
        return self.top

    def change_direction(self, new_direction: int) -> None:
        self.direction = new_direction
        if self.direction == Stem.Up or self.notesoverlap:
            self.side = Stem.RightSide
        else:
            self.side = Stem.LeftSide
        self.end = self.calculate_end()

    def set_pair(self, pair: "Stem", width_to_pair: int) -> None:
        self.pair = pair
        self.width_to_pair = width_to_pair

    # ----------------------------------------------------------------------
    # Drawing
    # ----------------------------------------------------------------------

    def draw(self, cr, ytop: int, topstaff: WhiteNote) -> None:
        if self.duration == NoteDuration.Whole:
            return

        _set_black(cr)
        self._draw_vertical_line(cr, ytop, topstaff)
        if self.duration in (
            NoteDuration.Quarter,
            NoteDuration.DottedQuarter,
            NoteDuration.Half,
            NoteDuration.DottedHalf,
        ) or self.receiver_in_pair:
            return

        if self.pair is not None:
            self._draw_horiz_bar_stem(cr, ytop, topstaff)
        else:
            self._draw_curvy_stem(cr, ytop, topstaff)

    def _draw_vertical_line(self, cr, ytop: int, topstaff: WhiteNote) -> None:
        if self.side == Stem.LeftSide:
            xstart = SC.LineSpace // 4 + 1
        else:
            xstart = SC.LineSpace // 4 + SC.NoteWidth

        if self.direction == Stem.Up:
            y1 = (
                ytop
                + topstaff.dist(self.bottom) * SC.NoteHeight // 2
                + SC.NoteHeight // 4
            )
            ystem = ytop + topstaff.dist(self.end) * SC.NoteHeight // 2
            _draw_line(cr, xstart, y1, xstart, ystem, 1)
        elif self.direction == Stem.Down:
            y1 = (
                ytop
                + topstaff.dist(self.top) * SC.NoteHeight // 2
                + SC.NoteHeight
            )
            if self.side == Stem.LeftSide:
                y1 -= SC.NoteHeight // 4
            else:
                y1 -= SC.NoteHeight // 2
            ystem = (
                ytop
                + topstaff.dist(self.end) * SC.NoteHeight // 2
                + SC.NoteHeight
            )
            _draw_line(cr, xstart, y1, xstart, ystem, 1)

    def _draw_curvy_stem(self, cr, ytop: int, topstaff: WhiteNote) -> None:
        if self.side == Stem.LeftSide:
            xstart = SC.LineSpace // 4 + 1
        else:
            xstart = SC.LineSpace // 4 + SC.NoteWidth

        if self.direction == Stem.Up:
            ystem = ytop + topstaff.dist(self.end) * SC.NoteHeight // 2

            if self.duration in (
                NoteDuration.Eighth,
                NoteDuration.DottedEighth,
                NoteDuration.Triplet,
                NoteDuration.Sixteenth,
                NoteDuration.ThirtySecond,
            ):
                _draw_bezier(
                    cr,
                    xstart, ystem,
                    xstart, ystem + 3 * SC.LineSpace // 2,
                    xstart + SC.LineSpace * 2, ystem + SC.NoteHeight * 2,
                    xstart + SC.LineSpace // 2, ystem + SC.NoteHeight * 3,
                    width=2,
                )
            ystem += SC.NoteHeight

            if self.duration in (
                NoteDuration.Sixteenth,
                NoteDuration.ThirtySecond,
            ):
                _draw_bezier(
                    cr,
                    xstart, ystem,
                    xstart, ystem + 3 * SC.LineSpace // 2,
                    xstart + SC.LineSpace * 2, ystem + SC.NoteHeight * 2,
                    xstart + SC.LineSpace // 2, ystem + SC.NoteHeight * 3,
                    width=2,
                )
            ystem += SC.NoteHeight
            if self.duration == NoteDuration.ThirtySecond:
                _draw_bezier(
                    cr,
                    xstart, ystem,
                    xstart, ystem + 3 * SC.LineSpace // 2,
                    xstart + SC.LineSpace * 2, ystem + SC.NoteHeight * 2,
                    xstart + SC.LineSpace // 2, ystem + SC.NoteHeight * 3,
                    width=2,
                )
        else:
            ystem = (
                ytop
                + topstaff.dist(self.end) * SC.NoteHeight // 2
                + SC.NoteHeight
            )
            if self.duration in (
                NoteDuration.Eighth,
                NoteDuration.DottedEighth,
                NoteDuration.Triplet,
                NoteDuration.Sixteenth,
                NoteDuration.ThirtySecond,
            ):
                _draw_bezier(
                    cr,
                    xstart, ystem,
                    xstart, ystem - SC.LineSpace,
                    xstart + SC.LineSpace * 2, ystem - SC.NoteHeight * 2,
                    xstart + SC.LineSpace, ystem - SC.NoteHeight * 2 - SC.LineSpace // 2,
                    width=2,
                )
            ystem -= SC.NoteHeight

            if self.duration in (
                NoteDuration.Sixteenth,
                NoteDuration.ThirtySecond,
            ):
                _draw_bezier(
                    cr,
                    xstart, ystem,
                    xstart, ystem - SC.LineSpace,
                    xstart + SC.LineSpace * 2, ystem - SC.NoteHeight * 2,
                    xstart + SC.LineSpace, ystem - SC.NoteHeight * 2 - SC.LineSpace // 2,
                    width=2,
                )
            ystem -= SC.NoteHeight
            if self.duration == NoteDuration.ThirtySecond:
                _draw_bezier(
                    cr,
                    xstart, ystem,
                    xstart, ystem - SC.LineSpace,
                    xstart + SC.LineSpace * 2, ystem - SC.NoteHeight * 2,
                    xstart + SC.LineSpace, ystem - SC.NoteHeight * 2 - SC.LineSpace // 2,
                    width=2,
                )

    def _draw_horiz_bar_stem(self, cr, ytop: int, topstaff: WhiteNote) -> None:
        beam_width = max(2, SC.NoteHeight // 2)

        if self.side == Stem.LeftSide:
            xstart = SC.LineSpace // 4 + 1
        else:
            xstart = SC.LineSpace // 4 + SC.NoteWidth

        if self.pair.side == Stem.LeftSide:
            xstart2 = SC.LineSpace // 4 + 1
        else:
            xstart2 = SC.LineSpace // 4 + SC.NoteWidth

        if self.direction == Stem.Up:
            xend = self.width_to_pair + xstart2
            ystart = ytop + topstaff.dist(self.end) * SC.NoteHeight // 2
            yend = ytop + topstaff.dist(self.pair.end) * SC.NoteHeight // 2

            if self.duration in (
                NoteDuration.Eighth,
                NoteDuration.DottedEighth,
                NoteDuration.Triplet,
                NoteDuration.Sixteenth,
                NoteDuration.ThirtySecond,
            ):
                _draw_line(cr, xstart, ystart, xend, yend, beam_width)

            ystart += SC.NoteHeight
            yend += SC.NoteHeight

            if self.duration == NoteDuration.DottedEighth:
                x = xend - SC.NoteHeight
                slope = (yend - ystart) / (xend - xstart) if xend != xstart else 0.0
                y = int(slope * (x - xend) + yend)
                _draw_line(cr, x, y, xend, yend, beam_width)

            if self.duration in (
                NoteDuration.Sixteenth,
                NoteDuration.ThirtySecond,
            ):
                _draw_line(cr, xstart, ystart, xend, yend, beam_width)

            ystart += SC.NoteHeight
            yend += SC.NoteHeight

            if self.duration == NoteDuration.ThirtySecond:
                _draw_line(cr, xstart, ystart, xend, yend, beam_width)
        else:
            xend = self.width_to_pair + xstart2
            ystart = (
                ytop + topstaff.dist(self.end) * SC.NoteHeight // 2 + SC.NoteHeight
            )
            yend = (
                ytop
                + topstaff.dist(self.pair.end) * SC.NoteHeight // 2
                + SC.NoteHeight
            )

            if self.duration in (
                NoteDuration.Eighth,
                NoteDuration.DottedEighth,
                NoteDuration.Triplet,
                NoteDuration.Sixteenth,
                NoteDuration.ThirtySecond,
            ):
                _draw_line(cr, xstart, ystart, xend, yend, beam_width)

            ystart -= SC.NoteHeight
            yend -= SC.NoteHeight

            if self.duration == NoteDuration.DottedEighth:
                x = xend - SC.NoteHeight
                slope = (yend - ystart) / (xend - xstart) if xend != xstart else 0.0
                y = int(slope * (x - xend) + yend)
                _draw_line(cr, x, y, xend, yend, beam_width)

            if self.duration in (
                NoteDuration.Sixteenth,
                NoteDuration.ThirtySecond,
            ):
                _draw_line(cr, xstart, ystart, xend, yend, beam_width)

            ystart -= SC.NoteHeight
            yend -= SC.NoteHeight

            if self.duration == NoteDuration.ThirtySecond:
                _draw_line(cr, xstart, ystart, xend, yend, beam_width)
