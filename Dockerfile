FROM python:3.11-alpine

RUN apk --no-cache add git
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY start_server.py ./
COPY server/ server/
COPY migrations/ migrations/
COPY storage/ storage/

CMD ["python", "./start_server.py"]
