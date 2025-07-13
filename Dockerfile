FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml .
COPY uv.lock .

RUN --mount=type=cache,target=/var/cache/pip \
    pip install --cache-dir /var/cache/pip uv

RUN --mount=type=cache,target=/var/cache/uv \
    uv sync --cache-dir /var/cache/uv

COPY . .

CMD ["uv", "run", "manage.py", "runbot"]
