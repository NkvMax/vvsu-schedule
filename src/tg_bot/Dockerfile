FROM python:3.9-slim

WORKDIR /app

RUN pip install -q poetry

COPY pyproject.toml poetry.lock* ./

RUN poetry config virtualenvs.create false
RUN poetry install --only main --no-root

COPY app ./app

CMD ["poetry", "run", "python", "-m", "app.bot"]