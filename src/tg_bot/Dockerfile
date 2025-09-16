FROM python:3.9-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN pip install -q poetry && poetry config virtualenvs.create false

COPY src/tg_bot/pyproject.toml src/tg_bot/poetry.lock* /app/
RUN poetry install --only main --no-root

COPY src/tg_bot/app /app/app

COPY src/schedule_vvsu /app/schedule_vvsu
RUN python -m pip install --no-cache-dir -r /app/schedule_vvsu/requirements.txt

ENV PYTHONPATH=/app:$PYTHONPATH

CMD ["poetry", "run", "python", "-m", "app.bot"]
