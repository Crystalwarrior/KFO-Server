FROM python:3.11-alpine

RUN apk --no-cache add git

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY server/ server/
COPY migrations/ migrations/
COPY storage/ storage/
COPY start_server.py ./

CMD ["uv", "run", "python", "./start_server.py"]
