import json

from fastapi.responses import StreamingResponse


class EventStreamResponse(StreamingResponse):
    """Declared as a route's response_class so the contract shows text/event-stream and nothing else."""
    media_type = "text/event-stream"


def format_sse(event: str, data: dict, event_id: str | None = None) -> str:
    """One server-sent event, Vietnamese text left readable."""
    prefix = f"id: {event_id}\n" if event_id else ""
    return prefix + f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, separators=(',', ':'))}\n\n"
