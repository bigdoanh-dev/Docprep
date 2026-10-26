"""Configuration: backend/config.yaml for tunables, .env at the repo root for secrets and URLs."""
import os
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")


@lru_cache
def settings() -> dict:
    with open(BACKEND_DIR / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


APP_ENVS = ("dev", "test", "production")


def app_env() -> str:
    """Where the code runs. Demo content, the dev learner and the dev reset are refused in production."""
    value = env("APP_ENV", "dev")
    if value not in APP_ENVS:
        raise RuntimeError(f"APP_ENV must be one of {', '.join(APP_ENVS)}; got {value!r}.")
    return value


def require_dev_env(command: str) -> None:
    """Commands that load demo data or empty tables run only where APP_ENV says dev or test, in so
    many words: a database whose environment forgot to set it is not assumed to be a dev database."""
    value = env("APP_ENV")
    if value not in ("dev", "test"):
        raise RuntimeError(
            f"`{command}` needs APP_ENV=dev or APP_ENV=test set explicitly (in .env or the environment); "
            f"got {value!r}. It is never run against production.")


APP_MODES = ("real", "mock")


def app_mode(value: str | None = None) -> str:
    """"real" serves the database-backed API; "mock" serves the contract's examples and needs no database."""
    mode = value or env("APP_MODE", "real")
    if mode not in APP_MODES:
        raise RuntimeError(f"APP_MODE must be one of {', '.join(APP_MODES)}; got {mode!r}.")
    return mode


def model_provider() -> str:
    """A scripted model must be an explicit local choice, never a production fallback."""
    value = env("MODEL_PROVIDER", "anthropic")
    if value not in ("scripted", "anthropic"):
        raise RuntimeError("MODEL_PROVIDER must be scripted or anthropic")
    if value == "scripted":
        require_dev_env("MODEL_PROVIDER=scripted")
    return value
