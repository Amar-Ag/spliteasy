# SplitEasy Backend

FastAPI backend for SplitEasy. Data lives in an in-memory mock database for now (`app/mock_db.py`) and resets on restart.

## Run

```bash
uv sync
uv run uvicorn main:app --reload
```

API docs: http://127.0.0.1:8000/docs

Demo accounts are seeded on startup: `alice`, `bob`, `carol`, `dave` — password `password123`.

## Test

```bash
uv run pytest
```

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `SPLITEASY_JWT_SECRET` | random per process | Secret for signing JWTs. Set it so tokens survive restarts. |
| `SPLITEASY_TOKEN_TTL_MINUTES` | `10080` (7 days) | Token lifetime |
| `SPLITEASY_CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated origins allowed to call the API (the Vite dev server) |
| `SPLITEASY_SEED_DEMO_DATA` | `true` | Seed demo users and groups |

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
app/database.py      Storage interface (Protocol)
app/mock_db.py       In-memory implementation — swap for SQLAlchemy later
app/security.py      Password hashing (PBKDF2) and JWTs
app/seed.py          Demo data
tests/               Endpoint tests (pytest + TestClient)
```

To switch to a real database, implement the `Database` protocol and pass it to `create_app(db=...)`.
