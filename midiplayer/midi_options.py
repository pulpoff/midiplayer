"""Port of MidiOptions.cs.

A plain options container wired to the sheet music menu + player toolbar.
Playback-specific fields that only made sense for the C# timidity pipeline
(``pauseTime``, ``useDefaultInstruments``) are kept for parity; the
FluidSynth-based player reads them directly.
"""

from __future__ import annotations

import os
from typing import List, Optional

from .music_theory import TimeSignature


class MidiOptions:
    """Sheet music + sound options."""

    # showNoteLetters values
    NoteNameNone = 0
    NoteNameLetter = 1
    NoteNameFixedDoReMi = 2
    NoteNameMovableDoReMi = 3
    NoteNameFixedNumber = 4
    NoteNameMovableNumber = 5

    def __init__(self, midifile=None):
        # Sheet Music Options
        self.filename: str = ""
        self.title: str = ""
        self.tracks: List[bool] = []
        self.scrollVert: bool = True
        self.largeNoteSize: bool = False
        self.twoStaffs: bool = False
        self.showNoteLetters: int = MidiOptions.NoteNameNone
        self.showLyrics: bool = True
        self.showMeasures: bool = False
        self.shifttime: int = 0
        self.transpose: int = 0
        self.key: int = -1
        self.time: Optional[TimeSignature] = None
        self.combineInterval: int = 40
        self.colors: Optional[List[tuple]] = None
        # Default shade colors — RGB tuples (0-255)
        self.shadeColor: tuple = (210, 205, 220)
        self.shade2Color: tuple = (80, 100, 250)

        # Sound options
        self.mute: List[bool] = []
        self.tempo: int = 0
        self.pauseTime: int = 0
        self.instruments: List[int] = []
        self.useDefaultInstruments: bool = True
        self.playMeasuresInLoop: bool = False
        self.playMeasuresInLoopStart: int = 0
        self.playMeasuresInLoopEnd: int = 0

        if midifile is not None:
            self._init_from_file(midifile)

    def _init_from_file(self, midifile) -> None:
        self.filename = midifile.FileName
        self.title = os.path.basename(midifile.FileName)
        numtracks = len(midifile.Tracks)

        self.tracks = [True] * numtracks
        self.mute = [False] * numtracks
        self.instruments = [0] * numtracks
        for i in range(numtracks):
            self.instruments[i] = midifile.Tracks[i].Instrument
            if midifile.Tracks[i].InstrumentName == "Percussion":
                self.tracks[i] = False
                self.mute[i] = True

        self.useDefaultInstruments = True
        self.scrollVert = False
        self.largeNoteSize = False
        self.twoStaffs = (numtracks == 1)
        self.showNoteLetters = MidiOptions.NoteNameNone
        self.showLyrics = True
        self.showMeasures = False
        self.shifttime = 0
        self.transpose = 0
        self.key = -1
        self.time = midifile.Time
        self.colors = None
        self.shadeColor = (210, 205, 220)
        self.shade2Color = (80, 100, 250)
        self.combineInterval = 40
        self.tempo = midifile.Time.Tempo
        self.pauseTime = 0
        self.playMeasuresInLoop = False
        self.playMeasuresInLoopStart = 0
        self.playMeasuresInLoopEnd = midifile.end_time() // midifile.Time.Measure
