FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml .
COPY uv.lock .

RUN --mount=type=cache,target=/var/cache/apt \
    apt update && \    
    apt install -y gcc

RUN --mount=type=cache,target=/var/cache/pip \
    pip install --cache-dir /var/cache/pip uv

RUN --mount=type=cache,target=/var/cache/uv \
    uv sync --cache-dir /var/cache/uv

COPY . .

RUN mkdir -p /app/data/logs/ /app/data/db/ /app/data/temp/ /app/data/pyrogram/

VOLUME [ "/app/data/" , "app/apps/", "app/apps/config/"]

# Create directory for Local Bot API Server session files
RUN mkdir -p /app/data/telegram-bot-api-sessions/

RUN . /apps/.venv/bin/activate

EXPOSE 8000

# RUN 
CMD ./run_celery.sh && uv run manage.py migrate && uv run manage.py runserver 0.0.0.0:8000 & uv run manage.py runbot --reload  
