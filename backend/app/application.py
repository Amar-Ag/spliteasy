from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings
from app.database import Database
from app.errors import register_exception_handlers
from app.routers import auth, expenses, groups, settlements
from app.seed import seed_demo_data
from app.sql_database import SqlDatabase


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

    app.include_router(auth.router)
    app.include_router(groups.router)
    app.include_router(expenses.router)
    app.include_router(settlements.router)

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
