import logging
import os
import secrets
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# The Vite dev server, reachable under either hostname.
DEFAULT_CORS_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    return default if raw is None else raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    token_ttl_minutes: int = 60 * 24 * 7
    password_hash_iterations: int = 600_000
    cors_origins: tuple[str, ...] = DEFAULT_CORS_ORIGINS
    seed_demo_data: bool = True
    # Any SQLAlchemy URL. Relative SQLite paths resolve against the working directory (backend/).
    database_url: str = "sqlite:///./spliteasy.db"

    @classmethod
    def from_env(cls) -> "Settings":
        secret = os.environ.get("SPLITEASY_JWT_SECRET")
        if not secret:
            secret = secrets.token_urlsafe(48)
            logger.warning("SPLITEASY_JWT_SECRET is not set; using a random secret, so tokens reset on restart.")

        origins = os.environ.get("SPLITEASY_CORS_ORIGINS", ",".join(DEFAULT_CORS_ORIGINS))
        return cls(
            jwt_secret=secret,
            token_ttl_minutes=int(os.environ.get("SPLITEASY_TOKEN_TTL_MINUTES", cls.token_ttl_minutes)),
            cors_origins=tuple(o.strip() for o in origins.split(",") if o.strip()),
            seed_demo_data=_env_bool("SPLITEASY_SEED_DEMO_DATA", True),
            database_url=os.environ.get("SPLITEASY_DATABASE_URL", cls.database_url),
        )
