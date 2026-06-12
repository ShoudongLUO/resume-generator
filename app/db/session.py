from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


# Env var names that may hold a Postgres URL, in priority order. Hosting
# providers inject the connection string under different names: a plain Neon
# setup uses DATABASE_URL; the Vercel Postgres / Neon integration may instead
# inject POSTGRES_URL (pooled) and *_NON_POOLING / *_UNPOOLED variants. We do
# NOT read POSTGRES_PRISMA_URL — it carries pgbouncer query params psycopg
# cannot parse.
_DB_URL_ENV_NAMES = (
    "DATABASE_URL",
    "POSTGRES_URL",
    "POSTGRES_URL_NON_POOLING",
    "DATABASE_URL_UNPOOLED",
)


def _resolve_url(explicit: str | None = None) -> str:
    if explicit:
        return explicit
    for name in _DB_URL_ENV_NAMES:
        value = os.getenv(name)
        if value:
            return value
    return "sqlite:///./data.db"


def _normalize_url(url: str) -> str:
    if url.startswith("postgresql+"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    return url


def make_engine(url: str | None = None):
    url = _normalize_url(_resolve_url(url))
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(url, connect_args=connect_args, future=True, pool_pre_ping=True)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
