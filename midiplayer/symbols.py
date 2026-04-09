"""Music symbol classes.

Ports of MusicSymbol.cs, BlankSymbol.cs, BarSymbol.cs, TimeSigSymbol.cs,
ClefSymbol.cs, AccidSymbol.cs, RestSymbol.cs, and LyricSymbol.cs.

Each symbol is responsible for drawing itself via Cairo. The coordinate
math is identical to the C# source: origin (0, 0) is the top-left of the
staff region, and ``ytop`` is passed in by the caller (Staff.draw) as the
y-pixel of the top staff line.
"""

from __future__ import annotations

import math
import os
from typing import Optional

from . import sheet_constants as SC
from .music_theory import Accid, Clef, NoteDuration, WhiteNote


# ---------------------------------------------------------------------------
# Cairo helpers
# ---------------------------------------------------------------------------

def _set_black(cr) -> None:
    cr.set_source_rgb(0, 0, 0)


def _draw_line(cr, x1, y1, x2, y2, width: int = 1) -> None:
    cr.set_line_width(width)
    cr.set_line_cap(1)  # CAIRO_LINE_CAP_ROUND-ish; round is fine here
    cr.move_to(x1 + 0.5, y1 + 0.5)
    cr.line_to(x2 + 0.5, y2 + 0.5)
    cr.stroke()


def _fill_rect(cr, x, y, w, h) -> None:
    cr.rectangle(x, y, w, h)
    cr.fill()


def _draw_bezier(cr, x1, y1, cx1, cy1, cx2, cy2, x2, y2, width=2) -> None:
    cr.set_line_width(width)
    cr.move_to(x1, y1)
    cr.curve_to(cx1, cy1, cx2, cy2, x2, y2)
    cr.stroke()


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class MusicSymbol:
    """Abstract base for all drawable music symbols."""

    @property
    def StartTime(self) -> int:
        raise NotImplementedError

    @property
    def MinWidth(self) -> int:
        raise NotImplementedError

    @property
    def Width(self) -> int:
        raise NotImplementedError

    @Width.setter
    def Width(self, value: int) -> None:
        raise NotImplementedError

    @property
    def AboveStaff(self) -> int:
        return 0

    @property
    def BelowStaff(self) -> int:
        return 0

    def draw(self, cr, ytop: int) -> None:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# BlankSymbol
# ---------------------------------------------------------------------------

class BlankSymbol(MusicSymbol):
    def __init__(self, starttime: int, width: int):
        self._starttime = starttime
        self._width = width

    @property
    def StartTime(self) -> int:
        return self._starttime

    @property
    def MinWidth(self) -> int:
        return 0

    @property
    def Width(self) -> int:
        return self._width

    @Width.setter
    def Width(self, value: int) -> None:
        self._width = value

    def draw(self, cr, ytop: int) -> None:
        return

    def __repr__(self) -> str:
        return f"BlankSymbol starttime={self._starttime} width={self._width}"


# ---------------------------------------------------------------------------
# BarSymbol
# ---------------------------------------------------------------------------

