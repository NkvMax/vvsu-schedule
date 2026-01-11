include make/calendars.mk

MAKEFILE_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
PROJECT_DIR  := $(abspath $(MAKEFILE_DIR))


ANSIBLE_DIR  := $(PROJECT_DIR)/ansible
INVENTORY    := $(ANSIBLE_DIR)/inventory.ini
PLAYBOOK     := $(ANSIBLE_DIR)/playbook.yml

.PHONY: infra build up run down status logs
infra:
	@sudo -v
	ansible-playbook -i $(INVENTORY) $(PLAYBOOK)

build:
	@sudo -v
	ansible-playbook -i $(INVENTORY) $(PLAYBOOK) --tags build

up:
	@sudo -v
	ansible-playbook -i $(INVENTORY) $(PLAYBOOK) --tags systemd

run:
	@sudo -v
	@sudo systemctl restart vvsu-sync.service
	@echo "Restarted vvsu-sync.service"

down:
	@sudo systemctl disable --now vvsu-sync.timer >/dev/null 2>&1 || true
	@sudo systemctl stop vvsu-sync.service >/dev/null 2>&1 || true
	@sudo rm -f /etc/systemd/system/vvsu-sync.service /etc/systemd/system/vvsu-sync.timer
	@sudo systemctl daemon-reload
	@sudo systemctl reset-failed vvsu-sync.service >/dev/null 2>&1 || true
	@echo "Removed systemd units."

status:
	@systemctl status vvsu-sync.timer --no-pager -l || true
	@systemctl status vvsu-sync.service --no-pager -l || true

logs:
	@journalctl -u vvsu-sync.service -n 200 --no-pager -o cat || true

.PHONY: version
version:
	@echo -n "commit: "
	@git rev-parse --short HEAD
	@echo -n "tag:    "
	@git describe --tags --exact-match 2>/dev/null || echo "(no tag)"

.PHONY: releases
releases:
	@git fetch --tags -q
	@git tag -l "v*" --sort=-v:refname | head -n 20

.PHONY: changelog
changelog:
	@test -n "$(VERSION)" || (echo "Set VERSION=vX.Y.Z"; exit 2)
	@git fetch --tags -q
	@echo "Changes from current -> $(VERSION):"
	@git log --oneline --decorate HEAD..$(VERSION)

.PHONY: update upgrade rollback _switch
update:
	@sudo -v
	@git pull --ff-only
	ansible-playbook -i $(INVENTORY) $(PLAYBOOK) --tags build,systemd
	@sudo systemctl restart vvsu-sync.service
	@echo "Updated current branch and restarted."

_switch:
	@test -n "$(VERSION)" || (echo "Set VERSION=vX.Y.Z"; exit 2)
	@sudo -v
	@git fetch --tags -q
	@git checkout -q $(VERSION)
	ansible-playbook -i $(INVENTORY) $(PLAYBOOK) --tags build,systemd
	@sudo systemctl restart vvsu-sync.service

upgrade: _switch
	@echo "Upgraded to $(VERSION)"

rollback: _switch
	@echo "Rolled back to $(VERSION)"

.PHONY: back
back:
	@git checkout -q lite-selfhosted
	@echo "Switched back to lite-selfhosted"

BLUE  := \033[34m
RESET := \033[0m

.PHONY: help
help:
	@echo ""
	@echo "Schedule-VVSU Lite Self-Hosted — команды Makefile"
	@echo ""
	@echo "Установка / Деплой:"
	@printf "  $(BLUE)%-34s$(RESET) %s\n" "make infra"    "Полный прогон ansible (build + systemd)"
	@printf "  $(BLUE)%-34s$(RESET) %s\n" "make build"    "Подготовить окружение (ansible tag: build)"
	@printf "  $(BLUE)%-34s$(RESET) %s\n" "make up"       "Установить и включить systemd service+timer (ansible tag: systemd)"
	@echo ""
	@echo "Запуск / Управление:"
	@printf "  $(BLUE)%-34s$(RESET) %s\n" "make run"      "Запустить синхронизацию сейчас (restart vvsu-sync.service)"
	@printf "  $(BLUE)%-34s$(RESET) %s\n" "make status"   "Статус таймера и сервиса systemd"
	@printf "  $(BLUE)%-34s$(RESET) %s\n" "make logs"     "Последние логи сервиса (journalctl)"
	@printf "  $(BLUE)%-34s$(RESET) %s\n" "make down"     "Отключить и удалить systemd unit-файлы"
	@echo ""
	@echo "Версии:"
	@printf "  $(BLUE)%-34s$(RESET) %s\n" "make version"  "Показать текущий commit и tag (если есть)"
	@printf "  $(BLUE)%-34s$(RESET) %s\n" "make releases" "Показать последние 20 тегов (v*)"
	@printf "  $(BLUE)%-34s$(RESET) %s\n" "make changelog VERSION=vX.Y.Z" "Показать изменения от текущей версии до VERSION"
	@echo ""
	@echo "Обновление / Переключение версии:"
	@printf "  $(BLUE)%-34s$(RESET) %s\n" "make update"   "Подтянуть текущую ветку (git pull) + деплой + рестарт"
	@printf "  $(BLUE)%-34s$(RESET) %s\n" "make upgrade VERSION=vX.Y.Z"  "Переключиться на тег VERSION + деплой + рестарт"
	@printf "  $(BLUE)%-34s$(RESET) %s\n" "make rollback VERSION=vX.Y.Z" "Откатиться на тег VERSION + деплой + рестарт"
	@printf "  $(BLUE)%-34s$(RESET) %s\n" "make back"     "Вернуться на ветку lite-selfhosted"
	@echo ""
	@echo "Календари сервисного аккаунта:"
	@printf "  $(BLUE)%-34s$(RESET) %s\n" "make cal-help"  "Справка по командам календарей"
	@printf "  $(BLUE)%-34s$(RESET) %s\n" "make cal-list"  "Список календарей сервисного аккаунта"
	@printf "  $(BLUE)%-34s$(RESET) %s\n" "make cal-add CAL_ID=..." "Добавить календарь в список SA (календарь должен быть расшарен)"
	@printf "  $(BLUE)%-34s$(RESET) %s\n" "make cal-remove CAL_ID=..." "Удалить календарь из списка SA (не удаляет календарь глобально)"
	@echo ""
