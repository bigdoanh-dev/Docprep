"""The model slots and the queue in front of them: first come, first served, with the real place in line."""
import time
from threading import Thread

import pytest

from app.chat.slots import ModelSlots, QueueFull, QueueTimeout


def until(condition, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "condition not met in time"
        time.sleep(0.01)


def test_free_slots_are_taken_without_waiting():
    slots = ModelSlots(2)
    assert list(slots.acquire(1)) == [] and list(slots.acquire(1)) == []
    assert (slots.in_use(), slots.waiting()) == (2, 0)
    slots.release()
    assert slots.in_use() == 1


def test_the_queue_is_first_come_first_served_and_says_the_place():
    slots = ModelSlots(1)
    list(slots.acquire(1))
    seen = {"a": [], "b": []}

    def wait(name):
        for place in slots.acquire(5):
            seen[name].append(place)
        seen[name].append("in")

    a = Thread(target=wait, args=("a",))
    a.start()
    until(lambda: slots.waiting() == 1)
    b = Thread(target=wait, args=("b",))
    b.start()
    until(lambda: slots.waiting() == 2 and seen["b"] == [2])
    assert seen["a"] == [1]
    slots.release()
    a.join(10)
    assert seen["a"] == [1, "in"]
    until(lambda: seen["b"] == [2, 1])                    # b moved up, and is still waiting
    slots.release()
    b.join(10)
    assert seen["b"] == [2, 1, "in"] and (slots.waiting(), slots.in_use()) == (0, 1)


def test_a_wait_that_is_too_long_gives_up_and_leaves_the_line():
    slots = ModelSlots(1)
    list(slots.acquire(1))
    started = time.monotonic()
    with pytest.raises(QueueTimeout):
        list(slots.acquire(0.3))
    assert 0.25 <= time.monotonic() - started < 10 and (slots.waiting(), slots.in_use()) == (0, 1)
    slots.release()
    assert list(slots.acquire(1)) == []                   # the slot goes to the next caller, not to the one who left


def test_a_slot_is_released_when_the_caller_fails():
    slots = ModelSlots(1)

    def work():
        for _ in slots.acquire(1):
            yield "queued"
        try:
            yield "working"
            raise RuntimeError("the model step broke")
        finally:
            slots.release()

    with pytest.raises(RuntimeError):
        list(work())
    assert slots.in_use() == 0 and list(slots.acquire(1)) == []


def test_a_caller_that_stops_waiting_is_taken_out_of_the_line():
    slots = ModelSlots(1)
    list(slots.acquire(1))
    waiting = slots.acquire(5)
    assert next(waiting) == 1 and slots.waiting() == 1
    waiting.close()                                       # the stream was dropped while queued
    assert slots.waiting() == 0
    slots.release()
    assert slots.in_use() == 0


def test_a_full_line_turns_the_next_caller_away_at_once():
    slots = ModelSlots(1)
    list(slots.acquire(1))
    first = slots.acquire(5, max_waiting=1)
    assert next(first) == 1                                # one waits: the line is full
    started = time.monotonic()
    with pytest.raises(QueueFull):
        list(slots.acquire(5, max_waiting=1))
    assert time.monotonic() - started < 1 and slots.waiting() == 1
    assert issubclass(QueueFull, QueueTimeout)             # handled as the system being busy
    first.close()
    assert list(ModelSlots(1).acquire(5, max_waiting=0)) == []     # a free slot needs no place in line
