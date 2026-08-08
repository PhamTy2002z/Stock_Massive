"""Auth domain module.

Deliberately re-exports only models: Alembic imports this package to register
metadata, and pulling the router in here would drag FastAPI wiring into
migrations.
"""

from .models import RefreshToken, User

__all__ = ["RefreshToken", "User"]
