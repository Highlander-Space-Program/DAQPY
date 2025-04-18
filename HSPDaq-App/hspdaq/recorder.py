"""
CSV buffering / flushing helper.

Usage
-----
rec = Recorder(csv_path, header)
rec.append(row)   # row is a list matching header length
rec.close()       # flush any remaining rows
"""
from __future__ import annotations
import csv
from pathlib import Path
from typing import List

from hspdaq.constants import BUFFER_LIMIT


class Recorder:
    def __init__(self, file_path: str | Path, header: List[str]) -> None:
        self.file_path = Path(file_path)
        self.buffer: List[List] = []

        # open file & write header immediately
        self._file = self.file_path.open("w", newline="")
        self._writer = csv.writer(self._file)
        self._writer.writerow(header)

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #
    def append(self, row: List) -> None:
        """Add one row; flush when BUFFER_LIMIT is reached."""
        self.buffer.append(row)
        if len(self.buffer) >= BUFFER_LIMIT:
            self._flush()

    def close(self) -> None:
        """Flush remaining rows and close the file handle."""
        if self.buffer:
            self._flush()
        self._file.close()

    # ------------------------------------------------------------------ #
    # internals
    # ------------------------------------------------------------------ #
    def _flush(self) -> None:
        self._writer.writerows(self.buffer)
        self._file.flush()
        self.buffer.clear()
        print(f"Written {BUFFER_LIMIT} rows to {self.file_path.name}")
