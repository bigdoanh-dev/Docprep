"""Loaders for the blueprint, the content and development data."""
from pathlib import Path

from app.config import app_env, settings
from seed.blueprint import load_blueprint, validate_blueprint, write_blueprint
from seed.content import CONTENT_DIR, load_content, validate_content, write_content
from seed.dev import ensure_demo_reviewers, ensure_dev_activation_code, ensure_dev_learner


def _checked_blueprint() -> dict:
    blueprint = load_blueprint()
    errors = validate_blueprint(blueprint)
    if errors:
        raise ValueError("invalid blueprint:\n" + "\n".join(errors))
    return blueprint


def run_blueprint(conn) -> None:
    """The blueprint, the provisional competency tree and the eight học phần. Repeatable.

    This is reference data, allowed in every environment: without it no question can be stored.
    """
    write_blueprint(conn, _checked_blueprint(), settings()["blueprint"]["foundation_weight"])
    conn.commit()


def run_seed(conn, content_dir: Path = CONTENT_DIR) -> None:
    """Blueprint, demo content approved by the demo reviewers, and a dev learner. Repeatable.

    Everything is checked before anything is written. Refused in production: the content is demo
    material and its approvals are a fixture, not expert review.
    """
    if app_env() == "production":
        raise RuntimeError("seed is for dev and test: it loads demo content and a dev learner")
    blueprint = _checked_blueprint()
    content = load_content(content_dir)
    errors = validate_content(content, blueprint)
    if errors:
        raise ValueError("invalid seed content:\n" + "\n".join(errors))

    write_blueprint(conn, blueprint, settings()["blueprint"]["foundation_weight"])
    write_content(conn, content, blueprint, ensure_demo_reviewers(conn))
    ensure_dev_activation_code(conn, ensure_dev_learner(conn))
    conn.commit()
