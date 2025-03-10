FROM python:3.9-slim

WORKDIR /app

RUN pip install --no-cache-dir poetry==1.6.1

COPY pyproject.toml poetry.lock /app/

RUN poetry install --no-interaction --no-ansi

COPY src /app/src

WORKDIR /app/src/schedule_vvsu

CMD ["poetry", "run", "python", "-m", "schedule_vvsu.cli.main", "--help"]