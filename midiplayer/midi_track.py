"""A MIDI track: list of notes + instrument + optional lyrics.

Direct port of MidiTrack.cs.
"""

from __future__ import annotations

from typing import List, Optional

from .midi_event import MidiEvent
from .midi_note import MidiNote


# Instrument list lives on MidiFile; import lazily to avoid cycles.
def _instrument_name(instrument: int) -> str:
    from .midi_file import MidiFile  # noqa: WPS433

    if 0 <= instrument <= 128:
        return MidiFile.INSTRUMENTS[instrument]
    return ""


class MidiTrack:
    """A single track's notes, instrument, and optional lyric events."""

    def __init__(self, tracknum_or_events, tracknum: Optional[int] = None):
        """Two constructors, matching the C# overloads.

        - ``MidiTrack(tracknum)`` creates an empty track (used by ``clone()``
          and splitting).
        - ``MidiTrack(events, tracknum)`` parses a list of MidiEvents into
          notes + instrument.
        """
        self.notes: List[MidiNote] = []
        self.instrument: int = 0
        self.lyrics: Optional[List[MidiEvent]] = None

        if tracknum is None:
            # Single-arg form: tracknum only
            self.tracknum = int(tracknum_or_events)
            return

        self.tracknum = tracknum
        events: List[MidiEvent] = tracknum_or_events

        # Use integers to avoid circular imports with MidiFile constants
        EVENT_NOTE_ON = 0x90
        EVENT_NOTE_OFF = 0x80
        EVENT_PROGRAM_CHANGE = 0xC0
        META_EVENT_LYRIC = 0x5

        for mevent in events:
            if mevent.EventFlag == EVENT_NOTE_ON and mevent.Velocity > 0:
                note = MidiNote(
                    mevent.StartTime, mevent.Channel, mevent.Notenumber, 0
                )
                self.add_note(note)
            elif mevent.EventFlag == EVENT_NOTE_ON and mevent.Velocity == 0:
                self.note_off(mevent.Channel, mevent.Notenumber, mevent.StartTime)
            elif mevent.EventFlag == EVENT_NOTE_OFF:
                self.note_off(mevent.Channel, mevent.Notenumber, mevent.StartTime)
            elif mevent.EventFlag == EVENT_PROGRAM_CHANGE:
                self.instrument = mevent.Instrument
            elif mevent.Metaevent == META_EVENT_LYRIC:
                self.add_lyric(mevent)

        if self.notes and self.notes[0].Channel == 9:
            self.instrument = 128  # Percussion override

    # C# property aliases ---------------------------------------------------

    @property
    def Number(self) -> int:
        return self.tracknum

    @property
    def Notes(self) -> List[MidiNote]:
        return self.notes

    @property
    def Instrument(self) -> int:
        return self.instrument

    @Instrument.setter
    def Instrument(self, value: int) -> None:
        self.instrument = value

    @property
    def InstrumentName(self) -> str:
        return _instrument_name(self.instrument)

    @property
    def Lyrics(self) -> Optional[List[MidiEvent]]:
        return self.lyrics

    @Lyrics.setter
    def Lyrics(self, value: Optional[List[MidiEvent]]) -> None:
        self.lyrics = value

    # ----------------------------------------------------------------------

    def add_note(self, note: MidiNote) -> None:
        self.notes.append(note)

    def note_off(self, channel: int, notenumber: int, endtime: int) -> None:
        for i in range(len(self.notes) - 1, -1, -1):
            note = self.notes[i]
            if (
                note.Channel == channel
                and note.Number == notenumber
                and note.Duration == 0
            ):
                note.note_off(endtime)
                return

    def add_lyric(self, mevent: MidiEvent) -> None:
        if self.lyrics is None:
            self.lyrics = []
        self.lyrics.append(mevent)

    def clone(self) -> "MidiTrack":
        track = MidiTrack(self.tracknum)
        track.instrument = self.instrument
        track.notes = [note.clone() for note in self.notes]
        if self.lyrics is not None:
            track.lyrics = list(self.lyrics)
        return track

    def __repr__(self) -> str:
        lines = [f"Track number={self.tracknum} instrument={self.instrument}"]
        lines += [repr(note) for note in self.notes]
        lines.append("End Track")
        return "\n".join(lines)
