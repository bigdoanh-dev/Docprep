"""How many model calls may run at once, and the line in front of them.

A turn that needs the model takes a slot for as long as the call and its check last. When every slot
is taken it waits in line, first come first served, and is told its place each time it changes: that
is the "Đang xếp hàng" the learner sees, with the real position. One process, in memory: a queue
across several server instances belongs to the chat core.
"""
import threading
import time
from typing import Iterator


class QueueTimeout(Exception):
    """The wait for a slot lasted longer than allowed."""


class QueueFull(QueueTimeout):
    """The line was already as long as allowed: the caller is turned away at once."""


class ModelSlots:
    def __init__(self, limit: int):
        self._limit = limit
        self._in_use = 0
        self._line: list[object] = []
        self._changed = threading.Condition()

    def acquire(self, timeout_s: float, poll_s: float = 0.25, max_waiting: int | None = None) -> Iterator[int]:
        """Take a slot. Yields nothing when one is free. Otherwise yields the caller's place in line
        (1 = next) when it starts to wait and each time the place changes, and ends when the caller
        holds a slot. Raises QueueTimeout after `timeout_s`, and QueueFull at once when `max_waiting`
        callers are already in line (each one waiting holds a server thread). A caller that stops
        iterating, or times out, leaves the line. The caller must `release()` the slot it was given."""
        ticket = object()
        deadline = time.monotonic() + timeout_s
        with self._changed:
            if not self._line and self._in_use < self._limit:
                self._in_use += 1
                return
            if max_waiting is not None and len(self._line) >= max_waiting:
                raise QueueFull()
            self._line.append(ticket)
        said = None
        try:
            while True:
                with self._changed:
                    place = self._line.index(ticket) + 1
                    if place == 1 and self._in_use < self._limit:
                        self._line.remove(ticket)
                        self._in_use += 1
                        self._changed.notify_all()      # the one behind is now first
                        return
                    if place == said:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise QueueTimeout()
                        self._changed.wait(min(poll_s, remaining))
                        continue
                said = place
                yield place
        finally:
            with self._changed:
                if ticket in self._line:
                    self._line.remove(ticket)
                    self._changed.notify_all()

    def release(self) -> None:
        with self._changed:
            self._in_use = max(0, self._in_use - 1)
            self._changed.notify_all()

    def in_use(self) -> int:
        with self._changed:
            return self._in_use

    def waiting(self) -> int:
        with self._changed:
            return len(self._line)
