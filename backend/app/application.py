from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import Settings
from app.database import Database
from app.errors import NotFound, register_exception_handlers
from app.routers import auth, expenses, groups, settlements
from app.seed import seed_demo_data
from app.sql_database import SqlDatabase

API_PREFIX = "/api"


def create_app(settings: Settings | None = None, db: Database | None = None) -> FastAPI:
    """Build the API.

    Pass `db` to supply any `Database` implementation (tests do). Otherwise the app connects to
    `settings.database_url`, creates missing tables, seeds demo data if enabled, and closes the
    connection pool on shutdown.
    """
    settings = settings or Settings.from_env()
    owned_db: SqlDatabase | None = None
    if db is None:
        owned_db = SqlDatabase.from_url(settings.database_url)
        owned_db.create_schema()
        if settings.seed_demo_data:
            seed_demo_data(owned_db, settings)
        db = owned_db

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        if owned_db is not None:
            owned_db.close()

    app = FastAPI(title="SplitEasy API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.db = db

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)

    # The API lives under /api so the frontend can own the rest of the URL space
    # (/groups/{id} is a page in the UI as well as an API path).
    for router in (auth.router, groups.router, expenses.router, settlements.router):
        app.include_router(router, prefix=API_PREFIX)

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    if settings.static_dir:
        mount_frontend(app, Path(settings.static_dir))

    return app


def mount_frontend(app: FastAPI, root: Path) -> None:
    """Serve the built frontend: real files as-is, every other path as index.html.

    The single-page app does its own routing, so a refresh on /groups/{id} must still get
    index.html. Registered last, so /api and /health keep priority.
    """
    index = root / "index.html"
    assets = root / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend(full_path: str) -> FileResponse:
        # An unmatched API path is a missing endpoint, not a page.
        if f"/{full_path}".startswith(f"{API_PREFIX}/"):
            raise NotFound("Not found")
        candidate = root.joinpath(full_path).resolve()
        if candidate.is_file() and candidate.is_relative_to(root.resolve()):
            return FileResponse(candidate)
        return FileResponse(index)
