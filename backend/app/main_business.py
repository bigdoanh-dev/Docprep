"""Independent Business API; does not instantiate a gateway or AI worker."""
from app.application import create_app as factory


def create_app(mode=None, database_url=None):
    return factory(mode, database_url, service="business")


app = create_app()
