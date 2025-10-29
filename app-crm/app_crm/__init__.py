"""
CRM service package.

The package exposes `create_app()` for FastAPI runners.
"""

from .api import create_app

__all__ = ["create_app"]
