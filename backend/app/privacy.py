"""Deterministic minimisation, not a claim of complete natural-language PII detection."""
import re
from app.gateway import GatewayError

PATTERNS = (
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    re.compile(r"(?<!\w)(?:\+?84|0)(?:[ .-]?\d){9,10}(?!\w)"),
    re.compile(r"\b(?:\d{12}|\d{9})\b"),
    re.compile(r"\b(?:at|rt)_[A-Za-z0-9_-]+\b"),
    re.compile(r"\bHV-[A-Za-z0-9-]+\b", re.I),
    re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I),
    re.compile(r"Bearer\s+\S+", re.I),
)


def clean(text: str) -> str:
    for pattern in PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


def clean_tree(value):
    if isinstance(value, str):
        return clean(value)
    if isinstance(value, dict):
        return {k: clean_tree(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_tree(v) for v in value]
    return value


def validate_prompt(system, messages):
    if any(set(message) - {"role", "content"} or
           message.get("role") not in ("user", "assistant") or
           not isinstance(message.get("content"), str) for message in messages):
        raise GatewayError("prompt_metadata_blocked")
    if clean(system) != system or clean_tree(messages) != messages:
        raise GatewayError("prompt_identifiers_blocked")
