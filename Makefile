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
