"""Port of MidiFile.cs — MIDI file parsing and option application.

This is a faithful translation of the parsing pipeline, ChangeMidiNotes
(sheet-music-side transforms), and the pulse/time-rounding helpers. The
original's ``ChangeSound`` / ``Write`` path rewrites a temporary MIDI file
for the C# player to feed to ``timidity``. In this port, the player uses
FluidSynth directly, so we only need ``ChangeMidiNotes`` for the sheet
display; playback options are applied live via FluidSynth.
"""

from __future__ import annotations

from typing import List, Optional

from .midi_event import MidiEvent
from .midi_file_reader import MidiFileException, MidiFileReader
from .midi_note import MidiNote
from .midi_track import MidiTrack
from .music_theory import TimeSignature


class MidiFile:
    """A parsed MIDI file."""

    # Event codes
    EVENT_NOTE_OFF = 0x80
    EVENT_NOTE_ON = 0x90
    EVENT_KEY_PRESSURE = 0xA0
    EVENT_CONTROL_CHANGE = 0xB0
    EVENT_PROGRAM_CHANGE = 0xC0
    EVENT_CHANNEL_PRESSURE = 0xD0
    EVENT_PITCH_BEND = 0xE0
    SYSEX_EVENT1 = 0xF0
    SYSEX_EVENT2 = 0xF7
    META_EVENT = 0xFF

    # Meta event codes
    META_EVENT_SEQUENCE = 0x0
    META_EVENT_TEXT = 0x1
    META_EVENT_COPYRIGHT = 0x2
    META_EVENT_SEQUENCE_NAME = 0x3
    META_EVENT_INSTRUMENT = 0x4
    META_EVENT_LYRIC = 0x5
    META_EVENT_MARKER = 0x6
    META_EVENT_END_OF_TRACK = 0x2F
    META_EVENT_TEMPO = 0x51
    META_EVENT_SMPTE_OFFSET = 0x54
    META_EVENT_TIME_SIGNATURE = 0x58
    META_EVENT_KEY_SIGNATURE = 0x59

    INSTRUMENTS = [
        "Acoustic Grand Piano", "Bright Acoustic Piano", "Electric Grand Piano",
        "Honky-tonk Piano", "Electric Piano 1", "Electric Piano 2",
        "Harpsichord", "Clavi", "Celesta", "Glockenspiel", "Music Box",
        "Vibraphone", "Marimba", "Xylophone", "Tubular Bells", "Dulcimer",
        "Drawbar Organ", "Percussive Organ", "Rock Organ", "Church Organ",
        "Reed Organ", "Accordion", "Harmonica", "Tango Accordion",
        "Acoustic Guitar (nylon)", "Acoustic Guitar (steel)",
        "Electric Guitar (jazz)", "Electric Guitar (clean)",
        "Electric Guitar (muted)", "Overdriven Guitar", "Distortion Guitar",
        "Guitar harmonics", "Acoustic Bass", "Electric Bass (finger)",
        "Electric Bass (pick)", "Fretless Bass", "Slap Bass 1", "Slap Bass 2",
        "Synth Bass 1", "Synth Bass 2", "Violin", "Viola", "Cello", "Contrabass",
        "Tremolo Strings", "Pizzicato Strings", "Orchestral Harp", "Timpani",
        "String Ensemble 1", "String Ensemble 2", "SynthStrings 1",
        "SynthStrings 2", "Choir Aahs", "Voice Oohs", "Synth Voice",
        "Orchestra Hit", "Trumpet", "Trombone", "Tuba", "Muted Trumpet",
        "French Horn", "Brass Section", "SynthBrass 1", "SynthBrass 2",
        "Soprano Sax", "Alto Sax", "Tenor Sax", "Baritone Sax", "Oboe",
        "English Horn", "Bassoon", "Clarinet", "Piccolo", "Flute", "Recorder",
        "Pan Flute", "Blown Bottle", "Shakuhachi", "Whistle", "Ocarina",
        "Lead 1 (square)", "Lead 2 (sawtooth)", "Lead 3 (calliope)",
        "Lead 4 (chiff)", "Lead 5 (charang)", "Lead 6 (voice)",
        "Lead 7 (fifths)", "Lead 8 (bass + lead)", "Pad 1 (new age)",
        "Pad 2 (warm)", "Pad 3 (polysynth)", "Pad 4 (choir)", "Pad 5 (bowed)",
        "Pad 6 (metallic)", "Pad 7 (halo)", "Pad 8 (sweep)", "FX 1 (rain)",
        "FX 2 (soundtrack)", "FX 3 (crystal)", "FX 4 (atmosphere)",
        "FX 5 (brightness)", "FX 6 (goblins)", "FX 7 (echoes)", "FX 8 (sci-fi)",
        "Sitar", "Banjo", "Shamisen", "Koto", "Kalimba", "Bag pipe", "Fiddle",
        "Shanai", "Tinkle Bell", "Agogo", "Steel Drums", "Woodblock",
        "Taiko Drum", "Melodic Tom", "Synth Drum", "Reverse Cymbal",
        "Guitar Fret Noise", "Breath Noise", "Seashore", "Bird Tweet",
        "Telephone Ring", "Helicopter", "Applause", "Gunshot", "Percussion",
    ]

    def __init__(self, source, title: Optional[str] = None):
        """Parse a MIDI file from a path (str) or bytes."""
        self.filename = ""
        self.events: List[List[MidiEvent]] = []
        self.tracks: List[MidiTrack] = []
        self.trackmode = 0
        self.timesig: Optional[TimeSignature] = None
        self.quarternote = 0
        self.totalpulses = 0
        self.trackPerChannel = False

        if isinstance(source, (bytes, bytearray)):
            reader = MidiFileReader(source)
            self._parse(reader, title or "")
        else:
            reader = MidiFileReader(source)
            self._parse(reader, source)

    # C# property aliases ---------------------------------------------------

    @property
    def Tracks(self) -> List[MidiTrack]:
        return self.tracks

    @property
    def Time(self) -> TimeSignature:
        return self.timesig  # type: ignore[return-value]

    @property
    def FileName(self) -> str:
        return self.filename

    @property
    def TotalPulses(self) -> int:
        return self.totalpulses

    # ----------------------------------------------------------------------

    def _parse(self, reader: MidiFileReader, filename: str) -> None:
        self.filename = filename
        self.tracks = []
        self.trackPerChannel = False

        header = reader.read_ascii(4)
        if header != "MThd":
            raise MidiFileException("Doesn't start with MThd", 0)
        length = reader.read_int()
        if length != 6:
            raise MidiFileException("Bad MThd header", 4)
        self.trackmode = reader.read_short()
        num_tracks = reader.read_short()
        self.quarternote = reader.read_short()

        self.events = []
        for tracknum in range(num_tracks):
            track_events = self._read_track(reader)
            self.events.append(track_events)
            track = MidiTrack(track_events, tracknum)
            if len(track.Notes) > 0 or track.Lyrics is not None:
                self.tracks.append(track)

        # Song length in pulses
        for track in self.tracks:
            if not track.Notes:
                continue
            last = track.Notes[-1]
            if self.totalpulses < last.StartTime + last.Duration:
                self.totalpulses = last.StartTime + last.Duration

        # Single track with multiple channels -> treat each channel as a track
        if len(self.tracks) == 1 and MidiFile._has_multiple_channels(self.tracks[0]):
            self.tracks = self._split_channels(
                self.tracks[0], self.events[self.tracks[0].Number]
            )
            self.trackPerChannel = True

        MidiFile._check_start_times(self.tracks)

        # Time signature + tempo from meta events
        tempo = 0
        numer = 0
        denom = 0
        for event_list in self.events:
            for mevent in event_list:
                if mevent.Metaevent == MidiFile.META_EVENT_TEMPO and tempo == 0:
                    tempo = mevent.Tempo
                if (
                    mevent.Metaevent == MidiFile.META_EVENT_TIME_SIGNATURE
                    and numer == 0
                ):
                    numer = mevent.Numerator
                    denom = mevent.Denominator
        if tempo == 0:
            tempo = 500000  # default: 120 bpm
        if numer == 0:
            numer = 4
            denom = 4
        self.timesig = TimeSignature(numer, denom, self.quarternote, tempo)

    def _read_track(self, reader: MidiFileReader) -> List[MidiEvent]:
        result: List[MidiEvent] = []
        starttime = 0
        header = reader.read_ascii(4)
        if header != "MTrk":
            raise MidiFileException("Bad MTrk header", reader.get_offset() - 4)
        tracklen = reader.read_int()
        trackend = tracklen + reader.get_offset()
        eventflag = 0

        while reader.get_offset() < trackend:
            try:
                deltatime = reader.read_varlen()
                starttime += deltatime
                peekevent = reader.peek()
            except MidiFileException:
                return result

            mevent = MidiEvent()
            result.append(mevent)
            mevent.DeltaTime = deltatime
            mevent.StartTime = starttime

            if peekevent >= MidiFile.EVENT_NOTE_OFF:
                mevent.HasEventflag = True
                eventflag = reader.read_byte()

            if (
                MidiFile.EVENT_NOTE_ON
                <= eventflag
                < MidiFile.EVENT_NOTE_ON + 16
            ):
                mevent.EventFlag = MidiFile.EVENT_NOTE_ON
                mevent.Channel = eventflag - MidiFile.EVENT_NOTE_ON
                mevent.Notenumber = reader.read_byte()
                mevent.Velocity = reader.read_byte()
            elif (
                MidiFile.EVENT_NOTE_OFF
                <= eventflag
                < MidiFile.EVENT_NOTE_OFF + 16
            ):
                mevent.EventFlag = MidiFile.EVENT_NOTE_OFF
                mevent.Channel = eventflag - MidiFile.EVENT_NOTE_OFF
                mevent.Notenumber = reader.read_byte()
                mevent.Velocity = reader.read_byte()
            elif (
                MidiFile.EVENT_KEY_PRESSURE
                <= eventflag
                < MidiFile.EVENT_KEY_PRESSURE + 16
            ):
                mevent.EventFlag = MidiFile.EVENT_KEY_PRESSURE
                mevent.Channel = eventflag - MidiFile.EVENT_KEY_PRESSURE
                mevent.Notenumber = reader.read_byte()
                mevent.KeyPressure = reader.read_byte()
            elif (
                MidiFile.EVENT_CONTROL_CHANGE
                <= eventflag
                < MidiFile.EVENT_CONTROL_CHANGE + 16
            ):
                mevent.EventFlag = MidiFile.EVENT_CONTROL_CHANGE
                mevent.Channel = eventflag - MidiFile.EVENT_CONTROL_CHANGE
                mevent.ControlNum = reader.read_byte()
                mevent.ControlValue = reader.read_byte()
            elif (
                MidiFile.EVENT_PROGRAM_CHANGE
                <= eventflag
                < MidiFile.EVENT_PROGRAM_CHANGE + 16
            ):
                mevent.EventFlag = MidiFile.EVENT_PROGRAM_CHANGE
                mevent.Channel = eventflag - MidiFile.EVENT_PROGRAM_CHANGE
                mevent.Instrument = reader.read_byte()
            elif (
                MidiFile.EVENT_CHANNEL_PRESSURE
                <= eventflag
                < MidiFile.EVENT_CHANNEL_PRESSURE + 16
            ):
                mevent.EventFlag = MidiFile.EVENT_CHANNEL_PRESSURE
                mevent.Channel = eventflag - MidiFile.EVENT_CHANNEL_PRESSURE
                mevent.ChanPressure = reader.read_byte()
            elif (
                MidiFile.EVENT_PITCH_BEND
                <= eventflag
                < MidiFile.EVENT_PITCH_BEND + 16
            ):
                mevent.EventFlag = MidiFile.EVENT_PITCH_BEND
                mevent.Channel = eventflag - MidiFile.EVENT_PITCH_BEND
                mevent.PitchBend = reader.read_short()
            elif eventflag == MidiFile.SYSEX_EVENT1:
                mevent.EventFlag = MidiFile.SYSEX_EVENT1
                mevent.Metalength = reader.read_varlen()
                mevent.Value = reader.read_bytes(mevent.Metalength)
            elif eventflag == MidiFile.SYSEX_EVENT2:
                mevent.EventFlag = MidiFile.SYSEX_EVENT2
                mevent.Metalength = reader.read_varlen()
                mevent.Value = reader.read_bytes(mevent.Metalength)
            elif eventflag == MidiFile.META_EVENT:
                mevent.EventFlag = MidiFile.META_EVENT
                mevent.Metaevent = reader.read_byte()
                mevent.Metalength = reader.read_varlen()
                mevent.Value = reader.read_bytes(mevent.Metalength)
                if mevent.Metaevent == MidiFile.META_EVENT_TIME_SIGNATURE:
                    if mevent.Metalength < 2:
                        mevent.Numerator = 0
                        mevent.Denominator = 4
                    else:
                        mevent.Numerator = mevent.Value[0]
                        mevent.Denominator = int(2 ** mevent.Value[1])
                elif mevent.Metaevent == MidiFile.META_EVENT_TEMPO:
                    if mevent.Metalength != 3:
                        raise MidiFileException(
                            f"Meta Event Tempo len == {mevent.Metalength} != 3",
                            reader.get_offset(),
                        )
                    mevent.Tempo = (
                        (mevent.Value[0] << 16)
                        | (mevent.Value[1] << 8)
                        | mevent.Value[2]
                    )
            else:
                raise MidiFileException(
                    f"Unknown event {mevent.EventFlag}",
                    reader.get_offset() - 1,
                )

        return result

    # ----------------------------------------------------------------------
    # Option application (sheet music side)
    # ----------------------------------------------------------------------

    def change_midi_notes(self, options) -> List[MidiTrack]:
        """Apply sheet-music menu options to a copy of the parsed tracks."""
        newtracks: List[MidiTrack] = []
        for track in range(len(self.tracks)):
            if options.tracks[track]:
                newtracks.append(self.tracks[track].clone())

        time = options.time if options.time is not None else self.timesig

        MidiFile.round_start_times(newtracks, options.combineInterval, self.timesig)
        MidiFile.round_durations(newtracks, time.Quarter)

        if options.twoStaffs:
            newtracks = MidiFile.combine_to_two_tracks(newtracks, self.timesig.Measure)
        if options.shifttime != 0:
            MidiFile.shift_time(newtracks, options.shifttime)
        if options.transpose != 0:
            MidiFile.transpose(newtracks, options.transpose)

        return newtracks

    # Alias to keep existing code in the port idiomatic to the C# name
    ChangeMidiNotes = change_midi_notes

    # ----------------------------------------------------------------------
    # Static helpers
    # ----------------------------------------------------------------------

    @staticmethod
    def _has_multiple_channels(track: MidiTrack) -> bool:
        channel = track.Notes[0].Channel
        return any(note.Channel != channel for note in track.Notes)

    @staticmethod
    def _check_start_times(tracks: List[MidiTrack]) -> None:
        for track in tracks:
            prevtime = -1
            for note in track.Notes:
                if note.StartTime < prevtime:
                    raise ValueError("start times not in increasing order")
                prevtime = note.StartTime

    @staticmethod
    def _split_channels(
        origtrack: MidiTrack, events: List[MidiEvent]
    ) -> List[MidiTrack]:
        channel_instruments = [0] * 16
        for mevent in events:
            if mevent.EventFlag == MidiFile.EVENT_PROGRAM_CHANGE:
                channel_instruments[mevent.Channel] = mevent.Instrument
        channel_instruments[9] = 128  # Percussion

        result: List[MidiTrack] = []
        for note in origtrack.Notes:
            found = False
            for track in result:
                if note.Channel == track.Notes[0].Channel:
                    track.add_note(note)
                    found = True
                    break
            if not found:
                track = MidiTrack(len(result) + 1)
                track.add_note(note)
                track.Instrument = channel_instruments[note.Channel]
                result.append(track)

        if origtrack.Lyrics is not None:
            for lyric in origtrack.Lyrics:
                for track in result:
                    if lyric.Channel == track.Notes[0].Channel:
                        track.add_lyric(lyric)
        return result

    @staticmethod
    def shift_time(tracks: List[MidiTrack], amount: int) -> None:
        for track in tracks:
            for note in track.Notes:
                note.StartTime = note.StartTime + amount

    @staticmethod
    def transpose(tracks: List[MidiTrack], amount: int) -> None:
        for track in tracks:
            for note in track.Notes:
                note.Number = max(0, note.Number + amount)

    @staticmethod
    def _find_high_low_notes(
        notes: List[MidiNote],
        measurelen: int,
        startindex: int,
        starttime: int,
        endtime: int,
        high: int,
        low: int,
    ):
        """Return (high, low) considering notes overlapping [starttime, endtime)."""
        i = startindex
        if starttime + measurelen < endtime:
            endtime = starttime + measurelen
        while i < len(notes) and notes[i].StartTime < endtime:
            if notes[i].EndTime < starttime:
                i += 1
                continue
            if notes[i].StartTime + measurelen < starttime:
                i += 1
                continue
            if high < notes[i].Number:
                high = notes[i].Number
            if low > notes[i].Number:
                low = notes[i].Number
            i += 1
        return high, low

    @staticmethod
    def _find_exact_high_low_notes(
        notes: List[MidiNote],
        startindex: int,
        starttime: int,
        high: int,
        low: int,
    ):
        i = startindex
        while notes[i].StartTime < starttime:
            i += 1
        while i < len(notes) and notes[i].StartTime == starttime:
            if high < notes[i].Number:
                high = notes[i].Number
            if low > notes[i].Number:
                low = notes[i].Number
            i += 1
        return high, low

    @staticmethod
    def split_track(track: MidiTrack, measurelen: int) -> List[MidiTrack]:
        notes = track.Notes
        top = MidiTrack(1)
        bottom = MidiTrack(2)
        result = [top, bottom]
        if not notes:
            return result

        prevhigh = 76  # E5, top of treble staff
        prevlow = 45  # A3, bottom of bass staff
        startindex = 0

        for note in notes:
            number = note.Number
            high = low = highExact = lowExact = number

            while notes[startindex].EndTime < note.StartTime:
                startindex += 1

            high, low = MidiFile._find_high_low_notes(
                notes, measurelen, startindex,
                note.StartTime, note.EndTime, high, low,
            )
            highExact, lowExact = MidiFile._find_exact_high_low_notes(
                notes, startindex, note.StartTime, highExact, lowExact
            )

            if highExact - number > 12 or number - lowExact > 12:
                if highExact - number <= number - lowExact:
                    top.add_note(note)
                else:
                    bottom.add_note(note)
            elif high - number > 12 or number - low > 12:
                if high - number <= number - low:
                    top.add_note(note)
                else:
                    bottom.add_note(note)
            elif highExact - lowExact > 12:
                if highExact - number <= number - lowExact:
                    top.add_note(note)
                else:
                    bottom.add_note(note)
            elif high - low > 12:
                if high - number <= number - low:
                    top.add_note(note)
                else:
                    bottom.add_note(note)
            else:
                if prevhigh - number <= number - prevlow:
                    top.add_note(note)
                else:
                    bottom.add_note(note)

            if high - low > 12:
                prevhigh = high
                prevlow = low

        top.Notes.sort(key=lambda n: n.sort_key())
        bottom.Notes.sort(key=lambda n: n.sort_key())
        return result

    @staticmethod
    def combine_to_single_track(tracks: List[MidiTrack]) -> MidiTrack:
        result = MidiTrack(1)
        if not tracks:
            return result
        if len(tracks) == 1:
            for note in tracks[0].Notes:
                result.add_note(note)
            return result

        noteindex = [0] * len(tracks)
        notecount = [len(t.Notes) for t in tracks]
        prevnote: Optional[MidiNote] = None

        while True:
            lowestnote: Optional[MidiNote] = None
            lowestTrack = -1
            for tracknum, track in enumerate(tracks):
                if noteindex[tracknum] >= notecount[tracknum]:
                    continue
                note = track.Notes[noteindex[tracknum]]
                if lowestnote is None:
                    lowestnote = note
                    lowestTrack = tracknum
                elif note.StartTime < lowestnote.StartTime:
                    lowestnote = note
                    lowestTrack = tracknum
                elif (
                    note.StartTime == lowestnote.StartTime
                    and note.Number < lowestnote.Number
                ):
                    lowestnote = note
                    lowestTrack = tracknum
            if lowestnote is None:
                break
            noteindex[lowestTrack] += 1
            if (
                prevnote is not None
                and prevnote.StartTime == lowestnote.StartTime
                and prevnote.Number == lowestnote.Number
            ):
                if lowestnote.Duration > prevnote.Duration:
                    prevnote.Duration = lowestnote.Duration
            else:
                result.add_note(lowestnote)
                prevnote = lowestnote
        return result

    @staticmethod
    def combine_to_two_tracks(
        tracks: List[MidiTrack], measurelen: int
    ) -> List[MidiTrack]:
        single = MidiFile.combine_to_single_track(tracks)
        result = MidiFile.split_track(single, measurelen)

        lyrics: List[MidiEvent] = []
        for track in tracks:
            if track.Lyrics is not None:
                lyrics.extend(track.Lyrics)
        if lyrics:
            lyrics.sort(key=lambda e: e.sort_key())
            result[0].Lyrics = lyrics
        return result

    # Aliases for the rest of the port
    CombineToSingleTrack = combine_to_single_track

    @staticmethod
    def round_start_times(
        tracks: List[MidiTrack], millisec: int, time: TimeSignature
    ) -> None:
        starttimes: List[int] = []
        for track in tracks:
            for note in track.Notes:
                starttimes.append(note.StartTime)
        starttimes.sort()

        interval = time.Quarter * millisec * 1000 // time.Tempo

        for i in range(len(starttimes) - 1):
            if starttimes[i + 1] - starttimes[i] <= interval:
                starttimes[i + 1] = starttimes[i]

        MidiFile._check_start_times(tracks)

        for track in tracks:
            i = 0
            for note in track.Notes:
                while (
                    i < len(starttimes)
                    and note.StartTime - interval > starttimes[i]
                ):
                    i += 1
                if (
                    i < len(starttimes)
                    and note.StartTime > starttimes[i]
                    and note.StartTime - starttimes[i] <= interval
                ):
                    note.StartTime = starttimes[i]
            track.Notes.sort(key=lambda n: n.sort_key())

    @staticmethod
    def round_durations(tracks: List[MidiTrack], quarternote: int) -> None:
        for track in tracks:
            prevNote: Optional[MidiNote] = None
            notes = track.Notes
            for i in range(len(notes) - 1):
                note1 = notes[i]
                if prevNote is None:
                    prevNote = note1

                note2 = note1
                for j in range(i + 1, len(notes)):
                    note2 = notes[j]
                    if note1.StartTime < note2.StartTime:
                        break
                maxduration = note2.StartTime - note1.StartTime

                dur = 0
                if quarternote <= maxduration:
                    dur = quarternote
                elif quarternote // 2 <= maxduration:
                    dur = quarternote // 2
                elif quarternote // 3 <= maxduration:
                    dur = quarternote // 3
                elif quarternote // 4 <= maxduration:
                    dur = quarternote // 4

                if dur < note1.Duration:
                    dur = note1.Duration

                if (
                    prevNote.StartTime + prevNote.Duration == note1.StartTime
                    and prevNote.Duration == note1.Duration
                ):
                    dur = note1.Duration

                note1.Duration = dur
                if notes[i + 1].StartTime != note1.StartTime:
                    prevNote = note1

    def end_time(self) -> int:
        last_start = 0
        for track in self.tracks:
            if not track.Notes:
                continue
            last = track.Notes[-1].StartTime
            last_start = max(last, last_start)
        return last_start

    EndTime = end_time

    def has_lyrics(self) -> bool:
        return any(track.Lyrics is not None for track in self.tracks)

    def __repr__(self) -> str:
        parts = [
            f"Midi File tracks={len(self.tracks)} quarter={self.quarternote}",
            repr(self.timesig),
        ]
        parts.extend(repr(track) for track in self.tracks)
        return "\n".join(parts)
