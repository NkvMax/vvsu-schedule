# Stage 1: Frontend build
FROM --platform=linux/amd64 node:20 AS frontend-build

WORKDIR /frontend

COPY src/frontend/package*.json ./
RUN npm ci

COPY src/frontend ./

RUN npm run build

# Stage 2: Backend setup
FROM python:3.9-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="/vvsu-schedule/src" \
    TZ=Asia/Vladivostok

WORKDIR /vvsu-schedule

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl tzdata ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry==2.1.1 \
    && poetry config virtualenvs.create false \
    && poetry self add poetry-plugin-shell

COPY pyproject.toml poetry.lock ./
COPY alembic.ini ./
COPY alembic ./alembic
COPY src ./src
RUN poetry install --no-interaction --no-ansi

# Копируем статический билд фронта
COPY --from=frontend-build /frontend/dist ./src/frontend/dist

CMD ["poetry", "run", "uvicorn", "schedule_vvsu.api:app", "--host", "0.0.0.0", "--port", "8000"]