class BarSymbol(MusicSymbol):
    def __init__(self, starttime: int):
        self._starttime = starttime
        self._width = self.MinWidth

    @property
    def StartTime(self) -> int:
        return self._starttime

    @property
    def MinWidth(self) -> int:
        return 2 * SC.LineSpace

    @property
    def Width(self) -> int:
        return self._width

    @Width.setter
    def Width(self, value: int) -> None:
        self._width = value

    def draw(self, cr, ytop: int) -> None:
        _set_black(cr)
        y = ytop
        yend = y + SC.LineSpace * 4 + SC.LineWidth * 4
        _draw_line(cr, SC.NoteWidth // 2, y, SC.NoteWidth // 2, yend, 1)

    def __repr__(self) -> str:
        return f"BarSymbol starttime={self._starttime} width={self._width}"


# ---------------------------------------------------------------------------
# LyricSymbol (not a MusicSymbol — used by Staff for text below the staff)
# ---------------------------------------------------------------------------

class LyricSymbol:
    def __init__(self, starttime: int, text: str):
        self.StartTime = starttime
        self.Text = text
        self.X = 0

    @property
    def MinWidth(self) -> int:
        return len(self.Text) * 10


# ---------------------------------------------------------------------------
# ClefSymbol
# ---------------------------------------------------------------------------

# Cached Cairo image surfaces for the treble/bass clef PNGs
_treble_surface = None
_bass_surface = None
_timesig_surfaces: dict = {}
_RESOURCE_DIR = os.path.join(os.path.dirname(__file__), "resources")


def _load_image_surface(filename: str):
    """Load a PNG as a Cairo ImageSurface. Returns None if Cairo unavailable."""
    try:
        import cairo  # type: ignore
    except ImportError:
        return None
    path = os.path.join(_RESOURCE_DIR, filename)
    try:
        return cairo.ImageSurface.create_from_png(path)
    except Exception:
        return None


def _get_clef_surfaces():
    global _treble_surface, _bass_surface
    if _treble_surface is None:
        _treble_surface = _load_image_surface("treble.png")
    if _bass_surface is None:
        _bass_surface = _load_image_surface("bass.png")
    return _treble_surface, _bass_surface


def _get_timesig_surface(digit: int):
    if digit in _timesig_surfaces:
        return _timesig_surfaces[digit]
    names = {
        2: "two.png", 3: "three.png", 4: "four.png",
        6: "six.png", 8: "eight.png", 9: "nine.png", 12: "twelve.png",
    }
    if digit not in names:
        return None
    surf = _load_image_surface(names[digit])
    _timesig_surfaces[digit] = surf
    return surf


class ClefSymbol(MusicSymbol):
    """Treble or bass clef image drawn at the left of a staff (or inline)."""

    def __init__(self, clef: Clef, starttime: int, small: bool):
        self.clef = clef
        self._starttime = starttime
        self.smallsize = small
        self._width = self.MinWidth

    @property
    def StartTime(self) -> int:
        return self._starttime

    @property
    def MinWidth(self) -> int:
        if self.smallsize:
            return SC.NoteWidth * 2
        return SC.NoteWidth * 3

    @property
    def Width(self) -> int:
        return self._width

    @Width.setter
    def Width(self, value: int) -> None:
        self._width = value

    @property
    def AboveStaff(self) -> int:
        if self.clef == Clef.Treble and not self.smallsize:
            return SC.NoteHeight * 2
        return 0

    @property
    def BelowStaff(self) -> int:
        if self.clef == Clef.Treble and not self.smallsize:
            return SC.NoteHeight * 2
        if self.clef == Clef.Treble and self.smallsize:
            return SC.NoteHeight
        return 0

    def draw(self, cr, ytop: int) -> None:
        # Right-align inside the allocated width
        dx = self.Width - self.MinWidth
        if dx:
            cr.translate(dx, 0)

        treble, bass = _get_clef_surfaces()

        y = ytop
        if self.clef == Clef.Treble:
            image = treble
            if self.smallsize:
                height = SC.StaffHeight + SC.StaffHeight // 4
            else:
                height = 3 * SC.StaffHeight // 2 + SC.NoteHeight // 2
                y = ytop - SC.NoteHeight
        else:
            image = bass
            if self.smallsize:
                height = SC.StaffHeight - 3 * SC.NoteHeight // 2
            else:
                height = SC.StaffHeight - SC.NoteHeight

        if image is not None:
            imgw = image.get_width()
            imgh = image.get_height()
            scale_y = height / imgh
            scale_x = (imgw * height / imgh) / imgw
            cr.save()
            cr.translate(0, y)
            cr.scale(scale_x, scale_y)
            cr.set_source_surface(image, 0, 0)
            cr.paint()
            cr.restore()

        if dx:
            cr.translate(-dx, 0)

    def __repr__(self) -> str:
        return (
            f"ClefSymbol clef={self.clef.name} small={self.smallsize} "
            f"width={self._width}"
        )


# ---------------------------------------------------------------------------
# TimeSigSymbol
# ---------------------------------------------------------------------------

class TimeSigSymbol(MusicSymbol):
    def __init__(self, numer: int, denom: int):
        self.numerator = numer
        self.denominator = denom
        self._width = self.MinWidth

    @property
    def StartTime(self) -> int:
        return -1

    @property
    def MinWidth(self) -> int:
        surf = _get_timesig_surface(2)
        if surf is None:
            # Fallback: rough width when image unavailable
            return SC.NoteHeight * 2
        return int(surf.get_width() * SC.NoteHeight * 2 / surf.get_height())

    @property
    def Width(self) -> int:
        return self._width

    @Width.setter
    def Width(self, value: int) -> None:
        self._width = value

    def draw(self, cr, ytop: int) -> None:
        numer = _get_timesig_surface(self.numerator)
        denom = _get_timesig_surface(self.denominator)
        if numer is None or denom is None:
            return

        dx = self.Width - self.MinWidth
        if dx:
            cr.translate(dx, 0)

        img_h = SC.NoteHeight * 2
        for surf, y in ((numer, ytop), (denom, ytop + SC.NoteHeight * 2)):
            src_w = surf.get_width()
            src_h = surf.get_height()
            scale_y = img_h / src_h
            scale_x = (src_w * img_h / src_h) / src_w
            cr.save()
            cr.translate(0, y)
            cr.scale(scale_x, scale_y)
            cr.set_source_surface(surf, 0, 0)
            cr.paint()
            cr.restore()

        if dx:
            cr.translate(-dx, 0)

    def __repr__(self) -> str:
        return f"TimeSigSymbol numerator={self.numerator} denominator={self.denominator}"


# ---------------------------------------------------------------------------
# AccidSymbol
# ---------------------------------------------------------------------------

class AccidSymbol(MusicSymbol):
    """A sharp, flat, or natural at a specific (whitenote, clef) position."""

    def __init__(self, accid: Accid, whitenote: WhiteNote, clef: Clef):
        self.accid = accid
        self.whitenote = whitenote
        self.clef = clef
        self._width = self.MinWidth

    @property
    def Note(self) -> WhiteNote:
        return self.whitenote

    @property
    def StartTime(self) -> int:
        return -1

    @property
    def MinWidth(self) -> int:
        return 3 * SC.NoteHeight // 2

    @property
    def Width(self) -> int:
        return self._width

    @Width.setter
    def Width(self, value: int) -> None:
        self._width = value

    @property
    def AboveStaff(self) -> int:
        dist = (
            WhiteNote.top(self.clef).dist(self.whitenote)
            * SC.NoteHeight
            // 2
        )
        if self.accid in (Accid.Sharp, Accid.Natural):
            dist -= SC.NoteHeight
        elif self.accid == Accid.Flat:
            dist -= 3 * SC.NoteHeight // 2
        return -dist if dist < 0 else 0

    @property
    def BelowStaff(self) -> int:
        dist = (
            WhiteNote.bottom(self.clef).dist(self.whitenote)
            * SC.NoteHeight
            // 2
            + SC.NoteHeight
        )
        if self.accid in (Accid.Sharp, Accid.Natural):
            dist += SC.NoteHeight
        return dist if dist > 0 else 0

    def draw(self, cr, ytop: int) -> None:
        dx = self.Width - self.MinWidth
        if dx:
            cr.translate(dx, 0)

        ynote = ytop + WhiteNote.top(self.clef).dist(self.whitenote) * SC.NoteHeight // 2

        _set_black(cr)
        if self.accid == Accid.Sharp:
            self._draw_sharp(cr, ynote)
        elif self.accid == Accid.Flat:
            self._draw_flat(cr, ynote)
        elif self.accid == Accid.Natural:
            self._draw_natural(cr, ynote)

        if dx:
            cr.translate(-dx, 0)

    def _draw_sharp(self, cr, ynote: int) -> None:
        # Two vertical lines
        ystart = ynote - SC.NoteHeight
        yend = ynote + 2 * SC.NoteHeight
        x = SC.NoteHeight // 2
        _draw_line(cr, x, ystart + 2, x, yend, 1)
        x += SC.NoteHeight // 2
        _draw_line(cr, x, ystart, x, yend - 2, 1)

        # Two slightly upward horizontal bars
        xstart = SC.NoteHeight // 2 - SC.NoteHeight // 4
        xend = SC.NoteHeight + SC.NoteHeight // 4
        ystart = ynote + SC.LineWidth
        yend = ystart - SC.LineWidth - SC.LineSpace // 4
        _draw_line(cr, xstart, ystart, xend, yend, max(1, SC.LineSpace // 2))
        ystart += SC.LineSpace
        yend += SC.LineSpace
        _draw_line(cr, xstart, ystart, xend, yend, max(1, SC.LineSpace // 2))

    def _draw_flat(self, cr, ynote: int) -> None:
        x = SC.LineSpace // 4
        # Vertical line
        _draw_line(
            cr,
            x,
            ynote - SC.NoteHeight - SC.NoteHeight // 2,
            x,
            ynote + SC.NoteHeight,
            1,
        )

        # Three bezier curves (curvy belly)
        for widen in range(3):
            cx2 = x + SC.LineSpace + (widen * SC.LineSpace // 4)
            cy2 = ynote + SC.LineSpace // 3 - (widen * SC.LineSpace // 4)
            _draw_bezier(
                cr,
                x, ynote + SC.LineSpace // 4,
                x + SC.LineSpace // 2, ynote - SC.LineSpace // 2,
                cx2, cy2,
                x, ynote + SC.LineSpace + SC.LineWidth + 1,
                width=1,
            )

    def _draw_natural(self, cr, ynote: int) -> None:
        ystart = ynote - SC.LineSpace - SC.LineWidth
        yend = ynote + SC.LineSpace + SC.LineWidth
        x = SC.LineSpace // 2
        _draw_line(cr, x, ystart, x, yend, 1)
        x += SC.LineSpace - SC.LineSpace // 4
        ystart = ynote - SC.LineSpace // 4
        yend = (
            ynote + 2 * SC.LineSpace + SC.LineWidth - SC.LineSpace // 4
        )
        _draw_line(cr, x, ystart, x, yend, 1)

        # Two slight horizontal bars
        xstart = SC.LineSpace // 2
        xend = xstart + SC.LineSpace - SC.LineSpace // 4
        ystart = ynote + SC.LineWidth
        yend = ystart - SC.LineWidth - SC.LineSpace // 4
        _draw_line(cr, xstart, ystart, xend, yend, max(1, SC.LineSpace // 2))
        ystart += SC.LineSpace
        yend += SC.LineSpace
        _draw_line(cr, xstart, ystart, xend, yend, max(1, SC.LineSpace // 2))

    def __repr__(self) -> str:
        return (
            f"AccidSymbol accid={self.accid.name} whitenote={self.whitenote} "
            f"clef={self.clef.name} width={self._width}"
        )


# ---------------------------------------------------------------------------
# RestSymbol
# ---------------------------------------------------------------------------

class RestSymbol(MusicSymbol):
    def __init__(self, start: int, duration: NoteDuration):
        self._starttime = start
        self.duration = duration
        self._width = self.MinWidth

    @property
    def StartTime(self) -> int:
        return self._starttime

    @property
    def MinWidth(self) -> int:
        return 2 * SC.NoteHeight + SC.NoteHeight // 2

    @property
    def Width(self) -> int:
        return self._width

    @Width.setter
    def Width(self, value: int) -> None:
        self._width = value

    def draw(self, cr, ytop: int) -> None:
        dx = self.Width - self.MinWidth
        cr.translate(dx + SC.NoteHeight // 2, 0)

        _set_black(cr)
        if self.duration == NoteDuration.Whole:
            self._draw_whole(cr, ytop)
        elif self.duration == NoteDuration.Half:
            self._draw_half(cr, ytop)
        elif self.duration == NoteDuration.Quarter:
            self._draw_quarter(cr, ytop)
        elif self.duration == NoteDuration.Eighth:
            self._draw_eighth(cr, ytop)

        cr.translate(-(dx + SC.NoteHeight // 2), 0)

    def _draw_whole(self, cr, ytop: int) -> None:
        y = ytop + SC.NoteHeight
        _fill_rect(cr, 0, y, SC.NoteWidth, SC.NoteHeight // 2)

    def _draw_half(self, cr, ytop: int) -> None:
        y = ytop + SC.NoteHeight + SC.NoteHeight // 2
        _fill_rect(cr, 0, y, SC.NoteWidth, SC.NoteHeight // 2)

    def _draw_quarter(self, cr, ytop: int) -> None:
        y = ytop + SC.NoteHeight // 2
        x = 2
        xend = x + 2 * SC.NoteHeight // 3
        _draw_line(cr, x, y, xend - 1, y + SC.NoteHeight - 1, 1)

        y = ytop + SC.NoteHeight + 1
        _draw_line(
            cr, xend - 2, y, x, y + SC.NoteHeight, max(1, SC.LineSpace // 2)
        )

        y = ytop + SC.NoteHeight * 2 - 1
        _draw_line(cr, 0, y, xend + 2, y + SC.NoteHeight, 1)

        if SC.NoteHeight == 6:
            _draw_line(
                cr,
                xend, y + 1 + 3 * SC.NoteHeight // 4,
                x // 2, y + 1 + 3 * SC.NoteHeight // 4,
                max(1, SC.LineSpace // 2),
            )
        else:  # NoteHeight == 8
            _draw_line(
                cr,
                xend, y + 3 * SC.NoteHeight // 4,
                x // 2, y + 3 * SC.NoteHeight // 4,
                max(1, SC.LineSpace // 2),
            )

        _draw_line(
            cr, 0, y + 2 * SC.NoteHeight // 3 + 1,
            xend - 1, y + 3 * SC.NoteHeight // 2, 1,
        )

    def _draw_eighth(self, cr, ytop: int) -> None:
        y = ytop + SC.NoteHeight - 1
        # Filled oval
        cr.save()
        cr.translate(0, y + 1)
        cr.scale(SC.LineSpace - 1, SC.LineSpace - 1)
        cr.arc(0.5, 0.5, 0.5, 0, 2 * math.pi)
        cr.fill()
        cr.restore()
        _draw_line(
            cr,
            (SC.LineSpace - 2) // 2, y + SC.LineSpace - 1,
            3 * SC.LineSpace // 2, y + SC.LineSpace // 2,
            1,
        )
        _draw_line(
            cr,
            3 * SC.LineSpace // 2, y + SC.LineSpace // 2,
            3 * SC.LineSpace // 4, y + SC.NoteHeight * 2,
            1,
        )

    def __repr__(self) -> str:
        return (
            f"RestSymbol starttime={self._starttime} "
            f"duration={self.duration.name} width={self._width}"
        )
