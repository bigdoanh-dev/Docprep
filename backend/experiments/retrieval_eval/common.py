"""Shared pieces of the retrieval evaluation: the model, the two retrieval paths, JSON calls."""
import os
import random
import time

from app.chat.normalise import normalise
from app.chat.pipeline import parse_model_json
from app.chat.retrieval import find
from app.config import settings
from app.ollama_gateway import OllamaConfig
from app.repo import content, corpus, embeddings


def gateway():
    """Claude through the project's own gateway (identifier check included). Model from YHDP_ANTHROPIC_MODEL."""
    from app.anthropic_gateway import AnthropicConfig, HostedGateway
    return HostedGateway(OllamaConfig.load(), AnthropicConfig.load())


def ask_json(gw, system: str, user: str, version: str, tries: int = 3) -> dict | None:
    """One JSON reply; retried on a malformed reply or a refused call (rate limits)."""
    for attempt in range(tries):
        try:
            data = parse_model_json(gw.complete("check", system, [{"role": "user", "content": user}], version).text)
            if data is not None:
                return data
        except Exception as e:  # noqa: BLE001 - logged and retried; an eval run must not die on one call
            print("model call failed:", type(e).__name__, e)
            time.sleep(2 * (attempt + 1))
    return None


def active_version(conn) -> str:
    return corpus.selected(conn)


def hybrid(conn, gw, text: str, limit: int = 30):
    """The chat worker's retrieval for a real provider (bge-m3 + full text, RRF), best `limit`."""
    return embeddings.search(conn, normalise(text, content.glossary(conn)), gw.embed([text]),
                             active_version(conn), limit=limit).passages


def keyword(conn, text: str, limit: int = 30, min_score: float | None = None):
    """The keyword-only path (used when no model is configured), with its threshold unless told otherwise."""
    cfg = settings()["retrieval"]
    return find(conn, normalise(text, content.glossary(conn)), limit,
                cfg["min_score"] if min_score is None else min_score).passages


def visible_passages(conn) -> list[dict]:
    corpus.scope(conn, active_version(conn))
    return conn.execute(
        """select p.id, d.title as document, p.chapter, p.section, p.context, p.text, p.competency_code
           from passage p join document d on d.id = p.document_id
           where not d.is_synthetic and corpus_passage_visible(p.id) order by p.id""").fetchall()


def seeded(seed: int = 20261122) -> random.Random:
    return random.Random(int(os.environ.get("EVAL_SEED", seed)))
