from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.db.init import init_db
from app.routes import auth, generate, llm_config, profile, runs


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
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
