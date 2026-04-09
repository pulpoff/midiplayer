"""Port of ChordSymbol.cs.

A chord symbol is a group of simultaneously-sounding notes. It owns its
accidental sub-symbols and up to two Stems (for chords with mixed
durations). The drawing routine matches the C# source pixel-for-pixel:
rotated ellipses for note heads, ledger lines above/below the staff,
optional dot for dotted durations, and delegated stem drawing.
"""

from __future__ import annotations

import math
from typing import List, Optional

from . import sheet_constants as SC
from .key_signature import KeySignature
from .midi_note import MidiNote
from .music_theory import Accid, Clef, NoteDuration, NoteScale, WhiteNote
from .stem import Stem
from .symbols import (
    AccidSymbol,
    MusicSymbol,
    _draw_line,
    _set_black,
)


class NoteData:
    """Per-note display information inside a chord."""

    __slots__ = ("number", "whitenote", "duration", "leftside", "accid")

    def __init__(self) -> None:
        self.number: int = 0
        self.whitenote: WhiteNote = WhiteNote(WhiteNote.A, 4)
        self.duration: NoteDuration = NoteDuration.Quarter
        self.leftside: bool = True
        self.accid: Accid = Accid.None_


class ChordSymbol(MusicSymbol):
    def __init__(
        self,
        midinotes: List[MidiNote],
        key: KeySignature,
        time,
        clef: Clef,
        sheetmusic=None,
    ):
        self.clef = clef
        self.sheetmusic = sheetmusic
        self.hastwostems = False

        self._starttime = midinotes[0].StartTime
        self._endtime = midinotes[0].EndTime

        # Validate increasing note numbers, find end time
        for i, note in enumerate(midinotes):
            if i > 1 and note.Number < midinotes[i - 1].Number:
                raise ValueError("Chord notes not in increasing order by number")
            if note.EndTime > self._endtime:
                self._endtime = note.EndTime

        self.notedata = ChordSymbol._create_note_data(midinotes, key, time)
        self.accidsymbols = ChordSymbol._create_accid_symbols(self.notedata, clef)

        # Decide how many stems we need
        dur1 = self.notedata[0].duration
        dur2 = dur1
        change = -1
        for i, nd in enumerate(self.notedata):
            dur2 = nd.duration
            if dur1 != dur2:
                change = i
                break

        if dur1 != dur2:
            self.hastwostems = True
            self.stem1 = Stem(
                self.notedata[0].whitenote,
                self.notedata[change - 1].whitenote,
                dur1,
                Stem.Down,
                ChordSymbol._notes_overlap(self.notedata, 0, change),
            )
            self.stem2 = Stem(
                self.notedata[change].whitenote,
                self.notedata[-1].whitenote,
                dur2,
                Stem.Up,
                ChordSymbol._notes_overlap(
                    self.notedata, change, len(self.notedata)
                ),
            )
        else:
            direction = ChordSymbol._stem_direction(
                self.notedata[0].whitenote,
                self.notedata[-1].whitenote,
                clef,
            )
            self.stem1 = Stem(
                self.notedata[0].whitenote,
                self.notedata[-1].whitenote,
                dur1,
                direction,
                ChordSymbol._notes_overlap(self.notedata, 0, len(self.notedata)),
            )
            self.stem2 = None

        # Whole notes have no stem
        if dur1 == NoteDuration.Whole:
            self.stem1 = None
        if dur2 == NoteDuration.Whole:
            self.stem2 = None

        self._width = self.MinWidth

    # C# property aliases ---------------------------------------------------

    @property
    def StartTime(self) -> int:
        return self._starttime

    @property
    def EndTime(self) -> int:
        return self._endtime

    @property
    def Clef(self) -> Clef:
        return self.clef

    @property
    def HasTwoStems(self) -> bool:
        return self.hastwostems

    @property
    def Stem(self) -> Optional[Stem]:
        if self.stem1 is None:
            return self.stem2
        if self.stem2 is None:
            return self.stem1
        if self.stem1.Duration < self.stem2.Duration:
            return self.stem1
        return self.stem2

    @property
    def Width(self) -> int:
        return self._width

    @Width.setter
    def Width(self, value: int) -> None:
        self._width = value

    @property
    def MinWidth(self) -> int:
        result = 2 * SC.NoteHeight + SC.NoteHeight * 3 // 4
        if self.accidsymbols:
            result += self.accidsymbols[0].MinWidth
            for i in range(1, len(self.accidsymbols)):
                accid = self.accidsymbols[i]
                prev = self.accidsymbols[i - 1]
                if accid.Note.dist(prev.Note) < 6:
                    result += accid.MinWidth
        from .midi_options import MidiOptions  # avoid import cycle at top
        if (
            self.sheetmusic is not None
            and getattr(self.sheetmusic, "showNoteLetters", MidiOptions.NoteNameNone)
            != MidiOptions.NoteNameNone
        ):
            result += 8
        return result

    @property
    def AboveStaff(self) -> int:
        topnote = self.notedata[-1].whitenote
        if self.stem1 is not None:
            topnote = WhiteNote.max(topnote, self.stem1.End)
        if self.stem2 is not None:
            topnote = WhiteNote.max(topnote, self.stem2.End)

        dist = topnote.dist(WhiteNote.top(self.clef)) * SC.NoteHeight // 2
        result = dist if dist > 0 else 0
        for symbol in self.accidsymbols:
            if symbol.AboveStaff > result:
                result = symbol.AboveStaff
        return result

    @property
    def BelowStaff(self) -> int:
        bottomnote = self.notedata[0].whitenote
        if self.stem1 is not None:
            bottomnote = WhiteNote.min(bottomnote, self.stem1.End)
        if self.stem2 is not None:
            bottomnote = WhiteNote.min(bottomnote, self.stem2.End)

        dist = WhiteNote.bottom(self.clef).dist(bottomnote) * SC.NoteHeight // 2
        result = dist if dist > 0 else 0
        for symbol in self.accidsymbols:
            if symbol.BelowStaff > result:
                result = symbol.BelowStaff
        return result

    # ----------------------------------------------------------------------
    # Construction helpers
    # ----------------------------------------------------------------------

    @staticmethod
    def _create_note_data(
        midinotes: List[MidiNote], key: KeySignature, time
    ) -> List[NoteData]:
        result = []
        for i, midi in enumerate(midinotes):
            nd = NoteData()
            nd.number = midi.Number
            nd.leftside = True
            nd.whitenote = key.get_white_note(midi.Number)
            nd.duration = time.get_note_duration(midi.EndTime - midi.StartTime)
            nd.accid = key.get_accidental(midi.Number, midi.StartTime // time.Measure)

            if i > 0 and nd.whitenote.dist(result[i - 1].whitenote) == 1:
                # Overlapping with previous; flip side
                nd.leftside = not result[i - 1].leftside
            else:
                nd.leftside = True
            result.append(nd)
        return result

    @staticmethod
    def _create_accid_symbols(
        notedata: List[NoteData], clef: Clef
    ) -> List[AccidSymbol]:
        return [
            AccidSymbol(n.accid, n.whitenote, clef)
            for n in notedata
            if n.accid != Accid.None_
        ]

    @staticmethod
    def _stem_direction(bottom: WhiteNote, top: WhiteNote, clef: Clef) -> int:
        if clef == Clef.Treble:
            middle = WhiteNote(WhiteNote.B, 5)
        else:
            middle = WhiteNote(WhiteNote.D, 3)
        dist = middle.dist(bottom) + middle.dist(top)
        return Stem.Up if dist >= 0 else Stem.Down

    @staticmethod
    def _notes_overlap(notedata: List[NoteData], start: int, end: int) -> bool:
        for i in range(start, end):
            if not notedata[i].leftside:
                return True
        return False

    # ----------------------------------------------------------------------
    # Drawing
    # ----------------------------------------------------------------------

    def draw(self, cr, ytop: int) -> None:
        dx = self.Width - self.MinWidth
        if dx:
            cr.translate(dx, 0)

        topstaff = WhiteNote.top(self.clef)
        xpos = self._draw_accidentals(cr, ytop)

        cr.translate(xpos, 0)
        self._draw_notes(cr, ytop, topstaff)
        cr.translate(-xpos, 0)

        if self.stem1 is not None:
            self.stem1.draw(cr, ytop, topstaff)
        if self.stem2 is not None:
            self.stem2.draw(cr, ytop, topstaff)

        if dx:
            cr.translate(-dx, 0)

    def _draw_accidentals(self, cr, ytop: int) -> int:
        xpos = 0
        prev: Optional[AccidSymbol] = None
        for symbol in self.accidsymbols:
            if prev is not None and symbol.Note.dist(prev.Note) < 6:
                xpos += symbol.Width
            cr.translate(xpos, 0)
            symbol.draw(cr, ytop)
            cr.translate(-xpos, 0)
            prev = symbol
        if prev is not None:
            xpos += prev.Width
        return xpos

    def _draw_notes(self, cr, ytop: int, topstaff: WhiteNote) -> None:
        _set_black(cr)
        for note in self.notedata:
            ynote = ytop + topstaff.dist(note.whitenote) * SC.NoteHeight // 2
            xnote = SC.LineSpace // 4
            if not note.leftside:
                xnote += SC.NoteWidth

            # Draw a rotated ellipse for the note head.
            cx = xnote + SC.NoteWidth / 2 + 1
            cy = ynote - SC.LineWidth + SC.NoteHeight / 2

            hollow = note.duration in (
                NoteDuration.Whole,
                NoteDuration.Half,
                NoteDuration.DottedHalf,
            )

            cr.save()
            cr.translate(cx, cy)
            cr.rotate(-math.pi / 4)

            # Scale a unit circle into the note-head ellipse shape
            rx = SC.NoteWidth / 2
            ry = (SC.NoteHeight - 1) / 2
            cr.save()
            cr.scale(rx, ry)
            cr.arc(0, 0, 1, 0, 2 * math.pi)
            cr.restore()
            if hollow:
                cr.set_line_width(1.2)
                cr.stroke()
            else:
                cr.fill()

            # Outline (always drawn in black)
            cr.save()
            cr.scale(rx, ry)
            cr.arc(0, 0, 1, 0, 2 * math.pi)
            cr.restore()
            cr.set_source_rgb(0, 0, 0)
            cr.set_line_width(1)
            cr.stroke()

            cr.restore()

            # Dotted duration -> draw a small filled circle to the right
            if note.duration in (
                NoteDuration.DottedHalf,
                NoteDuration.DottedQuarter,
                NoteDuration.DottedEighth,
            ):
                dot_x = xnote + SC.NoteWidth + SC.LineSpace // 3
                dot_y = ynote + SC.LineSpace // 3
                cr.arc(dot_x + 2, dot_y + 2, 2, 0, 2 * math.pi)
                cr.fill()

            # Ledger lines above the staff
            top_plus1 = topstaff.add(1)
            dist = note.whitenote.dist(top_plus1)
            y = ytop - SC.LineWidth
            if dist >= 2:
                i = 2
                while i <= dist:
                    y -= SC.NoteHeight
                    _draw_line(
                        cr,
                        xnote - SC.LineSpace // 4, y,
                        xnote + SC.NoteWidth + SC.LineSpace // 4, y,
                        1,
                    )
                    i += 2

            # Ledger lines below the staff
            bottom = top_plus1.add(-8)
            y = ytop + (SC.LineSpace + SC.LineWidth) * 4 - 1
            dist = bottom.dist(note.whitenote)
            if dist >= 2:
                i = 2
                while i <= dist:
                    y += SC.NoteHeight
                    _draw_line(
                        cr,
                        xnote - SC.LineSpace // 4, y,
                        xnote + SC.NoteWidth + SC.LineSpace // 4, y,
                        1,
                    )
                    i += 2

    # ----------------------------------------------------------------------
    # Beam creation
    # ----------------------------------------------------------------------

    @staticmethod
    def can_create_beam(chords: List["ChordSymbol"], time, start_quarter: bool) -> bool:
        if not chords:
            return False
        first_stem = chords[0].Stem
        last_stem = chords[-1].Stem
        if first_stem is None or last_stem is None:
            return False
        num_chords = len(chords)
        measure = chords[0].StartTime // time.Measure
        dur = first_stem.Duration
        dur2 = last_stem.Duration

        dotted8_to_16 = False
        if (
            num_chords == 2
            and dur == NoteDuration.DottedEighth
            and dur2 == NoteDuration.Sixteenth
        ):
            dotted8_to_16 = True

        if dur in (
            NoteDuration.Whole,
            NoteDuration.Half,
            NoteDuration.DottedHalf,
            NoteDuration.Quarter,
            NoteDuration.DottedQuarter,
        ) or (dur == NoteDuration.DottedEighth and not dotted8_to_16):
            return False

        if num_chords == 6:
            if dur != NoteDuration.Eighth:
                return False
            correct_time = (
                (time.Numerator == 3 and time.Denominator == 4)
                or (time.Numerator == 6 and time.Denominator == 8)
                or (time.Numerator == 6 and time.Denominator == 4)
            )
            if not correct_time:
                return False
            if time.Numerator == 6 and time.Denominator == 4:
                beat = time.Quarter * 3
                if (chords[0].StartTime % beat) > time.Quarter // 6:
                    return False
        elif num_chords == 4:
            if time.Numerator == 3 and time.Denominator == 8:
                return False
            correct_time = time.Numerator in (2, 4, 8)
            if not correct_time and dur != NoteDuration.Sixteenth:
                return False
            beat = time.Quarter
            if dur == NoteDuration.Eighth:
                beat = time.Quarter * 2
            elif dur == NoteDuration.ThirtySecond:
                beat = time.Quarter // 2
            if (chords[0].StartTime % beat) > time.Quarter // 6:
                return False
        elif num_chords == 3:
            valid = dur == NoteDuration.Triplet or (
                dur == NoteDuration.Eighth
                and time.Numerator == 12
                and time.Denominator == 8
            )
            if not valid:
                return False
            beat = time.Quarter
            if time.Numerator == 12 and time.Denominator == 8:
                beat = (time.Quarter // 2) * 3
            if (chords[0].StartTime % beat) > time.Quarter // 6:
                return False
        elif num_chords == 2:
            if start_quarter:
                beat = time.Quarter
                if (chords[0].StartTime % beat) > time.Quarter // 6:
                    return False

        for chord in chords:
            if (chord.StartTime // time.Measure) != measure:
                return False
            if chord.Stem is None:
                return False
            if chord.Stem.Duration != dur and not dotted8_to_16:
                return False
            if chord.Stem.isBeam:
                return False

        has_two_stems = False
        direction = Stem.Up
        for chord in chords:
            if chord.HasTwoStems:
                if has_two_stems and chord.Stem.Direction != direction:
                    return False
                has_two_stems = True
                direction = chord.Stem.Direction

        if not has_two_stems:
            note1 = (
                first_stem.Top if first_stem.Direction == Stem.Up else first_stem.Bottom
            )
            note2 = (
                last_stem.Top if last_stem.Direction == Stem.Up else last_stem.Bottom
            )
            direction = ChordSymbol._stem_direction(note1, note2, chords[0].Clef)

        if direction == Stem.Up:
            if abs(first_stem.Top.dist(last_stem.Top)) >= 11:
                return False
        else:
            if abs(first_stem.Bottom.dist(last_stem.Bottom)) >= 11:
                return False
        return True

    @staticmethod
    def create_beam(chords: List["ChordSymbol"], spacing: int) -> None:
        first_stem = chords[0].Stem
        last_stem = chords[-1].Stem

        new_direction = -1
        for chord in chords:
            if chord.HasTwoStems:
                new_direction = chord.Stem.Direction
                break
        if new_direction == -1:
            note1 = (
                first_stem.Top if first_stem.Direction == Stem.Up else first_stem.Bottom
            )
            note2 = (
                last_stem.Top if last_stem.Direction == Stem.Up else last_stem.Bottom
            )
            new_direction = ChordSymbol._stem_direction(note1, note2, chords[0].Clef)

        for chord in chords:
            chord.Stem.Direction = new_direction

        if len(chords) == 2:
            ChordSymbol._bring_stems_closer(chords)
        else:
            ChordSymbol._line_up_stem_ends(chords)

        first_stem.set_pair(last_stem, spacing)
        for chord in chords[1:]:
            chord.Stem.Receiver = True

    @staticmethod
    def _bring_stems_closer(chords: List["ChordSymbol"]) -> None:
        first_stem = chords[0].Stem
        last_stem = chords[1].Stem

        if (
            first_stem.Duration == NoteDuration.DottedEighth
            and last_stem.Duration == NoteDuration.Sixteenth
        ):
            if first_stem.Direction == Stem.Up:
                first_stem.End = first_stem.End.add(2)
            else:
                first_stem.End = first_stem.End.add(-2)

        distance = abs(first_stem.End.dist(last_stem.End))
        if first_stem.Direction == Stem.Up:
            if WhiteNote.max(first_stem.End, last_stem.End) == first_stem.End:
                last_stem.End = last_stem.End.add(distance // 2)
            else:
                first_stem.End = first_stem.End.add(distance // 2)
        else:
            if WhiteNote.min(first_stem.End, last_stem.End) == first_stem.End:
                last_stem.End = last_stem.End.add(-distance // 2)
            else:
                first_stem.End = first_stem.End.add(-distance // 2)

    @staticmethod
    def _line_up_stem_ends(chords: List["ChordSymbol"]) -> None:
        first_stem = chords[0].Stem
        last_stem = chords[-1].Stem
        middle_stem = chords[1].Stem

        if first_stem.Direction == Stem.Up:
            top = first_stem.End
            for chord in chords:
                top = WhiteNote.max(top, chord.Stem.End)
            if top == first_stem.End and top.dist(last_stem.End) >= 2:
                first_stem.End = top
                middle_stem.End = top.add(-1)
                last_stem.End = top.add(-2)
            elif top == last_stem.End and top.dist(first_stem.End) >= 2:
                first_stem.End = top.add(-2)
                middle_stem.End = top.add(-1)
                last_stem.End = top
            else:
                first_stem.End = top
                middle_stem.End = top
                last_stem.End = top
        else:
            bottom = first_stem.End
            for chord in chords:
                bottom = WhiteNote.min(bottom, chord.Stem.End)
            if bottom == first_stem.End and last_stem.End.dist(bottom) >= 2:
                middle_stem.End = bottom.add(1)
                last_stem.End = bottom.add(2)
            elif bottom == last_stem.End and first_stem.End.dist(bottom) >= 2:
                middle_stem.End = bottom.add(1)
                first_stem.End = bottom.add(2)
            else:
                first_stem.End = bottom
                middle_stem.End = bottom
                last_stem.End = bottom

        for i in range(1, len(chords) - 1):
            chords[i].Stem.End = middle_stem.End
