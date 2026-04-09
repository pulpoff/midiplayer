"""Core music-theory data types.

Direct port of NoteScale, WhiteNote, Accid, Clef and NoteDuration/TimeSignature
from the original MidiSheetMusic C# source.
"""

from __future__ import annotations

from enum import IntEnum


# ---------------------------------------------------------------------------
# NoteScale — a MIDI note number modulo-12 into the chromatic scale.
# ---------------------------------------------------------------------------

class NoteScale:
    A = 0
    Asharp = 1
    Bflat = 1
    B = 2
    C = 3
    Csharp = 4
    Dflat = 4
    D = 5
    Dsharp = 6
    Eflat = 6
    E = 7
    F = 8
    Fsharp = 9
    Gflat = 9
    G = 10
    Gsharp = 11
    Aflat = 11

    @staticmethod
    def to_number(notescale: int, octave: int) -> int:
        return 9 + notescale + octave * 12

    @staticmethod
    def from_number(number: int) -> int:
        return (number + 3) % 12

    @staticmethod
    def is_black_key(notescale: int) -> bool:
        return notescale in (
            NoteScale.Asharp,
            NoteScale.Csharp,
            NoteScale.Dsharp,
            NoteScale.Fsharp,
            NoteScale.Gsharp,
        )


# ---------------------------------------------------------------------------
# Clef / Accid enums
# ---------------------------------------------------------------------------

class Clef(IntEnum):
    Treble = 0
    Bass = 1


class Accid(IntEnum):
    None_ = 0
    Sharp = 1
    Flat = 2
    Natural = 3


# Allow 'Accid.None' style usage from tests / tools.
Accid.NoAccid = Accid.None_  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# WhiteNote — a white-key position (letter + octave).
# ---------------------------------------------------------------------------

class WhiteNote:
    """A non-sharp, non-flat note identified by letter (A-G) and octave."""

    A = 0
    B = 1
    C = 2
    D = 3
    E = 4
    F = 5
    G = 6

    __slots__ = ("letter", "octave")

    def __init__(self, letter: int, octave: int):
        if not (0 <= letter <= 6):
            raise ValueError(f"Letter {letter} is incorrect")
        self.letter = letter
        self.octave = octave

    def dist(self, other: "WhiteNote") -> int:
        """Return (self - other) distance in white notes."""
        return (self.octave - other.octave) * 7 + (self.letter - other.letter)

    def add(self, amount: int) -> "WhiteNote":
        num = self.octave * 7 + self.letter + amount
        if num < 0:
            num = 0
        return WhiteNote(num % 7, num // 7)

    def number(self) -> int:
        offsets = {
            WhiteNote.A: NoteScale.A,
            WhiteNote.B: NoteScale.B,
            WhiteNote.C: NoteScale.C,
            WhiteNote.D: NoteScale.D,
            WhiteNote.E: NoteScale.E,
            WhiteNote.F: NoteScale.F,
            WhiteNote.G: NoteScale.G,
        }
        return NoteScale.to_number(offsets[self.letter], self.octave)

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, WhiteNote)
            and self.letter == other.letter
            and self.octave == other.octave
        )

    def __hash__(self) -> int:
        return hash((self.letter, self.octave))

    def __lt__(self, other: "WhiteNote") -> bool:
        return self.dist(other) < 0

    def __repr__(self) -> str:
        names = "ABCDEFG"
        return f"{names[self.letter]}{self.octave}"

    @staticmethod
    def max(x: "WhiteNote", y: "WhiteNote") -> "WhiteNote":
        return x if x.dist(y) > 0 else y

    @staticmethod
    def min(x: "WhiteNote", y: "WhiteNote") -> "WhiteNote":
        return x if x.dist(y) < 0 else y

    @staticmethod
    def top(clef: Clef) -> "WhiteNote":
        return WhiteNote.TOP_TREBLE if clef == Clef.Treble else WhiteNote.TOP_BASS

    @staticmethod
    def bottom(clef: Clef) -> "WhiteNote":
        return WhiteNote.BOTTOM_TREBLE if clef == Clef.Treble else WhiteNote.BOTTOM_BASS


