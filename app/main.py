from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.db.init import init_db
from app.routes import auth, generate, llm_config, profile, runs

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Best-effort table creation. If the database is unreachable/misconfigured we
    # log it but still let the app start, so the SPA loads and a clear error
    # surfaces per-request instead of every route returning an opaque 500
    # ("Application startup failed").
    try:
        init_db()
    except Exception:  # noqa: BLE001
        logger.exception("init_db() failed at startup; continuing without table init")
    yield


app = FastAPI(title="Resume Generator", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(llm_config.router)
app.include_router(profile.router)
app.include_router(generate.router)
app.include_router(runs.router)

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@app.get("/")
def index() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=_STATIC_DIR, check_dir=False), name="static")
