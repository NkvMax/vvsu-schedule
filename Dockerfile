FROM python:3.9-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Добавляем src в PYTHONPATH, чтобы пакет schedule_vvsu был доступен как установленный пакет
ENV PYTHONPATH="/vvsu-schedule/src"

WORKDIR /vvsu-schedule

# Устанавливаем системные зависимости (curl, wget, gnupg, unzip)
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    gnupg \
    unzip && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Устанавливаем Poetry
RUN pip install --no-cache-dir poetry==2.1.1

# Отключаем создание виртуальных окружений, чтобы Poetry устанавливал зависимости прямо в образе
RUN poetry config virtualenvs.create false

# Копируем файлы описания зависимостей
COPY pyproject.toml poetry.lock ./

# Устанавливаем зависимости и сам пакет (без использования --no-root, чтобы проект был установлен как пакет)
RUN poetry install --no-interaction --no-ansi --no-root

# Копируем исходный код проекта из каталога src
COPY src ./src

CMD ["python", "-m", "src.schedule_vvsu.scheduler"]
