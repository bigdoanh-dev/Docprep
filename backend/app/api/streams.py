"""Server-sent events from a generator that needs the database again after the request has ended."""
import logging
import threading
from typing import Callable, ContextManager, Iterator

from fastapi import Request

from app.sse import EventStreamResponse, format_sse

log = logging.getLogger(__name__)

# A connection of the pool for as long as a `with` block lasts: committed when the block ends,
# rolled back if it raises.
Connect = Callable[[], ContextManager]


def sse_from(request: Request, events: Callable[[Connect], Iterator[tuple[str, dict]]]) -> EventStreamResponse:
    """Stream `events(connect)` as server-sent events.

    The request's own connection is committed and handed back when the route returns, before the
    first byte is sent. The generator therefore takes a connection of its own each time it reads or
    writes, with `connect()`, and holds none in between: not while it waits for the model, and not
    while it waits for its turn. If the client goes away the generator is still run to its end, so
    what it stores is kept.
    """
    return EventStreamResponse(stream_events(request.app.state.pool.connection, events),
                               headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def stream_events(connect: Connect, events: Callable[[Connect], Iterator[tuple[str, dict]]]) -> Iterator[str]:
    produced = events(connect)
    try:
        for name, data in produced:
            yield format_sse(name, data)
    except GeneratorExit:
        # The client went away. The turn is finished anyway, unsent: the model call was made and
        # paid for, and the learner who reopens the chat must find the answer, not a lone question.
        # It is finished on a thread of its own: the server closes a dropped stream on its event loop,
        # and the rest of a turn (a wait in line, the model call) must never block that loop.
        threading.Thread(target=_finish, args=(produced,), name="finish-dropped-turn", daemon=True).start()
        raise


def _finish(produced: Iterator) -> None:
    try:
        for _ in produced:
            pass
    except Exception:
        log.exception("finishing a dropped answer stream failed")
