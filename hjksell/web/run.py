"""Import target used by the local uvicorn development command."""

from .app import create_app

app = create_app()
