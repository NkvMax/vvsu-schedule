# Ansible bootstrap для schedule-vvsu-lite

## Запуск (localhost)
Из корня репозитория:

Через Makefile:

```bash
make infra
```

## Примечания

* Кэш браузеров Playwright закреплен за домашней директорией пользователя синхронизации через `PLAYWRIGHT_BROWSERS_PATH`, чтобы избежать проблем с `/root/.cache`.
* Если Firefox уже установлен в `~/.cache/ms-playwright`, шаг загрузки браузера пропускается.
