"""PitchVision API. Interactive documentation: /docs (Swagger UI) and /redoc."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import models  # noqa: F401  (ensures the package path shim runs)
from .config import BACKEND_DIR, settings
from .routers import bowling, core, labs, matches


def run_migrations() -> None:
    """Bring the database schema up to date with Alembic."""
    from alembic import command
    from alembic.config import Config
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
    command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.run_migrations:
        run_migrations()
    yield


app = FastAPI(
    title="PitchVision API",
    version="1.0.0",
    description="Cricket performance and analytics for a school team. All analytics are computed by the shared "
                "`pitchvision` Python package, which the Jupyter notebooks import as well. Video-based results "
                "are estimates with stated uncertainty; the DRS simulation is educational, not an official system.",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

for r in (core.router, bowling.router, matches.router, labs.router):
    app.include_router(r, prefix="/api")


@app.get("/api/health", tags=["health"])
def health():
    return {"status": "ok", "version": app.version}


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    # Never leak a stack trace to the browser; the server log has the detail.
    import logging
    logging.getLogger("pitchvision").exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Something went wrong on the server. Try again; "
                                                            "if it keeps happening, check the server log."})


# Serve the built frontend (frontend/dist) when it exists, so one process runs the whole app.
_DIST = BACKEND_DIR.parent / "frontend" / "dist"
if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = _DIST / path
        return FileResponse(f if path and f.is_file() else _DIST / "index.html")
