from __future__ import annotations

from app.db.models import Base
from app.db.session import engine


def init_db() -> None:
    """Create all tables if they do not exist (idempotent)."""
    Base.metadata.create_all(bind=engine)
