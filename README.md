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

## Building and running

On Debian / Ubuntu / any derivative, the whole workflow is a single command:

```sh
./build.sh
```

On first run, `build.sh` will `sudo apt-get install` any missing runtime
dependencies and then launch the app. There is no compilation step — this
is a pure Python project:

```
python3 python3-gi python3-gi-cairo python3-cairo gir1.2-gtk-4.0
fluidsynth python3-fluidsynth fluid-soundfont-gm
```

You can also pass a MIDI file directly:

```sh
./build.sh Bach__Musette_in_D_major.mid
```

Or skip the install / launch steps individually:

```sh
./build.sh --deps     # install runtime dependencies, don't launch
./build.sh --run      # launch without re-checking dependencies
./build.sh --run file.mid
```

The app can also be launched directly once dependencies are installed:

```sh
python3 -m midiplayer [file.mid]
```

## Status

Functionally complete and smoke-tested against both bundled Bach MIDI
files. The layout engine reproduces the engraving algorithms from the
original pixel-for-pixel; the GUI matches the original's menu bar,
toolbar, piano panel and scrollable sheet area.

Landed:

- Music theory primitives (`NoteScale`, `WhiteNote`, `Clef`, `Accid`,
  `NoteDuration`, `TimeSignature`) and major key signature with
  sharp/flat maps, per-measure accidental tracking, and key guessing
- MIDI file parser (`MidiFileReader`, `MidiEvent`, `MidiNote`,
  `MidiTrack`, `MidiFile`) with `ChangeMidiNotes`, `RoundStartTimes`,
  `RoundDurations`, `SplitTrack`, `CombineToSingleTrack`,
  `CombineToTwoTracks`, and `MidiOptions`
- Music symbol classes with Cairo draw routines — `MusicSymbol`,
  `BlankSymbol`, `BarSymbol`, `ClefSymbol` (PNG clef images),
  `TimeSigSymbol` (PNG digit images), `AccidSymbol`, `RestSymbol`,
  `ChordSymbol` with `NoteData`, ledger lines, dotted notes and beam
  creation, plus `Stem` with curvy flags and horizontal beams
- Layout engine (`ClefMeasures`, `SymbolWidths`, `Staff`, `SheetMusic`):
  chord grouping, bar insertion, rest filling, clef changes, cross-track
  alignment, staff partitioning respecting measure boundaries, full
  justification, beam creation, zoom, drawing and playback shading
- `Piano` keyboard renderer matching the original's
  pixel-perfect look (black border frame, realistic black keys, two-
  colour shading for left/right hand in two-track songs)
- `AudioPlayer` — FluidSynth backend replacing the original `timidity`
  subprocess, with live transpose / mute / instrument / volume /
  speed support, talking to PipeWire / PulseAudio / ALSA automatically
- GTK4 widgets (`SheetMusicWidget`, `PianoWidget`, `PlayerWidget`) and
  `SheetMusicWindow` with the original's File / View / Color / Tracks /
  Notes / Help menu bar, Play / Stop / Rewind / Fast-forward buttons,
  Speed and Volume sliders, and click-to-seek
- `build.sh` one-shot installer + entry point

## Layout

```
build.sh                    One-shot installer + launcher
midiplayer/                 Python package
  __main__.py               python -m midiplayer entry point
  app.py                    Gtk.Application subclass
  music_theory.py           NoteScale, WhiteNote, Clef, Accid, TimeSignature
  key_signature.py          KeySignature with sharp/flat maps + guessing
  midi_file_reader.py       Binary MIDI reader
  midi_event.py             Raw MIDI event
  midi_note.py              Parsed MIDI note
  midi_track.py             MIDI track with note list + lyrics
  midi_file.py              Top-level parser + ChangeMidiNotes + splitting
  midi_options.py           Sheet + sound option container
  sheet_constants.py        Per-note-size drawing constants
  symbols.py                MusicSymbol base + BarSymbol, BlankSymbol,
                            ClefSymbol, TimeSigSymbol, AccidSymbol,
                            RestSymbol, LyricSymbol
  stem.py                   Stem with vertical line, flags, and beams
  chord_symbol.py           ChordSymbol + NoteData + beam creation
  clef_measures.py          Per-measure treble/bass clef decision
  symbol_widths.py          Cross-track width alignment
  staff.py                  Single staff row: draw + shade
  sheet_music.py            Top-level layout engine
  piano.py                  Keyboard renderer (toolkit-agnostic)
  audio_player.py           FluidSynth playback backend
  resources/                Clef + time signature PNGs from the original
  widgets/                  GTK4 DrawingArea wrappers
    sheet_music_widget.py
    piano_widget.py
    player_widget.py
    window.py               ApplicationWindow with menu bar + layout
MidiSheetMusic-2.6-linux-src.tar.gz   Original C# source (reference)
Bach__Invention_No._13.mid  Sample MIDI for smoke tests
Bach__Musette_in_D_major.mid
```

## Credits

The sheet music engraving algorithms, layout math, and visual design are all
from Madhav Vaidyanathan's MidiSheetMusic 2.6, licensed under GPLv2. This port
preserves that license.
