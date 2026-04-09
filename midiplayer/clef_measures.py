"""Port of ClefMeasures.cs.

For each measure of a track, determine whether to render in treble or bass
clef based on the average MIDI note number.
"""

from __future__ import annotations

from typing import List

from .midi_note import MidiNote
from .music_theory import Clef, WhiteNote


class ClefMeasures:
    def __init__(self, notes: List[MidiNote], measurelen: int):
        self._measurelen = measurelen
        mainclef = ClefMeasures._main_clef(notes)
        nextmeasure = measurelen
        pos = 0
        clef = mainclef
        self._clefs: List[Clef] = []

        while pos < len(notes):
            sumnotes = 0
            notecount = 0
            while pos < len(notes) and notes[pos].StartTime < nextmeasure:
                sumnotes += notes[pos].Number
                notecount += 1
                pos += 1
            if notecount == 0:
                notecount = 1

            avgnote = sumnotes // notecount
            if avgnote == 0:
                # Keep previous clef
                pass
            elif avgnote >= WhiteNote.BOTTOM_TREBLE.number():
                clef = Clef.Treble
            elif avgnote <= WhiteNote.TOP_BASS.number():
                clef = Clef.Bass
            else:
                clef = mainclef

            self._clefs.append(clef)
            nextmeasure += measurelen

        self._clefs.append(clef)

    def get_clef(self, starttime: int) -> Clef:
        if starttime // self._measurelen >= len(self._clefs):
            return self._clefs[-1]
        return self._clefs[starttime // self._measurelen]

    GetClef = get_clef

    @staticmethod
    def _main_clef(notes: List[MidiNote]) -> Clef:
        if not notes:
            return Clef.Treble
        middle_c = WhiteNote.MIDDLE_C.number()
        total = sum(n.Number for n in notes)
        if total // len(notes) >= middle_c:
            return Clef.Treble
        return Clef.Bass
