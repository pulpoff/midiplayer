"""Port of KeySignature.cs.

Major key signature with accidental-map lookups, sharps/flats display symbols
and a heuristic for guessing the key from a set of notes.
"""

from __future__ import annotations

from typing import List, Optional

from .music_theory import Accid, Clef, NoteScale, WhiteNote


class KeySignature:
    """A major key signature (number of sharps or flats)."""

    # The sharp-key indices (equal to number of sharps)
    C = 0
    G = 1
    D = 2
    A = 3
    E = 4
    B = 5

    # The flat-key indices (equal to number of flats)
    F = 1
    Bflat = 2
    Eflat = 3
    Aflat = 4
    Dflat = 5
    Gflat = 6

    _sharp_keys: Optional[List[List[Accid]]] = None
    _flat_keys: Optional[List[List[Accid]]] = None

    def __init__(self, num_sharps: int, num_flats: int = 0):
        """Create a KeySignature. Either num_sharps OR num_flats must be 0.

        A single int argument is also supported and interpreted as a NoteScale.
        """
        if num_sharps != 0 and num_flats != 0:
            raise ValueError("Bad KeySignature args")
        self.num_sharps = num_sharps
        self.num_flats = num_flats

        KeySignature._create_accidental_maps()
        self._keymap: List[Accid] = [Accid.None_] * 160
        self._reset_keymap()
        self._create_symbols()
        self._prev_measure = 0

    @classmethod
    def from_notescale(cls, notescale: int) -> "KeySignature":
        mapping = {
            NoteScale.A: (3, 0),
            NoteScale.Bflat: (0, 2),
            NoteScale.B: (5, 0),
            NoteScale.C: (0, 0),
            NoteScale.Dflat: (0, 5),
            NoteScale.D: (2, 0),
            NoteScale.Eflat: (0, 3),
            NoteScale.E: (4, 0),
            NoteScale.F: (0, 1),
            NoteScale.Gflat: (0, 6),
            NoteScale.G: (1, 0),
            NoteScale.Aflat: (0, 4),
        }
        sharps, flats = mapping.get(notescale, (0, 0))
        return cls(sharps, flats)

    # ------------------------------------------------------------------
    # Static key maps
    # ------------------------------------------------------------------
    @classmethod
    def _create_accidental_maps(cls) -> None:
        if cls._sharp_keys is not None:
            return

        sharp_keys: List[List[Accid]] = [[Accid.None_] * 12 for _ in range(8)]
        flat_keys: List[List[Accid]] = [[Accid.None_] * 12 for _ in range(8)]

        # C major (0 sharps)
        m = sharp_keys[cls.C]
        m[NoteScale.Asharp] = Accid.Flat
        m[NoteScale.Csharp] = Accid.Sharp
        m[NoteScale.Dsharp] = Accid.Sharp
        m[NoteScale.Fsharp] = Accid.Sharp
        m[NoteScale.Gsharp] = Accid.Sharp

        # G major (1 sharp)
        m = sharp_keys[cls.G]
        m[NoteScale.Asharp] = Accid.Flat
        m[NoteScale.Csharp] = Accid.Sharp
        m[NoteScale.Dsharp] = Accid.Sharp
        m[NoteScale.F] = Accid.Natural
        m[NoteScale.Gsharp] = Accid.Sharp

        # D major (2 sharps)
        m = sharp_keys[cls.D]
        m[NoteScale.Asharp] = Accid.Flat
        m[NoteScale.C] = Accid.Natural
        m[NoteScale.Dsharp] = Accid.Sharp
        m[NoteScale.F] = Accid.Natural
        m[NoteScale.Gsharp] = Accid.Sharp

        # A major (3 sharps)
        m = sharp_keys[cls.A]
        m[NoteScale.Asharp] = Accid.Flat
        m[NoteScale.C] = Accid.Natural
        m[NoteScale.Dsharp] = Accid.Sharp
        m[NoteScale.F] = Accid.Natural
        m[NoteScale.G] = Accid.Natural

        # E major (4 sharps)
        m = sharp_keys[cls.E]
        m[NoteScale.Asharp] = Accid.Flat
        m[NoteScale.C] = Accid.Natural
        m[NoteScale.D] = Accid.Natural
        m[NoteScale.F] = Accid.Natural
        m[NoteScale.G] = Accid.Natural

        # B major (5 sharps)
        m = sharp_keys[cls.B]
        m[NoteScale.A] = Accid.Natural
        m[NoteScale.C] = Accid.Natural
        m[NoteScale.D] = Accid.Natural
        m[NoteScale.F] = Accid.Natural
        m[NoteScale.G] = Accid.Natural

        # Flat keys
        m = flat_keys[cls.C]
        m[NoteScale.Asharp] = Accid.Flat
        m[NoteScale.Csharp] = Accid.Sharp
        m[NoteScale.Dsharp] = Accid.Sharp
        m[NoteScale.Fsharp] = Accid.Sharp
        m[NoteScale.Gsharp] = Accid.Sharp

        # F major (1 flat)
        m = flat_keys[cls.F]
        m[NoteScale.B] = Accid.Natural
        m[NoteScale.Csharp] = Accid.Sharp
        m[NoteScale.Eflat] = Accid.Flat
        m[NoteScale.Fsharp] = Accid.Sharp
        m[NoteScale.Aflat] = Accid.Flat

        # Bb major (2 flats)
        m = flat_keys[cls.Bflat]
        m[NoteScale.B] = Accid.Natural
        m[NoteScale.Csharp] = Accid.Sharp
        m[NoteScale.E] = Accid.Natural
        m[NoteScale.Fsharp] = Accid.Sharp
        m[NoteScale.Aflat] = Accid.Flat

        # Eb major (3 flats)
        m = flat_keys[cls.Eflat]
        m[NoteScale.A] = Accid.Natural
        m[NoteScale.B] = Accid.Natural
        m[NoteScale.Dflat] = Accid.Flat
        m[NoteScale.E] = Accid.Natural
        m[NoteScale.Fsharp] = Accid.Sharp

        # Ab major (4 flats)
        m = flat_keys[cls.Aflat]
        m[NoteScale.A] = Accid.Natural
        m[NoteScale.B] = Accid.Natural
        m[NoteScale.D] = Accid.Natural
        m[NoteScale.E] = Accid.Natural
        m[NoteScale.Fsharp] = Accid.Sharp

        # Db major (5 flats)
        m = flat_keys[cls.Dflat]
        m[NoteScale.A] = Accid.Natural
        m[NoteScale.B] = Accid.Natural
        m[NoteScale.D] = Accid.Natural
        m[NoteScale.E] = Accid.Natural
        m[NoteScale.G] = Accid.Natural

        # Gb major (6 flats)
        m = flat_keys[cls.Gflat]
        m[NoteScale.A] = Accid.Natural
        m[NoteScale.C] = Accid.Natural
        m[NoteScale.D] = Accid.Natural
        m[NoteScale.E] = Accid.Natural
        m[NoteScale.G] = Accid.Natural

        cls._sharp_keys = sharp_keys
        cls._flat_keys = flat_keys

    def _reset_keymap(self) -> None:
        if self.num_flats > 0:
            key = KeySignature._flat_keys[self.num_flats]
        else:
            key = KeySignature._sharp_keys[self.num_sharps]
        for notenumber in range(len(self._keymap)):
            self._keymap[notenumber] = key[NoteScale.from_number(notenumber)]

    def _create_symbols(self) -> None:
        # Avoid circular import by using a delayed import
        from .symbols import AccidSymbol  # noqa: WPS433

        count = max(self.num_sharps, self.num_flats)
        self._treble_symbols: List[AccidSymbol] = []
        self._bass_symbols: List[AccidSymbol] = []
        if count == 0:
            return

        if self.num_sharps > 0:
            treblenotes = [
                WhiteNote(WhiteNote.F, 5),
                WhiteNote(WhiteNote.C, 5),
                WhiteNote(WhiteNote.G, 5),
                WhiteNote(WhiteNote.D, 5),
                WhiteNote(WhiteNote.A, 6),
                WhiteNote(WhiteNote.E, 5),
            ]
            bassnotes = [
                WhiteNote(WhiteNote.F, 3),
                WhiteNote(WhiteNote.C, 3),
                WhiteNote(WhiteNote.G, 3),
                WhiteNote(WhiteNote.D, 3),
                WhiteNote(WhiteNote.A, 4),
                WhiteNote(WhiteNote.E, 3),
            ]
            accid = Accid.Sharp
        else:
            treblenotes = [
                WhiteNote(WhiteNote.B, 5),
                WhiteNote(WhiteNote.E, 5),
                WhiteNote(WhiteNote.A, 5),
                WhiteNote(WhiteNote.D, 5),
                WhiteNote(WhiteNote.G, 4),
                WhiteNote(WhiteNote.C, 5),
            ]
            bassnotes = [
                WhiteNote(WhiteNote.B, 3),
                WhiteNote(WhiteNote.E, 3),
                WhiteNote(WhiteNote.A, 3),
                WhiteNote(WhiteNote.D, 3),
                WhiteNote(WhiteNote.G, 2),
                WhiteNote(WhiteNote.C, 3),
            ]
            accid = Accid.Flat

        for i in range(count):
            self._treble_symbols.append(AccidSymbol(accid, treblenotes[i], Clef.Treble))
            self._bass_symbols.append(AccidSymbol(accid, bassnotes[i], Clef.Bass))

    def get_symbols(self, clef: Clef) -> list:
        return self._treble_symbols if clef == Clef.Treble else self._bass_symbols

    def get_accidental(self, notenumber: int, measure: int) -> Accid:
        if measure != self._prev_measure:
            self._reset_keymap()
            self._prev_measure = measure

        result = self._keymap[notenumber]
        if result == Accid.Sharp:
            self._keymap[notenumber] = Accid.None_
            self._keymap[notenumber - 1] = Accid.Natural
        elif result == Accid.Flat:
            self._keymap[notenumber] = Accid.None_
            self._keymap[notenumber + 1] = Accid.Natural
        elif result == Accid.Natural:
            self._keymap[notenumber] = Accid.None_
            nextkey = NoteScale.from_number(notenumber + 1)
            prevkey = NoteScale.from_number(notenumber - 1)
            if (
                self._keymap[notenumber - 1] == Accid.None_
                and self._keymap[notenumber + 1] == Accid.None_
                and NoteScale.is_black_key(nextkey)
                and NoteScale.is_black_key(prevkey)
            ):
                if self.num_flats == 0:
                    self._keymap[notenumber + 1] = Accid.Sharp
                else:
                    self._keymap[notenumber - 1] = Accid.Flat
            elif (
                self._keymap[notenumber - 1] == Accid.None_
                and NoteScale.is_black_key(prevkey)
            ):
                self._keymap[notenumber - 1] = Accid.Flat
            elif (
                self._keymap[notenumber + 1] == Accid.None_
                and NoteScale.is_black_key(nextkey)
            ):
                self._keymap[notenumber + 1] = Accid.Sharp

        return result

    def get_white_note(self, notenumber: int) -> WhiteNote:
        notescale = NoteScale.from_number(notenumber)
        octave = (notenumber + 3) // 12 - 1
        letter = 0

        whole_sharps = [
            WhiteNote.A, WhiteNote.A,
            WhiteNote.B,
            WhiteNote.C, WhiteNote.C,
            WhiteNote.D, WhiteNote.D,
            WhiteNote.E,
            WhiteNote.F, WhiteNote.F,
            WhiteNote.G, WhiteNote.G,
        ]
        whole_flats = [
            WhiteNote.A,
            WhiteNote.B, WhiteNote.B,
            WhiteNote.C,
            WhiteNote.D, WhiteNote.D,
            WhiteNote.E, WhiteNote.E,
            WhiteNote.F,
            WhiteNote.G, WhiteNote.G,
            WhiteNote.A,
        ]

        accid = self._keymap[notenumber]
        if accid == Accid.Flat:
            letter = whole_flats[notescale]
        elif accid == Accid.Sharp:
            letter = whole_sharps[notescale]
        elif accid == Accid.Natural:
            letter = whole_sharps[notescale]
        else:  # Accid.None_
            letter = whole_sharps[notescale]
            if NoteScale.is_black_key(notescale):
                if (
                    self._keymap[notenumber - 1] == Accid.Natural
                    and self._keymap[notenumber + 1] == Accid.Natural
                ):
                    if self.num_flats > 0:
                        letter = whole_flats[notescale]
                    else:
                        letter = whole_sharps[notescale]
                elif self._keymap[notenumber - 1] == Accid.Natural:
                    letter = whole_sharps[notescale]
                elif self._keymap[notenumber + 1] == Accid.Natural:
                    letter = whole_flats[notescale]

        # G-flat major edge cases
        if self.num_flats == KeySignature.Gflat and notescale == NoteScale.B:
            letter = WhiteNote.C
        if self.num_flats == KeySignature.Gflat and notescale == NoteScale.Bflat:
            letter = WhiteNote.B
        if self.num_flats > 0 and notescale == NoteScale.Aflat:
            octave += 1

        return WhiteNote(letter, octave)

    @staticmethod
    def guess(notes: List[int]) -> "KeySignature":
        KeySignature._create_accidental_maps()
        notecount = [0] * 12
        for notenumber in notes:
            notecount[(notenumber + 3) % 12] += 1

        bestkey = 0
        is_best_sharp = True
        smallest = len(notes) if notes else 0

        for key in range(6):
            count = 0
            for n in range(12):
                if KeySignature._sharp_keys[key][n] != Accid.None_:
                    count += notecount[n]
            if count < smallest:
                smallest = count
                bestkey = key
                is_best_sharp = True

        for key in range(7):
            count = 0
            for n in range(12):
                if KeySignature._flat_keys[key][n] != Accid.None_:
                    count += notecount[n]
            if count < smallest:
                smallest = count
                bestkey = key
                is_best_sharp = False

        if is_best_sharp:
            return KeySignature(bestkey, 0)
        return KeySignature(0, bestkey)

    def equals(self, other: "KeySignature") -> bool:
        return self.num_sharps == other.num_sharps and self.num_flats == other.num_flats

    def notescale(self) -> int:
        flat_major = [
            NoteScale.C, NoteScale.F, NoteScale.Bflat, NoteScale.Eflat,
            NoteScale.Aflat, NoteScale.Dflat, NoteScale.Gflat, NoteScale.B,
        ]
        sharp_major = [
            NoteScale.C, NoteScale.G, NoteScale.D, NoteScale.A, NoteScale.E,
            NoteScale.B, NoteScale.Fsharp, NoteScale.Csharp, NoteScale.Gsharp,
            NoteScale.Dsharp,
        ]
        if self.num_flats > 0:
            return flat_major[self.num_flats]
        return sharp_major[self.num_sharps]

    @staticmethod
    def key_to_string(notescale: int) -> str:
        names = {
            NoteScale.A: "A major, F# minor",
            NoteScale.Bflat: "B-flat major, G minor",
            NoteScale.B: "B major, A-flat minor",
            NoteScale.C: "C major, A minor",
            NoteScale.Dflat: "D-flat major, B-flat minor",
            NoteScale.D: "D major, B minor",
            NoteScale.Eflat: "E-flat major, C minor",
            NoteScale.E: "E major, C# minor",
            NoteScale.F: "F major, D minor",
            NoteScale.Gflat: "G-flat major, E-flat minor",
            NoteScale.G: "G major, E minor",
            NoteScale.Aflat: "A-flat major, F minor",
        }
        return names.get(notescale, "")

    def __repr__(self) -> str:
        return KeySignature.key_to_string(self.notescale())
