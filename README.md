# Schedule‑VVSU **Lite** (GitHub Actions)

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![Playwright](https://img.shields.io/badge/Playwright-Firefox-informational)
![Google%20Calendar%20API](https://img.shields.io/badge/Google-Calendar%20API-success)
![GitHub%20Actions](https://img.shields.io/badge/CI-GitHub%20Actions-purple)
[![License](https://img.shields.io/github/license/NkvMax/vvsu-schedule)](https://github.com/NkvMax/vvsu-schedule/blob/main/LICENSE)

Проект для **автосинхронизации расписания ВВГУ в Google Calendar** без серверов и Docker.  
Lite-версия — это минимальный Python‑скрипт + GitHub Actions: все выполняется по расписанию в облаке.

> Полная версия с API/БД/ботом находится в ветке **main**. Эта документация относится к ветке **lite-version**.

### Время выполнения

Полный цикл пайплайна при повторных запусках GitHub Actions занимает **около 3 минут 30 секунд**  
(включая установку зависимостей, загрузку браузера Playwright и синхронизацию расписания). **При повторных запусках береться кэш браузера и pip-пакетов.**

---
<details>
<summary><b>Быстрый старт (GitHub Actions)</b></summary>

### 1) Форкни репозиторий
Форкни `NkvMax/vvsu-schedule` и переключись на ветку **lite-version** (именно здесь находится код Lite).

### 2) Включи Google Calendar API
В своем GCP‑проекте включи **Google Calendar API**:
- https://console.cloud.google.com/apis/library
- Выбери проект -> найди “Google Calendar API” -> **Enable**.

### 3) Создай Service Account и JSON‑ключ
- IAM & Admin -> Service Accounts -> Create.
- Роль достаточно **Project -> Editor** (для теста).
- Keys -> Add key -> **JSON** -> скачай `service_account.json`.

**Преобразуй ключ в Base64** (одна строка):

- macOS / Linux:
  ```bash
  base64 -w0 service_account.json | pbcopy
  ```

- Windows PowerShell:
  ```powershell
  [Convert]::ToBase64String([IO.File]::ReadAllBytes("service_account.json"))
  ```
  Ключ попадет сразу в буфер обмена

### 4) Добавь единый секрет `ACTIONS_ENV`
GitHub -> твое репо -> **Settings -> Secrets and variables -> Actions -> New repository secret**.

**Name:** `ACTIONS_ENV`  
**Value:** весь блок `.env` ниже (замени значениями; каждая строка — `KEY=VALUE`).

> **Подробное описание всех переменных**  
> Смотри файл [`.env.example.github.actions`](https://github.com/NkvMax/vvsu-schedule/blob/lite-version/.env.example.github.actions) —  
> там перечислены _все параметры окружения_ с комментариями, значениями по умолчанию  
> и примерами для GitHub Actions.
> 
> В `README` ниже приведен минимальный пример для быстрого запуска,  
> но полный список доступных ключей и их описание ищи именно там.


```ini
#############################################
# VVSU cabinet credentials
#############################################
LOGIN_URL=https://cabinet.vvsu.ru/
SCHEDULE_URL=https://cabinet.vvsu.ru/time-table/
VVSU_LOGIN=your_login
VVSU_PASSWORD=your_password

#############################################
# Playwright
#############################################
PW_HEADLESS=1
PW_TIMEOUT_MS=20000
PW_SLEEP_AFTER=0

#############################################
# Sync
#############################################
TIMEZONE=Asia/Vladivostok
HORIZON_DAYS=180
REMINDER_MINUTES=10
LOG_LEVEL=INFO

#############################################
# Google Calendar
#############################################

# Идентификация календаря:
# Укажите либо имя календаря (удобно), либо его ID
GCAL_CALENDAR_SUMMARY=
GCAL_CALENDAR_ID=

# Автоматически создать календарь, если не найден по имени
GCAL_CREATE_IF_MISSING=1
GCAL_NEW_CALENDAR_TZ=Asia/Vladivostok

# Расшарить календарь на твою почту что ты мог его администрировать и добовлять другие аккаунты через web-интерфейс
GCAL_SHARE_GMAIL=
GCAL_SHARE_ROLE=writer

# Удалять будущие события, которых больше нет в расписании (0/1)
GCAL_REMOVE_MISSING=0

#############################################
# Service Account JSON as Base64 (SINGLE LINE)
#############################################
GOOGLE_CREDENTIALS_B64=PASTE_BASE64_HERE
```

> Сервисный аккаунт **видит только** свои календари и те, что **расшарены на его e‑mail**.  
> Либо укажи `GCAL_CALENDAR_ID` календаря, расшаренного на SA (роль *Make changes to events*), либо позволь создать новый календарь (`GCAL_CREATE_IF_MISSING=1`).

### 5) Включи workflow в **main**
В **ветке main** лежит отключенный файл:  
`.github/workflows/vvsu-lite-sync.yml.disabled`

Скопируй его под рабочим именем и закоммить:
```bash
cp .github/workflows/vvsu-lite-sync.yml.disabled .github/workflows/vvsu-lite-sync.yml
git add .github/workflows/vvsu-lite-sync.yml
git commit -m "ci: enable vvsu-lite-sync workflow (lite-version checkout)"
git push
```

Workflow чекаутит **lite-version** и запускает синк по крону **каждый день в 13:00 Владивосток (UTC+10)**:  
`cron: "0 3 * * *"` — можно запускать вручную через **Actions -> Run workflow**.

---

## Ошибки

- **403 `accessNotConfigured`** — включи **Google Calendar API** для своего GCP‑проекта.
- **404 / `insufficientPermissions`** — календарь не расшарен на e‑mail сервисного аккаунта / неверный ID.
- **Дубликаты событий** — ID генерируются детерминированно; при конфликте выполняется `update`. Повторы обычно вызваны изменением правила генерации ID — запусти еще раз, или включи `GCAL_REMOVE_MISSING=1` для «сноса» исчезнувших.

---

## Безопасность

- Все секреты — только в **`ACTIONS_ENV`** (GitHub Secrets).  

---



## Pull requests

PR‑ы приветствуются. Придерживайся стиля коммитов **Conventional Commits** (`feat:`, `fix:`, `chore(ci): ...`).

