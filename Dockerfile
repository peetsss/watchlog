ARG PYTHON_VERSION=3.14-slim
ARG PYTHON_BUILD_VERSION=$PYTHON_VERSION-trixie

FROM python:${PYTHON_BUILD_VERSION}

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ARG USER_ID
ARG GROUP_ID

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_SYSTEM_PYTHON=1

RUN groupadd -g $GROUP_ID -o user && useradd -o -m -u $USER_ID -g user user

RUN apt-get update -y && \
    apt-get install -y --no-install-recommends netcat-openbsd && \
    apt-get clean

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv export --frozen --format=requirements-txt --dev > requirements.txt && \
    uv pip install --system --no-cache -r requirements.txt

COPY ./src .

RUN sed -i 's/\r$//g' /app/entrypoint.sh && chmod +x /app/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]

USER user
