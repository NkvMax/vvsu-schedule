# VVSU Schedule — Lite (Playwright + Firefox)

Легкая версия синхронизации расписания ВВГУ в Google Calendar.
Dev — через **Poetry**, браузер — **Playwright Firefox (bundled)**, CI — **GitHub Actions**.

## Быстрый старт (локально)

```bash
poetry install
poetry run playwright install firefox

# заполните .env (логин/пароль ВВГУ, календарь, путь до service_account.json)
cp .env.example .env

# сухой прогон без записи в календарь
poetry run python -m vvsu_lite.sync --dry-run

# боевая запись
poetry run python -m vvsu_lite.sync
```

## CI (GitHub Actions)
Экспорт зависимости для CI:
```bash
poetry export -f requirements.txt --output requirements.txt --without-hashes
```

В CI используются GitHub Secrets (`VVSU_LOGIN`, `VVSU_PASSWORD`, `GOOGLE_CREDENTIALS_B64`, `CALENDAR_ID`/`CALENDAR_NAME`).
