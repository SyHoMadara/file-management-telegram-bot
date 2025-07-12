# Use an appropriate base image
FROM python:3.13-slim

# Ensure BuildKit is enabled (not needed in the Dockerfile, but ensure it’s enabled in your environment)
# Set the working directory
WORKDIR /app

COPY pyproject.toml .
COPY uv.lock .

# Use RUN --mount to bind /home/hosein to /hiiii and copy files
RUN --mount=type=cache,target=/var/cache/pip \
    pip install --cache-dir /var/cache/pip uv

RUN --mount=type=cache,target=/var/cache/uv \
    uv sync --cache-dir /var/cache/uv

COPY . .

CMD ["uv", "run", "manage.py", "runbot"]
