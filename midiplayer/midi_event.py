"""A single MIDI event. Direct port of MidiEvent.cs."""

from __future__ import annotations


class MidiEvent:
    """A single MIDI event — channel message, sysex, or meta event.

    This is a union-style container: only the fields relevant to the event's
    EventFlag / Metaevent are meaningful at any time. Matches the C# class.
    """

    __slots__ = (
        "DeltaTime",
        "StartTime",
        "HasEventflag",
        "EventFlag",
        "Channel",
        "Notenumber",
        "Velocity",
        "Instrument",
        "KeyPressure",
        "ChanPressure",
        "ControlNum",
        "ControlValue",
        "PitchBend",
        "Numerator",
        "Denominator",
        "Tempo",
        "Metaevent",
        "Metalength",
        "Value",
    )

    def __init__(self) -> None:
        self.DeltaTime = 0
        self.StartTime = 0
        self.HasEventflag = False
        self.EventFlag = 0
        self.Channel = 0
        self.Notenumber = 0
        self.Velocity = 0
        self.Instrument = 0
        self.KeyPressure = 0
        self.ChanPressure = 0
        self.ControlNum = 0
        self.ControlValue = 0
        self.PitchBend = 0
        self.Numerator = 0
        self.Denominator = 0
        self.Tempo = 0
        self.Metaevent = 0
        self.Metalength = 0
        self.Value = b""

    def clone(self) -> "MidiEvent":
        other = MidiEvent()
        other.DeltaTime = self.DeltaTime
        other.StartTime = self.StartTime
        other.HasEventflag = self.HasEventflag
        other.EventFlag = self.EventFlag
        other.Channel = self.Channel
        other.Notenumber = self.Notenumber
        other.Velocity = self.Velocity
        other.Instrument = self.Instrument
        other.KeyPressure = self.KeyPressure
        other.ChanPressure = self.ChanPressure
        other.ControlNum = self.ControlNum
        other.ControlValue = self.ControlValue
        other.PitchBend = self.PitchBend
        other.Numerator = self.Numerator
        other.Denominator = self.Denominator
        other.Tempo = self.Tempo
        other.Metaevent = self.Metaevent
        other.Metalength = self.Metalength
        other.Value = self.Value
        return other

    def sort_key(self):
        """Return a tuple suitable for sorted()/list.sort() on MidiEvents."""
        return (self.StartTime, self.EventFlag, self.Notenumber)
