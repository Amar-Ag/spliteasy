# Stage 1 — build the frontend. An empty VITE_API_URL keeps API calls same-origin,
# because the backend serves these files itself.
FROM node:22-alpine AS frontend

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./
ENV VITE_API_URL=""
RUN npm run build


# Stage 2 — the backend, serving the API and the built frontend.
FROM python:3.12-slim AS backend
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Dependencies first so code changes don't re-resolve them.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev

COPY backend/ ./
COPY --from=frontend /frontend/dist ./static

# The database lives on a volume so it survives `docker run --rm` and image rebuilds.
ENV SPLITEASY_STATIC_DIR=/app/static \
    SPLITEASY_DATABASE_URL=sqlite:////data/spliteasy.db
VOLUME ["/data"]

RUN useradd --create-home --uid 1000 app && mkdir -p /data && chown app:app /data /app
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health').read()"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