# Common white notes used in layout calculations.
WhiteNote.TOP_TREBLE = WhiteNote(WhiteNote.E, 5)
WhiteNote.BOTTOM_TREBLE = WhiteNote(WhiteNote.F, 4)
WhiteNote.TOP_BASS = WhiteNote(WhiteNote.G, 3)
WhiteNote.BOTTOM_BASS = WhiteNote(WhiteNote.A, 3)
WhiteNote.MIDDLE_C = WhiteNote(WhiteNote.C, 4)


# ---------------------------------------------------------------------------
# NoteDuration + TimeSignature
# ---------------------------------------------------------------------------

class NoteDuration(IntEnum):
    ThirtySecond = 0
    Sixteenth = 1
    Triplet = 2
    Eighth = 3
    DottedEighth = 4
    Quarter = 5
    DottedQuarter = 6
    Half = 7
    DottedHalf = 8
    Whole = 9


class TimeSignature:
    """Time signature + pulse/tempo metadata."""

    def __init__(self, numerator: int, denominator: int, quarternote: int, tempo: int):
        if numerator <= 0 or denominator <= 0 or quarternote <= 0:
            raise ValueError("Invalid time signature")

        # MIDI files sometimes contain a wrong numerator=5
        if numerator == 5:
            numerator = 4

        self.numerator = numerator
        self.denominator = denominator
        self.quarternote = quarternote
        self.tempo = tempo

        if denominator < 4:
            beat = quarternote * 2
        else:
            beat = quarternote // (denominator // 4)
        self.measure = numerator * beat

    # Accessors matching the C# property names
    @property
    def Numerator(self) -> int:
        return self.numerator

    @property
    def Denominator(self) -> int:
        return self.denominator

    @property
    def Quarter(self) -> int:
        return self.quarternote

    @property
    def Measure(self) -> int:
        return self.measure

    @property
    def Tempo(self) -> int:
        return self.tempo

    def get_measure(self, time: int) -> int:
        return time // self.measure

    def get_note_duration(self, duration: int) -> NoteDuration:
        whole = self.quarternote * 4
        if duration >= 28 * whole // 32:
            return NoteDuration.Whole
        if duration >= 20 * whole // 32:
            return NoteDuration.DottedHalf
        if duration >= 14 * whole // 32:
            return NoteDuration.Half
        if duration >= 10 * whole // 32:
            return NoteDuration.DottedQuarter
        if duration >= 7 * whole // 32:
            return NoteDuration.Quarter
        if duration >= 5 * whole // 32:
            return NoteDuration.DottedEighth
        if duration >= 6 * whole // 64:
            return NoteDuration.Eighth
        if duration >= 5 * whole // 64:
            return NoteDuration.Triplet
        if duration >= 3 * whole // 64:
            return NoteDuration.Sixteenth
        return NoteDuration.ThirtySecond

    @staticmethod
    def get_stem_duration(dur: NoteDuration) -> NoteDuration:
        if dur == NoteDuration.DottedHalf:
            return NoteDuration.Half
        if dur == NoteDuration.DottedQuarter:
            return NoteDuration.Quarter
        if dur == NoteDuration.DottedEighth:
            return NoteDuration.Eighth
        return dur

    def duration_to_time(self, dur: NoteDuration) -> int:
        eighth = self.quarternote // 2
        sixteenth = eighth // 2
        table = {
            NoteDuration.Whole: self.quarternote * 4,
            NoteDuration.DottedHalf: self.quarternote * 3,
            NoteDuration.Half: self.quarternote * 2,
            NoteDuration.DottedQuarter: 3 * eighth,
            NoteDuration.Quarter: self.quarternote,
            NoteDuration.DottedEighth: 3 * sixteenth,
            NoteDuration.Eighth: eighth,
            NoteDuration.Triplet: self.quarternote // 3,
            NoteDuration.Sixteenth: sixteenth,
            NoteDuration.ThirtySecond: sixteenth // 2,
        }
        return table.get(dur, 0)

    def __repr__(self) -> str:
        return (
            f"TimeSignature={self.numerator}/{self.denominator} "
            f"quarter={self.quarternote} tempo={self.tempo}"
        )
