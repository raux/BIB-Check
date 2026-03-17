"""In-memory log handler that captures backend log messages for the UI."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone

from backend.models.schemas import LogEntry


class MemoryLogHandler(logging.Handler):
    """A logging handler that stores log records in an in-memory buffer.

    The buffer is bounded and can be drained (read + clear) so that each
    validation request receives only the logs produced during that request.
    """

    def __init__(self, capacity: int = 500) -> None:
        super().__init__()
        self._capacity = capacity
        self._buffer: list[LogEntry] = []
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        entry = LogEntry(
            level=record.levelname,
            message=self.format(record),
            timestamp=datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
        )
        with self._lock:
            self._buffer.append(entry)
            if len(self._buffer) > self._capacity:
                self._buffer = self._buffer[-self._capacity :]

    def drain(self) -> list[LogEntry]:
        """Return all buffered entries and clear the buffer."""
        with self._lock:
            entries = list(self._buffer)
            self._buffer.clear()
        return entries

    def get_entries(self) -> list[LogEntry]:
        """Return all buffered entries without clearing."""
        with self._lock:
            return list(self._buffer)
