"""Compatibility entrypoint for the single-process Alpha runtime."""
from app.application import create_app

app = create_app()
