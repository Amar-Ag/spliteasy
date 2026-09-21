# SplitEasy

A web app for splitting shared expenses across multiple groups.

Built as part of the [AI Dev Tools Zoomcamp](https://github.com/DataTalksClub/ai-dev-tools-zoomcamp) — Homework 2.

## Stack
- Frontend: React + TypeScript
- Backend: FastAPI (Python)
- Database: SQLite via SQLAlchemy

## Run with Docker

One image contains the API and the built frontend, served together on port 8000.

```bash
docker build -t spliteasy .
docker run -p 8000:8000 -v spliteasy-data:/data -e SPLITEASY_JWT_SECRET=change-me spliteasy
```

Open http://localhost:8000. The SQLite database lives on the `/data` volume, so it survives
restarts and rebuilds. Without `SPLITEASY_JWT_SECRET` a random secret is generated on each start,
which signs everyone out when the container restarts.

## Run locally

```bash
cd backend && uv run uvicorn main:app --reload   # http://localhost:8000
cd frontend && npm run dev                       # http://localhost:5173
```

In development the frontend runs on its own port and calls the backend at `http://localhost:8000`
(`VITE_API_URL`). The API is served under `/api`; every other path belongs to the frontend.
