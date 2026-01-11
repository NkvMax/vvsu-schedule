# make/calendars.mk — Вспомогательные функции предназначены для управления календарями для служебной учетной записи.
#
# Usage:
#   make cal-list
#   make cal-add CAL_ID="...@group.calendar.google.com"
#   make cal-remove CAL_ID="...@group.calendar.google.com"
#
# Optional:
#   make cal-list SA_JSON=/path/to/service_account.json

CAL_MK_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
CAL_REPO_ROOT := $(abspath $(CAL_MK_DIR)/..)

SA_JSON ?= $(CAL_REPO_ROOT)/credentials/service_account.json
PY ?= $(if $(wildcard $(CAL_REPO_ROOT)/.venv/bin/python),$(CAL_REPO_ROOT)/.venv/bin/python,python3)

.PHONY: cal-help cal-list cal-add cal-remove

cal-help:
	@echo "Calendar tools:"
	@echo "  make cal-list [SA_JSON=...]"
	@echo "  make cal-add CAL_ID=... [SA_JSON=...]"
	@echo "  make cal-remove CAL_ID=... [SA_JSON=...]   (remove from SA CalendarList, not delete globally)"

SRC_DIR := $(CAL_REPO_ROOT)/src/vvsu_lite

cal-list:
	@$(PY) $(SRC_DIR)/check_calendars.py --sa "$(SA_JSON)"

cal-add:
	@test -n "$(CAL_ID)" || (echo "Set CAL_ID=..."; exit 2)
	@$(PY) $(SRC_DIR)/add_calendar_to_sa.py --sa "$(SA_JSON)" add "$(CAL_ID)" --verify

cal-remove:
	@test -n "$(CAL_ID)" || (echo "Set CAL_ID=..."; exit 2)
	@$(PY) $(SRC_DIR)/add_calendar_to_sa.py --sa "$(SA_JSON)" remove "$(CAL_ID)" --yes
