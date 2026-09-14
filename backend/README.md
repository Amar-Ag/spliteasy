# SplitEasy Backend

FastAPI backend for SplitEasy. Data is stored with SQLAlchemy — a local SQLite file (`backend/spliteasy.db`) by default.

## Run

```bash
uv sync
uv run uvicorn main:app --reload
```

API docs: http://127.0.0.1:8000/docs

Tables are created on startup if missing. Demo accounts are seeded into an empty database: `alice`, `bob`, `carol`, `dave` — password `password123`. Delete `spliteasy.db` to start fresh.

## Test

```bash
uv run pytest
```

API tests run twice — against in-memory SQLite and a temporary SQLite file. `tests/test_sql_database.py` covers the storage layer directly.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `SPLITEASY_JWT_SECRET` | random per process | Secret for signing JWTs. Set it so tokens survive restarts. |
| `SPLITEASY_TOKEN_TTL_MINUTES` | `10080` (7 days) | Token lifetime |
| `SPLITEASY_CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated origins allowed to call the API (the Vite dev server) |
| `SPLITEASY_SEED_DEMO_DATA` | `true` | Seed demo users and groups into an empty database |
| `SPLITEASY_DATABASE_URL` | `sqlite:///./spliteasy.db` | Any SQLAlchemy URL, e.g. `postgresql+psycopg://user:pass@host/spliteasy` (install the driver with `uv add`) |

## API

JSON uses camelCase and money is integer cents, matching `frontend/src/types.ts`. Errors are `{"detail": "message"}`.
All endpoints except register/login/health need `Authorization: Bearer <token>`.

| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | Create account → `{token, user}` |
| POST | `/auth/login` | Log in with email or username → `{token, user}` |
| POST | `/auth/logout` | Revoke the current token |
| GET | `/auth/me` | Current user |
| GET | `/groups` | My groups with my balance in each |
| POST | `/groups` | Create a group |
| GET | `/groups/{id}` | Group with members |
| POST | `/groups/{id}/members` | Add a member by email or username |
| GET | `/groups/{id}/expenses` | Expense history, newest first |
| POST | `/groups/{id}/expenses` | Add expense split by `amount` (cents) or `percent` |
| GET | `/groups/{id}/balances` | Net balance per member and suggested transfers |
| GET | `/groups/{id}/settlements` | Payment history, newest first |
| POST | `/groups/{id}/settlements` | Record a payment |

Non-members get `404` for a group, so group ids can't be probed.

## Layout

```
main.py              ASGI entry point (uvicorn main:app)
app/application.py   App factory: settings, database, routers, CORS
app/routers/         HTTP endpoints
app/services.py      Business rules and validation
app/money.py         Split allocation and debt simplification
app/database.py      Storage interface (Protocol) — the only thing services and routes depend on
app/sql_database.py  SQLAlchemy tables and the `SqlDatabase` implementation
app/models.py        Domain dataclasses passed between layers
app/security.py      Password hashing (PBKDF2) and JWTs
app/seed.py          Demo data
tests/               API tests (pytest + TestClient) and storage tests
```

The app is database-agnostic at two levels: `SqlDatabase` works with any SQLAlchemy-supported database via
`SPLITEASY_DATABASE_URL`, and a completely different store can be plugged in by implementing the `Database`
protocol and passing it to `create_app(db=...)`.

Schema changes are applied with `create_all`, which only creates missing tables. Once the schema needs to evolve
with real data in place, add Alembic migrations.
