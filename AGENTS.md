# SplitEasy — Agent Context

## Project
Expense splitting app. Full spec in `_docs/specs.md` — read it before starting any task.

## Structure
- `frontend/` — React + TypeScript, Vite
- `backend/` — FastAPI, Python, uv for package management
- `_docs/` — specs and planning docs

## Key rules
- Frontend: all backend calls centralized in one place (e.g. `frontend/src/api.ts`)
- Backend: FastAPI with SQLAlchemy, SQLite for now
- Tests: write tests before implementing endpoints
- Auth: JWT tokens

## Commands
- Frontend: `npm run dev` (from `frontend/`)
- Backend: `uv run uvicorn main:app --reload` (from `backend/`)
- Tests: `uv run pytest` (from `backend/`)
