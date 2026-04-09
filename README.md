# midiplayer

A modern GTK4 MIDI sheet music player for Linux, based on Madhav
Vaidyanathan's [MidiSheetMusic](http://midisheetmusic.com/) 2.6.

The original is a C#/Mono WinForms application that ships with a Linux build
script targeting `xbuild` and the `timidity` CLI for playback. This project is
a ground-up Python port that keeps the same look and layout algorithms but
swaps the runtime out for a stack that's native on modern Debian/Ubuntu:

| Concern        | Original (2.6)           | This port                          |
|----------------|--------------------------|-------------------------------------|
| Language       | C# / Mono                | Python 3                            |
| GUI toolkit    | System.Windows.Forms     | GTK 4 (PyGObject)                   |
| Drawing        | System.Drawing / GDI+    | Cairo (via `Gtk.DrawingArea`)       |
| MIDI synthesis | `timidity` subprocess    | **FluidSynth** (`python-fluidsynth`) |
| Audio output   | ALSA via timidity        | PipeWire / PulseAudio / ALSA (auto) |
| Build system   | `xbuild` + Mono          | `apt install` only — no compiler    |

The goal is that the app **looks the same** as the original — same grand-staff
engraving, same piano keyboard with left-hand / right-hand shading, same
toolbar with rewind / play / stop / fast-forward / speed / volume — while
running on a current GNOME desktop with proper audio hardware support.

## Status

Work in progress on branch `claude/modernize-midi-player-oYmls`. The port is
being landed incrementally; see the commit log for the current state.

Landed so far:

- Music theory primitives (`NoteScale`, `WhiteNote`, `Clef`, `Accid`,
  `NoteDuration`, `TimeSignature`)
- Major key signature with sharp/flat maps, accidental tracking, and the
  key-guessing heuristic

Up next:

- MIDI file parser (`MidiFile`, `MidiTrack`, `MidiNote`, `MidiEvent`,
  `MidiFileReader`) and `MidiOptions`
- Music symbol classes and their Cairo drawing routines (`MusicSymbol`,
  `BlankSymbol`, `BarSymbol`, `ClefSymbol`, `TimeSigSymbol`, `AccidSymbol`,
  `RestSymbol`, `ChordSymbol`, `Stem`)
- Layout engine (`ClefMeasures`, `SymbolWidths`, `Staff`, `SheetMusic`)
- `Piano` widget — GTK4 `DrawingArea` with realistic key rendering and
  playback highlighting
- `MidiPlayer` toolbar widget with FluidSynth backend
- `SheetMusicWindow` — GTK4 `ApplicationWindow` with the original's
  File / View / Color / Tracks / Notes / Help menu bar
- `build.sh` one-shot installer + entry point

## Building (planned)

Once the port is complete, building and running will be a single command on
Debian / Ubuntu / any derivative:

```sh
./build.sh
```

Under the hood this will `apt install` the Python + GTK4 + FluidSynth runtime
dependencies (no compilation step — pure Python) and then launch the app.
Planned package list:

```
python3 python3-gi python3-gi-cairo gir1.2-gtk-4.0
fluidsynth python3-fluidsynth fluid-soundfont-gm
```

## Layout

```
midiplayer/                 Python package
  music_theory.py           NoteScale, WhiteNote, Clef, Accid, TimeSignature
  key_signature.py          KeySignature with sharp/flat maps + guessing
  resources/                Clef + time signature images (from the original)
MidiSheetMusic-2.6-linux-src.tar.gz   Original C# source (reference)
Bach__Invention_No._13.mid  Sample MIDI for smoke tests
Bach__Musette_in_D_major.mid
```

## Credits

The sheet music engraving algorithms, layout math, and visual design are all
from Madhav Vaidyanathan's MidiSheetMusic 2.6, licensed under GPLv2. This port
preserves that license.
