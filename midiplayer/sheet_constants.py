"""Sheet music drawing constants.

The original SheetMusic.cs keeps these as static fields that are recomputed
whenever `SetNoteSize(largenotes)` is called. We keep the same model: a
module-level mutable state that symbol classes read when drawing.
"""

from __future__ import annotations


# Fixed constants matching SheetMusic.cs
LineWidth = 1
LeftMargin = 4
TitleHeight = 14
PageWidth = 800
PageHeight = 1050

# Set by set_note_size()
LineSpace: int = 5
StaffHeight: int = 0
NoteHeight: int = 0
NoteWidth: int = 0


def set_note_size(largenotes: bool) -> None:
    """Recompute the per-note-size drawing constants.

    Mirrors ``SheetMusic.SetNoteSize`` in the C# source. ``LineSpace`` is the
    pixel gap between staff lines; everything else is derived from it.
    """
    global LineSpace, StaffHeight, NoteHeight, NoteWidth

    LineSpace = 7 if largenotes else 5
    StaffHeight = LineSpace * 4 + LineWidth * 5
    NoteHeight = LineSpace + LineWidth
    NoteWidth = 3 * LineSpace // 2


# Initialise to the default (small) size
set_note_size(False)
