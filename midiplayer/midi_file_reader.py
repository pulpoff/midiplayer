"""Low-level binary MIDI file reader.

Direct port of MidiFileReader.cs.
"""

from __future__ import annotations

import os


class MidiFileException(Exception):
    """Raised when a MIDI file cannot be parsed."""

    def __init__(self, message: str, offset: int = 0):
        super().__init__(f"{message} (offset {offset})")
        self.offset = offset


class MidiFileReader:
    """A big-endian byte reader over a whole MIDI file loaded in memory."""

    def __init__(self, source):
        if isinstance(source, (bytes, bytearray)):
            self._data = bytes(source)
        else:
            # Treat as a filename
            if not os.path.exists(source):
                raise MidiFileException(f"File {source} does not exist", 0)
            with open(source, "rb") as fh:
                self._data = fh.read()
            if not self._data:
                raise MidiFileException(f"File {source} is empty (0 bytes)", 0)
        self._offset = 0

    def _check_read(self, amount: int) -> None:
        if self._offset + amount > len(self._data):
            raise MidiFileException("File is truncated", self._offset)

    def peek(self) -> int:
        self._check_read(1)
        return self._data[self._offset]

    def read_byte(self) -> int:
        self._check_read(1)
        value = self._data[self._offset]
        self._offset += 1
        return value

    def read_bytes(self, amount: int) -> bytes:
        self._check_read(amount)
        value = self._data[self._offset : self._offset + amount]
        self._offset += amount
        return value

    def read_short(self) -> int:
        self._check_read(2)
        value = (self._data[self._offset] << 8) | self._data[self._offset + 1]
        self._offset += 2
        return value

    def read_int(self) -> int:
        self._check_read(4)
        b0, b1, b2, b3 = self._data[self._offset : self._offset + 4]
        self._offset += 4
        return (b0 << 24) | (b1 << 16) | (b2 << 8) | b3

    def read_ascii(self, length: int) -> str:
        self._check_read(length)
        value = self._data[self._offset : self._offset + length].decode(
            "ascii", errors="replace"
        )
        self._offset += length
        return value

    def read_varlen(self) -> int:
        """Read a MIDI variable-length integer (1-4 bytes)."""
        result = 0
        b = self.read_byte()
        result = b & 0x7F
        for _ in range(3):
            if b & 0x80:
                b = self.read_byte()
                result = (result << 7) + (b & 0x7F)
            else:
                break
        return result

    def skip(self, amount: int) -> None:
        self._check_read(amount)
        self._offset += amount

    def get_offset(self) -> int:
        return self._offset

    def get_data(self) -> bytes:
        return self._data
