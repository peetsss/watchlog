# syntax=docker/dockerfile:1
ARG NODE_VERSION=22-alpine
ARG PYTHON_VERSION=3.14-slim-trixie

FROM node:${NODE_VERSION} AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:${PYTHON_VERSION} AS runtime
COPY --from=ghcr.io/astral-sh/uv:0.9.25 /uv /bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1 \
    UV_LINK_MODE=copy \
    WATCHLOG_ENV=prod \
    WATCHLOG_FRONTEND_DIR=/app/frontend/dist

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv export --frozen --format=requirements-txt --no-dev > /tmp/requirements.txt && \
    uv pip install --system --no-cache -r /tmp/requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts ./scripts
COPY --from=frontend /app/frontend/dist ./frontend/dist

RUN useradd --create-home --uid 1000 appuser && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/ready')" || exit 1
CMD ["python", "-m", "scripts.api_entrypoint"]
