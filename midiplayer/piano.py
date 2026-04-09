"""Port of Piano.cs.

The Piano panel is a 7-octave keyboard rendered with Cairo. It has two
responsibilities:

1. Draw itself once — realistic-looking black and white keys with the
   distinctive dark border frame visible in the original screenshot.
2. Shade notes during playback, using one brush for single-track songs
   and two brushes (right hand / left hand) for two-track piano songs.

The drawing math is a straight port of the C# source. Integer pixel
arithmetic is preserved so the pixel-perfect look of the original is
reproduced.
"""

from __future__ import annotations

from typing import List, Optional

from .midi_file import MidiFile
from .midi_note import MidiNote
from .midi_options import MidiOptions


class Piano:
    """Piano keyboard renderer. Toolkit-agnostic; called from a GTK wrapper."""

    KEYS_PER_OCTAVE = 7
    MAX_OCTAVE = 7

    # Colours from the C# Piano.cs (RGB 0-255)
    GRAY1 = (16, 16, 16)
    GRAY2 = (90, 90, 90)
    GRAY3 = (200, 200, 200)
    SHADE1 = (210, 205, 220)  # default right-hand / single-track highlight
    SHADE2 = (150, 200, 220)  # default left-hand highlight

    def __init__(self, base_key_width: int = 14):
        """Create a new Piano with the given unit white-key width.

        The C# version reads the screen width to pick the key size; the
        GTK4 widget passes it in so the piano scales with the window.
        """
        self.set_key_width(base_key_width)

        # Playback state
        self.notes: List[MidiNote] = []
        self.use_two_colors = False
        self.max_shade_duration = 0
        self.show_note_letters = MidiOptions.NoteNameNone
        self.shade_color = Piano.SHADE1
        self.shade2_color = Piano.SHADE2

    # ----------------------------------------------------------------------

    def set_key_width(self, white_key_width: int) -> None:
        if white_key_width % 2 != 0:
            white_key_width -= 1
        self.white_key_width = white_key_width
        self.white_key_height = white_key_width * 5
        self.black_key_width = white_key_width // 2
        self.black_key_height = self.white_key_height * 5 // 9
        self.margin = 0
        self.black_border = white_key_width // 2

        self.width = (
            self.margin * 2
            + self.black_border * 2
            + self.white_key_width * Piano.KEYS_PER_OCTAVE * Piano.MAX_OCTAVE
        )
        self.height = (
            self.margin * 2 + self.black_border * 3 + self.white_key_height
        )

        bkw = self.black_key_width
        wkw = self.white_key_width
        self.black_key_offsets = [
            wkw - bkw // 2 - 1,
            wkw + bkw // 2 - 1,
            2 * wkw - bkw // 2,
            2 * wkw + bkw // 2,
            4 * wkw - bkw // 2 - 1,
            4 * wkw + bkw // 2 - 1,
            5 * wkw - bkw // 2,
            5 * wkw + bkw // 2,
            6 * wkw - bkw // 2,
            6 * wkw + bkw // 2,
        ]

    def set_midi_file(
        self, midifile: Optional[MidiFile], options: Optional[MidiOptions]
    ) -> None:
        if midifile is None:
            self.notes = []
            self.use_two_colors = False
            return

        tracks = midifile.change_midi_notes(options)
        single = MidiFile.combine_to_single_track(tracks)
        self.notes = single.Notes
        self.max_shade_duration = midifile.Time.Quarter * 2

        # Remember which track a note came from via its Channel field
        # (so shade_notes can pick between shade1 / shade2 when useTwoColors).
        for tracknum, track in enumerate(tracks):
            for note in track.Notes:
                note.Channel = tracknum
        self.use_two_colors = len(tracks) == 2
        self.show_note_letters = options.showNoteLetters if options else 0

    def set_shade_colors(self, c1: tuple, c2: tuple) -> None:
        self.shade_color = c1
        self.shade2_color = c2

    # ----------------------------------------------------------------------
    # Cairo helpers (scoped to this module to avoid importing symbols.py)
    # ----------------------------------------------------------------------

    @staticmethod
    def _set_rgb(cr, rgb: tuple) -> None:
        r, g, b = rgb
        cr.set_source_rgb(r / 255.0, g / 255.0, b / 255.0)

    @staticmethod
    def _fill_rect(cr, x, y, w, h) -> None:
        cr.rectangle(x, y, w, h)
        cr.fill()

    @staticmethod
    def _draw_line(cr, x1, y1, x2, y2, width: float = 1) -> None:
        cr.set_line_width(width)
        cr.move_to(x1 + 0.5, y1 + 0.5)
        cr.line_to(x2 + 0.5, y2 + 0.5)
        cr.stroke()

    # ----------------------------------------------------------------------
    # Drawing
    # ----------------------------------------------------------------------

    def draw(self, cr) -> None:
        # Background of the whole piano area (light gray under everything)
        cr.save()
        cr.set_source_rgb(0.827, 0.827, 0.827)  # D3D3D3 = LightGray
        cr.rectangle(0, 0, self.width, self.height)
        cr.fill()
        cr.restore()

        # White key fill + black keys + outlines, inside the border frame
        cr.save()
        cr.translate(self.margin + self.black_border, self.margin + self.black_border)

        cr.set_source_rgb(1, 1, 1)
        cr.rectangle(
            0, 0,
            self.white_key_width * Piano.KEYS_PER_OCTAVE * Piano.MAX_OCTAVE,
            self.white_key_height,
        )
        cr.fill()

        self._draw_black_keys(cr)
        self._draw_outline(cr)
        cr.restore()

        self._draw_black_border(cr)

    def _draw_octave_outline(self, cr) -> None:
        right = self.white_key_width * Piano.KEYS_PER_OCTAVE

        Piano._set_rgb(cr, Piano.GRAY1)
        Piano._draw_line(cr, 0, 0, 0, self.white_key_height)
        Piano._draw_line(cr, right, 0, right, self.white_key_height)
        Piano._draw_line(cr, 0, self.white_key_height, right, self.white_key_height)
        Piano._set_rgb(cr, Piano.GRAY3)
        Piano._draw_line(cr, right - 1, 0, right - 1, self.white_key_height)
        Piano._draw_line(cr, 1, 0, 1, self.white_key_height)

        # Line between E and F
        Piano._set_rgb(cr, Piano.GRAY1)
        Piano._draw_line(
            cr,
            3 * self.white_key_width, 0,
            3 * self.white_key_width, self.white_key_height,
        )
        Piano._set_rgb(cr, Piano.GRAY3)
        Piano._draw_line(
            cr,
            3 * self.white_key_width - 1, 0,
            3 * self.white_key_width - 1, self.white_key_height,
        )
        Piano._draw_line(
            cr,
            3 * self.white_key_width + 1, 0,
            3 * self.white_key_width + 1, self.white_key_height,
        )

        # Outlines around the black keys
        bkh = self.black_key_height
        for i in range(0, 10, 2):
            x1 = self.black_key_offsets[i]
            x2 = self.black_key_offsets[i + 1]

            Piano._set_rgb(cr, Piano.GRAY1)
            Piano._draw_line(cr, x1, 0, x1, bkh)
            Piano._draw_line(cr, x2, 0, x2, bkh)
            Piano._draw_line(cr, x1, bkh, x2, bkh)

            Piano._set_rgb(cr, Piano.GRAY2)
            Piano._draw_line(cr, x1 - 1, 0, x1 - 1, bkh + 1)
            Piano._draw_line(cr, x2 + 1, 0, x2 + 1, bkh + 1)
            Piano._draw_line(cr, x1 - 1, bkh + 1, x2 + 1, bkh + 1)

            Piano._set_rgb(cr, Piano.GRAY3)
            Piano._draw_line(cr, x1 - 2, 0, x1 - 2, bkh + 2)
            Piano._draw_line(cr, x2 + 2, 0, x2 + 2, bkh + 2)
            Piano._draw_line(cr, x1 - 2, bkh + 2, x2 + 2, bkh + 2)

        # Lines between the bottom halves of the white keys
        for i in range(1, Piano.KEYS_PER_OCTAVE):
            if i == 3:
                continue  # handled above (E/F)
            Piano._set_rgb(cr, Piano.GRAY1)
            Piano._draw_line(
                cr,
                i * self.white_key_width, bkh,
                i * self.white_key_width, self.white_key_height,
            )
            Piano._set_rgb(cr, Piano.GRAY2)
            Piano._draw_line(
                cr,
                i * self.white_key_width - 1, bkh + 1,
                i * self.white_key_width - 1, self.white_key_height,
            )
            Piano._set_rgb(cr, Piano.GRAY3)
            Piano._draw_line(
                cr,
                i * self.white_key_width + 1, bkh + 1,
                i * self.white_key_width + 1, self.white_key_height,
            )

    def _draw_outline(self, cr) -> None:
        for octave in range(Piano.MAX_OCTAVE):
            cr.save()
            cr.translate(octave * self.white_key_width * Piano.KEYS_PER_OCTAVE, 0)
            self._draw_octave_outline(cr)
            cr.restore()

    def _draw_black_keys(self, cr) -> None:
        for octave in range(Piano.MAX_OCTAVE):
            cr.save()
            cr.translate(octave * self.white_key_width * Piano.KEYS_PER_OCTAVE, 0)
            for i in range(0, 10, 2):
                x1 = self.black_key_offsets[i]
                Piano._set_rgb(cr, Piano.GRAY1)
                Piano._fill_rect(cr, x1, 0, self.black_key_width, self.black_key_height)
                Piano._set_rgb(cr, Piano.GRAY2)
                Piano._fill_rect(
                    cr,
                    x1 + 1,
                    self.black_key_height - self.black_key_height // 8,
                    self.black_key_width - 2,
                    self.black_key_height // 8,
                )
            cr.restore()

    def _draw_black_border(self, cr) -> None:
        piano_width = self.white_key_width * Piano.KEYS_PER_OCTAVE * Piano.MAX_OCTAVE

        Piano._set_rgb(cr, Piano.GRAY1)
        Piano._fill_rect(
            cr,
            self.margin, self.margin,
            piano_width + self.black_border * 2, self.black_border - 2,
        )
        Piano._fill_rect(
            cr,
            self.margin, self.margin,
            self.black_border, self.white_key_height + self.black_border * 3,
        )
        Piano._fill_rect(
            cr,
            self.margin,
            self.margin + self.black_border + self.white_key_height,
            self.black_border * 2 + piano_width,
            self.black_border * 2,
        )
        Piano._fill_rect(
            cr,
            self.margin + self.black_border + piano_width, self.margin,
            self.black_border, self.white_key_height + self.black_border * 3,
        )

        Piano._set_rgb(cr, Piano.GRAY2)
        Piano._draw_line(
            cr,
            self.margin + self.black_border, self.margin + self.black_border - 1,
            self.margin + self.black_border + piano_width,
            self.margin + self.black_border - 1,
        )

        # Gray bottom of each white key
        cr.save()
        cr.translate(self.margin + self.black_border, self.margin + self.black_border)
        Piano._set_rgb(cr, Piano.GRAY2)
        for i in range(Piano.KEYS_PER_OCTAVE * Piano.MAX_OCTAVE):
            Piano._fill_rect(
                cr,
                i * self.white_key_width + 1, self.white_key_height + 2,
                self.white_key_width - 2, self.black_border // 2,
            )
        cr.restore()

    # ----------------------------------------------------------------------
    # Shading
    # ----------------------------------------------------------------------

    def shade_notes(self, cr, current_pulse: int, prev_pulse: int) -> None:
        """Shade notes at ``current_pulse`` and un-shade at ``prev_pulse``."""
        if not self.notes:
            return

        cr.save()
        cr.translate(self.margin + self.black_border, self.margin + self.black_border)

        last_shaded = self._find_closest_start_time(prev_pulse - self.max_shade_duration * 2)
        for i in range(last_shaded, len(self.notes)):
            start = self.notes[i].StartTime
            end = self.notes[i].EndTime
            notenumber = self.notes[i].Number
            next_start = self._next_start_time(i)
            next_start_track = self._next_start_time_same_track(i)
            end = max(end, next_start_track)
            end = min(end, start + self.max_shade_duration - 1)

            if start > prev_pulse and start > current_pulse:
                break

            if (
                start <= current_pulse < next_start
                and current_pulse < end
                and start <= prev_pulse < next_start
                and prev_pulse < end
            ):
                break

            # Note sounds at the current pulse — shade it
            if start <= current_pulse < end:
                if self.use_two_colors and self.notes[i].Channel == 1:
                    color = self.shade2_color
                else:
                    color = self.shade_color
                self._shade_one_note(cr, notenumber, color)
            # Note sounded at the previous pulse — erase its shade
            elif start <= prev_pulse < end:
                num = notenumber % 12
                if num in (1, 3, 6, 8, 10):
                    self._shade_one_note(cr, notenumber, Piano.GRAY1)
                else:
                    self._shade_one_note(cr, notenumber, (255, 255, 255))

        cr.restore()

    def _find_closest_start_time(self, pulse_time: int) -> int:
        if not self.notes:
            return 0
        left = 0
        right = len(self.notes) - 1
        while right - left > 1:
            i = (right + left) // 2
            if self.notes[left].StartTime == pulse_time:
                break
            elif self.notes[i].StartTime <= pulse_time:
                left = i
            else:
                right = i
        while left >= 1 and self.notes[left - 1].StartTime == self.notes[left].StartTime:
            left -= 1
        return left

    def _next_start_time(self, i: int) -> int:
        start = self.notes[i].StartTime
        end = self.notes[i].EndTime
        while i < len(self.notes):
            if self.notes[i].StartTime > start:
                return self.notes[i].StartTime
            end = max(end, self.notes[i].EndTime)
            i += 1
        return end

    def _next_start_time_same_track(self, i: int) -> int:
        start = self.notes[i].StartTime
        end = self.notes[i].EndTime
        track = self.notes[i].Channel
        while i < len(self.notes):
            if self.notes[i].Channel != track:
                i += 1
                continue
            if self.notes[i].StartTime > start:
                return self.notes[i].StartTime
            end = max(end, self.notes[i].EndTime)
            i += 1
        return end

    def _shade_one_note(self, cr, notenumber: int, color: tuple) -> None:
        """Fill the region for a single piano key with ``color``.

        Only notes from 24 to 96 are drawn (the 7 visible octaves).
        """
        octave = notenumber // 12
        notescale = notenumber % 12
        octave -= 2
        if octave < 0 or octave >= Piano.MAX_OCTAVE:
            return

        cr.save()
        cr.translate(octave * self.white_key_width * Piano.KEYS_PER_OCTAVE, 0)
        Piano._set_rgb(cr, color)

        wkw = self.white_key_width
        bkw = self.black_key_width
        bkh = self.black_key_height
        wkh = self.white_key_height
        bottom_half = wkh - (bkh + 3)
        offs = self.black_key_offsets

        if notescale == 0:      # C
            x1 = 2
            x2 = offs[0] - 2
            Piano._fill_rect(cr, x1, 0, x2 - x1, bkh + 3)
            Piano._fill_rect(cr, x1, bkh + 3, wkw - 3, bottom_half)
        elif notescale == 1:    # C#
            x1 = offs[0]
            x2 = offs[1]
            Piano._fill_rect(cr, x1, 0, x2 - x1, bkh)
            if color == Piano.GRAY1:
                Piano._set_rgb(cr, Piano.GRAY2)
                Piano._fill_rect(cr, x1 + 1, bkh - bkh // 8, bkw - 2, bkh // 8)
        elif notescale == 2:    # D
            x1 = wkw + 2
            x2 = offs[1] + 3
            x3 = offs[2] - 2
            Piano._fill_rect(cr, x2, 0, x3 - x2, bkh + 3)
            Piano._fill_rect(cr, x1, bkh + 3, wkw - 3, bottom_half)
        elif notescale == 3:    # D#
            x1 = offs[2]
            Piano._fill_rect(cr, x1, 0, bkw, bkh)
            if color == Piano.GRAY1:
                Piano._set_rgb(cr, Piano.GRAY2)
                Piano._fill_rect(cr, x1 + 1, bkh - bkh // 8, bkw - 2, bkh // 8)
        elif notescale == 4:    # E
            x1 = wkw * 2 + 2
            x2 = offs[3] + 3
            x3 = wkw * 3 - 1
            Piano._fill_rect(cr, x2, 0, x3 - x2, bkh + 3)
            Piano._fill_rect(cr, x1, bkh + 3, wkw - 3, bottom_half)
        elif notescale == 5:    # F
            x1 = wkw * 3 + 2
            x2 = offs[4] - 2
            Piano._fill_rect(cr, x1, 0, x2 - x1, bkh + 3)
            Piano._fill_rect(cr, x1, bkh + 3, wkw - 3, bottom_half)
        elif notescale == 6:    # F#
            x1 = offs[4]
            Piano._fill_rect(cr, x1, 0, bkw, bkh)
            if color == Piano.GRAY1:
                Piano._set_rgb(cr, Piano.GRAY2)
                Piano._fill_rect(cr, x1 + 1, bkh - bkh // 8, bkw - 2, bkh // 8)
        elif notescale == 7:    # G
            x1 = wkw * 4 + 2
            x2 = offs[5] + 3
            x3 = offs[6] - 2
            Piano._fill_rect(cr, x2, 0, x3 - x2, bkh + 3)
            Piano._fill_rect(cr, x1, bkh + 3, wkw - 3, bottom_half)
        elif notescale == 8:    # G#
            x1 = offs[6]
            Piano._fill_rect(cr, x1, 0, bkw, bkh)
            if color == Piano.GRAY1:
                Piano._set_rgb(cr, Piano.GRAY2)
                Piano._fill_rect(cr, x1 + 1, bkh - bkh // 8, bkw - 2, bkh // 8)
        elif notescale == 9:    # A
            x1 = wkw * 5 + 2
            x2 = offs[7] + 3
            x3 = offs[8] - 2
            Piano._fill_rect(cr, x2, 0, x3 - x2, bkh + 3)
            Piano._fill_rect(cr, x1, bkh + 3, wkw - 3, bottom_half)
        elif notescale == 10:   # A#
            x1 = offs[8]
            Piano._fill_rect(cr, x1, 0, bkw, bkh)
            if color == Piano.GRAY1:
                Piano._set_rgb(cr, Piano.GRAY2)
                Piano._fill_rect(cr, x1 + 1, bkh - bkh // 8, bkw - 2, bkh // 8)
        elif notescale == 11:   # B
            x1 = wkw * 6 + 2
            x2 = offs[9] + 3
            x3 = wkw * Piano.KEYS_PER_OCTAVE - 1
            Piano._fill_rect(cr, x2, 0, x3 - x2, bkh + 3)
            Piano._fill_rect(cr, x1, bkh + 3, wkw - 3, bottom_half)

        cr.restore()
