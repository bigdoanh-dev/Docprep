"""Independent Chat Orchestrator."""
from app.application import create_app as factory


def create_app(mode=None, database_url=None):
    return factory(mode, database_url, service="chat")


app = create_app()
