"""ASGI entrypoint module for Uvicorn.

This small wrapper exists so we can run the FastAPI app from `app.py`
without conflicting with the `app/` package directory.
"""

from app import app  # FastAPI instance defined in app.py

__all__ = ["app"]


