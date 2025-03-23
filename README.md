# Schedule-VVSU

Проект для автоматической синхронизации расписания занятий из личного кабинета в Google Calendar.  
Позволяет извлекать расписание с сайта ВВГУ и автоматически создавать или обновлять события в календаре.


## Возможности

- Парсинг расписания (лекции, практики и пр.) из личного кабинета.
    
- Добавление и обновление событий в Google Calendar (через сервисный аккаунт или пользовательский OAuth).
    
- Гибкая конфигурация через `.env` или переменные окружения.
    
- Запуск по расписанию (APScheduler) или вручную через CLI.


## Файлы и директории

- `src/schedule_vvsu/cli/`: реализация командного интерфейса (CLI).
    
- `src/schedule_vvsu/google_calendar/`: логика взаимодействия с Google API.
    
- `src/schedule_vvsu/parser.py`: парсинг расписания.
    
- `src/schedule_vvsu/scheduler.py`: запуск APScheduler для периодического парсинга.
    
- `.env.example`: пример файла окружения.
    
- `pyproject.toml`, `poetry.lock`: управление зависимостями.
    
- `Dockerfile`: инструкция сборки Docker-образа.
    
- `docker-compose.yml`: упрощенный запуск в контейнере.
    

## Требования

- **Python 3.9+** (либо **Docker**, если хотите запускать все в контейнере).
    
- **Poetry** (для управления зависимостями) или `pip` с `requirements.txt` как классический подход.
    
- **Google API credentials**:
    
    - Сервисный аккаунт (**рекомендуется** для продакшена).
        
    - Или пользовательский аккаунт (**Legacy**, требует ручной OAuth-авторизации раз в несколько дней).
        

---

## Установка и запуск (без Docker)

### Клонируйте репозиторий

```bash
git clone https://github.com/username/schedule-vvsu.git
cd schedule-vvsu
```

### Настройка Google Calendar

#### Сервисный аккаунт:

- Получите JSON-ключ из Google Cloud Console.
    

- Вставте содержимое файла по пути src/schedule_vvsu/json/credentials/service_account.json


- Приложение создаст или обновит события от имени сервисного аккаунта.
    

#### Пользовательский аккаунт (OAuth):

- Создайте OAuth Client ID в Google Cloud Console.
    

- Вставте содержимое файла по пути src/schedule_vvsu/json/credentials/user_account.json


- При первом запуске потребуется авторизация через браузер.
    

### Установите зависимости

Через Poetry:

```bash
poetry install
```

Или через pip:

```bash
pip install -r requirements.txt
```

### Конфигурация

Создайте `.env` файл из шаблона `.env.example` и заполните необходимые переменные:

```
LOGIN_URL=https://cabinet.vvsu.ru/
SCHEDULE_URL=https://cabinet.vvsu.ru/time-table/
USERNAME=my_username
PASSWORD=my_password
TIMEZONE=Asia/Vladivostok
CALENDAR_NAME=Расписание ВВГУ
ACCOUNT_TYPE=service_account
USER_MAIL_ACCOUNT=...
DEV_MODE=false
ACTIVATE_DOCKER_TIME_SETTINGS=true
PARSING_INTERVALS=9:00,14:00,17:00
```

### Запуск CLI

Запуск CLI для управления:

### Вариант A: Сразу через poetry run

```bash
poetry run python -m schedule_vvsu.cli.main --help
```

Запуск планировщика:

```bash
poetry run python -m schedule_vvsu.scheduler
```

### Вариант B: Через интерактивную оболочку

Активировать окружение:
```bash
poetry shell
```

Вызвать CLI напрямую:
```bash
vvsu-cli --help
```

```bash
vvsu-cli start-scheduler
```

```bash
vvsu-cli stop-scheduler
```

---

## Запуск через Docker

### Сборка и запуск контейнера

```bash
docker-compose up --build
```



---


Если проект оказался полезен, поддержите его звездочкой ⭐️ на GitHub!

Pull-requests и обсуждения приветствуются! ☺️
