"""What a /v1 route can ask for: a connection, the time, the model gateway, the caller's address."""
from datetime import datetime, timezone
from functools import lru_cache

from fastapi import Depends, Request

from app.config import ROOT_DIR, env, settings


def get_conn(request: Request):
    """A pooled connection for this request: committed when the route returns, rolled back if it raises.
    Mock mode has no database, so it yields nothing."""
    if request.app.state.mode == "mock":
        yield None
        return
    with request.app.state.pool.connection() as conn:
        yield conn


# scope="function" makes the commit happen when the route returns, before the response is sent, so a
# request the client chains straight after always sees the write.
Conn = Depends(get_conn, scope="function")


def get_now() -> datetime:
    return datetime.now(timezone.utc)


Now = Depends(get_now)


@lru_cache
def get_gateway():
    """The one caller of the model. Tests override this dependency with a scripted gateway."""
    from app.config import model_provider
    if model_provider() == "scripted":
        from app.scripted_gateway import ScriptedGateway
        return ScriptedGateway()
    from app.gateway import AnthropicGateway
    return AnthropicGateway(settings()["gateway"], env("ANTHROPIC_API_KEY"), env("DEMO_REPLAY"),
                            ROOT_DIR / ".replay")


Gateway = Depends(get_gateway)


def client_ip(request: Request) -> str:
    """The caller's address, which the sign-in rate limit counts failures by.

    This is the socket peer. Behind a reverse proxy that is the proxy, and every caller would share
    one bucket: run the server with `--forwarded-allow-ips` set to the proxy's own address, so
    X-Forwarded-For from it is honoured. Never `*`: a caller could then forge the header and dodge
    the limit. People behind one NAT (a classroom) share an address and so share the limit.
    """
    return request.client.host if request.client else "unknown"
