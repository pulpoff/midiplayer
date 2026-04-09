"""A single MIDI note (start/end time in pulses, pitch, channel).

Direct port of MidiNote.cs.
"""

from __future__ import annotations


class MidiNote:
    """A MIDI note with start time, channel, note number and duration."""

    __slots__ = ("starttime", "channel", "notenumber", "duration")

    def __init__(self, starttime: int, channel: int, notenumber: int, duration: int):
        self.starttime = starttime
        self.channel = channel
        self.notenumber = notenumber
        self.duration = duration

    # C# property names kept for parity with the rest of the port
    @property
    def StartTime(self) -> int:
        return self.starttime

    @StartTime.setter
    def StartTime(self, value: int) -> None:
        self.starttime = value

    @property
    def EndTime(self) -> int:
        return self.starttime + self.duration

    @property
    def Channel(self) -> int:
        return self.channel

    @Channel.setter
    def Channel(self, value: int) -> None:
        self.channel = value

    @property
    def Number(self) -> int:
        return self.notenumber

    @Number.setter
    def Number(self, value: int) -> None:
        self.notenumber = value

    @property
    def Duration(self) -> int:
        return self.duration

    @Duration.setter
    def Duration(self, value: int) -> None:
        self.duration = value

    def note_off(self, endtime: int) -> None:
        self.duration = endtime - self.starttime

    def clone(self) -> "MidiNote":
        return MidiNote(self.starttime, self.channel, self.notenumber, self.duration)

    def sort_key(self):
        """Return (StartTime, Number) for stable sorting."""
        return (self.starttime, self.notenumber)

    def __repr__(self) -> str:
        scale = ["A", "A#", "B", "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#"]
        return (
            f"MidiNote channel={self.channel} number={self.notenumber} "
            f"{scale[(self.notenumber + 3) % 12]} start={self.starttime} "
            f"duration={self.duration}"
        )
