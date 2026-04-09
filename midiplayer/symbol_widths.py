"""Port of SymbolWidths.cs.

Tracks per-track symbol widths per start time so that staves in different
tracks can be vertically aligned.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .symbols import BarSymbol, LyricSymbol, MusicSymbol


class SymbolWidths:
    def __init__(
        self,
        tracks: List[List[MusicSymbol]],
        tracklyrics: Optional[List[Optional[List[LyricSymbol]]]] = None,
    ):
        # Per-track: starttime -> summed width for all symbols at that time
        self._widths: List[Dict[int, int]] = [
            SymbolWidths._track_widths(syms) for syms in tracks
        ]

        # Maximum width per starttime across all tracks
        self._maxwidths: Dict[int, int] = {}
        for d in self._widths:
            for t, w in d.items():
                if t not in self._maxwidths or self._maxwidths[t] < w:
                    self._maxwidths[t] = w

        if tracklyrics is not None:
            for lyrics in tracklyrics:
                if lyrics is None:
                    continue
                for lyric in lyrics:
                    width = lyric.MinWidth
                    time = lyric.StartTime
                    if (
                        time not in self._maxwidths
                        or self._maxwidths[time] < width
                    ):
                        self._maxwidths[time] = width

        self._starttimes = sorted(self._maxwidths.keys())

    @staticmethod
    def _track_widths(symbols: List[MusicSymbol]) -> Dict[int, int]:
        widths: Dict[int, int] = {}
        for m in symbols:
            if isinstance(m, BarSymbol):
                continue
            start = m.StartTime
            w = m.MinWidth
            widths[start] = widths.get(start, 0) + w
        return widths

    def get_extra_width(self, track: int, start: int) -> int:
        if start not in self._widths[track]:
            return self._maxwidths[start]
        return self._maxwidths[start] - self._widths[track][start]

    GetExtraWidth = get_extra_width

    @property
    def StartTimes(self) -> List[int]:
        return self._starttimes
