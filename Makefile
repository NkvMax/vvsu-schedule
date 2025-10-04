# Makefile для управления vvsu-schedule

GREEN=\033[0;32m
YELLOW=\033[1;33m
RED=\033[0;31m
NC=\033[0m

COMPOSE_FILE=docker-compose.prod.yml
URL=https://schedule.localhost

.PHONY: up down restart logs clean help status

up:
	@echo "Запуск проекта..."
	@docker compose -f $(COMPOSE_FILE) up -d --build
	@echo "$(GREEN)Проект запущен! Откройте в браузере: $(URL)$(NC)"

up-fast:
	@echo "Запуск проект... (без сборки и без pull)"
	@docker compose -f $(COMPOSE_FILE) up -d --no-build --pull never --remove-orphans
	@echo "$(GREEN)Проект запущен! Откройте в браузере: $(URL)$(NC)"

down:
	@echo "Остановка проекта..."
	@docker compose -f $(COMPOSE_FILE) down
	@echo "Проект остановлен."

restart: down up
	@echo "Перезапуск проекта..."

logs:
	@echo "Вывод логов..."
	@docker compose -f $(COMPOSE_FILE) logs -f

clean:
	@echo "Очистка (удаление контейнеров, сетей и томов)..."
	@docker compose -f $(COMPOSE_FILE) down -v --remove-orphans
	@echo "Очистка завершена."

help:
	@echo "Доступные команды:"
	@echo "  make up        - Запустить проект"
	@echo "  make down      - Остановить проект"
	@echo "  make restart   - Перезапустить проект"
	@echo "  make logs      - Показать логи"
	@echo "  make clean     - Очистить все (контейнеры, сети, тома)"
	@echo "  make status    - Показать статус сервера и настроек"
	@echo "  make help      - Показать эту справку"

status:
	@echo "---------------------"

	@echo "$(YELLOW)Состояние сервисов:$(NC)"
	@services=$$(docker compose -f $(COMPOSE_FILE) ps --format "  {{.Service}} : {{.State}}"); \
	if [ -z "$$services" ]; then \
		echo "  $(RED)No running services$(NC)"; \
	else \
		echo "$$services" | sed 's/Up/$(GREEN)Up$(NC)/; s/Exit/$(RED)Exit$(NC)/; s/Stopped/$(RED)Stopped$(NC)/'; \
	fi
	@echo "---------------------"

	@echo "$(YELLOW)Нагрузка на сервер:$(NC)"
	@if docker compose -f $(COMPOSE_FILE) ps -q | grep -q .; then \
		docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" | \
		sed '1d' | \
		while read -r name cpu ram; do \
			printf "  %-20s : CPU %-6s | RAM %-20s\n" "$$name" "$$cpu" "$$ram"; \
		done; \
	else \
		echo "  $(RED)Services are not running$(NC)"; \
	fi
	@echo "---------------------"

	@echo "$(YELLOW)Настройки:$(NC)"
	@if [ -f .env ]; then \
		echo "  TIMEZONE         : $$(grep TIMEZONE .env | cut -d'=' -f2)"; \
	else \
		echo "  .env not found. Check container settings."; \
	fi
	@echo "  URL              : $(GREEN)$(URL)$(NC)"
	@echo "---------------------"
