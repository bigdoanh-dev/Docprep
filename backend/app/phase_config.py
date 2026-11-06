"""Phase 1 has explicit, independent runtime configuration. No implicit external provider."""
from dataclasses import dataclass
import os
import re
from app.config import require_dev_env


def integer(name, default, minimum=1):
    value = int(os.environ.get(name, default))
    if value < minimum:
        raise RuntimeError(f"{name} must be >= {minimum}")
    return value


@dataclass(frozen=True)
class PhaseConfig:
    redis_url: str
    namespace: str
    provider: str
    pool_max: int
    active: int
    waiting: int
    queue_s: int
    turn_s: int
    lease_s: int
    event_ttl_s: int
    model_limit: int

    @classmethod
    def load(cls):
        provider = os.environ.get("PHASE_MODEL_PROVIDER", "disabled")
        if provider not in ("disabled", "scripted", "ollama"):
            raise RuntimeError("Phase 1 model protocol is unapproved; use disabled, scripted or dev/test ollama")
        if provider in ("scripted", "ollama"):
            require_dev_env("PHASE_MODEL_PROVIDER=" + provider)
        namespace = os.environ.get("PHASE_REDIS_NAMESPACE", "docprep:phase1")
        if not re.fullmatch(r"[a-zA-Z0-9:_-]{1,80}", namespace):
            raise RuntimeError("Invalid PHASE_REDIS_NAMESPACE")
        cfg = cls(os.environ.get("REDIS_URL", "redis://127.0.0.1:16379/0"), namespace, provider,
                  integer("PHASE_POOL_MAX", 5), integer("PHASE_ACTIVE_TURNS", 1),
                  integer("PHASE_MAX_WAITING", 20), integer("PHASE_QUEUE_SECONDS", 60),
                  integer("PHASE_TURN_SECONDS", 360), integer("PHASE_LEASE_SECONDS", 15, 3),
                  integer("PHASE_EVENT_TTL_SECONDS", 3600), integer("PHASE_MODEL_SLOTS", 1))
        if cfg.turn_s <= cfg.queue_s:
            raise RuntimeError("PHASE_TURN_SECONDS must exceed PHASE_QUEUE_SECONDS")
        return cfg
