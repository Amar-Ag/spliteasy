from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings
from app.database import Database
from app.errors import register_exception_handlers
from app.mock_db import MockDatabase
from app.routers import auth, expenses, groups, settlements
from app.seed import seed_demo_data


def create_app(settings: Settings | None = None, db: Database | None = None) -> FastAPI:
    """Build the API. Tests pass their own settings and database; `main.py` uses the environment."""
    settings = settings or Settings.from_env()
    if db is None:
        db = MockDatabase()
        if settings.seed_demo_data:
            seed_demo_data(db, settings)

    app = FastAPI(title="SplitEasy API", version="0.1.0")
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
