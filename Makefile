.DEFAULT_GOAL := help

SHELL := bash
.SHELLFLAGS := -euo pipefail -c

ROOT := $(CURDIR)
ENV_FILE ?= $(ROOT)/.env

PYTHON ?= python3

VENV_AUDIO ?= $(ROOT)/.venv_audio
VENV_CRM ?= $(ROOT)/.venv_crm
VENV_MS ?= $(ROOT)/.venv_ms
VENV_BOT ?= $(ROOT)/.venv_bot

PROD_SSH ?= cyberdb_admin@10.6.97.25
PROD_PATH ?= /opt/ud-mvp
PROD_BRANCH ?= main

help:
	@echo "Targets:"
	@echo "  build               Create venvs + install deps (runs on current machine)"
	@echo "  start               Start all services via tmux (runs on current machine)"
	@echo "  stop                Stop all services (tmux kill; runs on current machine)"
	@echo "  health              Check local health endpoints (runs on current machine)"
	@echo "  test                Run unit/integration tests (local)"
	@echo "  smoke-pdf           Run PDF pipeline smoke stages (requires REQUEST_DIR=...)"
	@echo "  deploy-old          Deploy to old server via git pull + restart"
	@echo "  deploy-old-hard     Deploy with reset/clean (DANGEROUS)"
	@echo "  health-old          Check health on old server"
	@echo ""
	@echo "Vars (override like: make prod-deploy PROD_SSH=user@host):"
	@echo "  PROD_SSH=$(PROD_SSH)"
	@echo "  PROD_PATH=$(PROD_PATH)"
	@echo "  PROD_BRANCH=$(PROD_BRANCH)"
	@echo "  PYTHON=$(PYTHON)"

.PHONY: help build start stop health test smoke-pdf deploy-old deploy-old-hard health-old

$(VENV_AUDIO)/bin/python:
	$(PYTHON) -m venv $(VENV_AUDIO)

$(VENV_CRM)/bin/python:
	$(PYTHON) -m venv $(VENV_CRM)

$(VENV_MS)/bin/python:
	$(PYTHON) -m venv $(VENV_MS)

$(VENV_BOT)/bin/python:
	$(PYTHON) -m venv $(VENV_BOT)

build: $(VENV_AUDIO)/bin/python $(VENV_CRM)/bin/python $(VENV_MS)/bin/python $(VENV_BOT)/bin/python
	$(VENV_AUDIO)/bin/pip install -U pip wheel setuptools
	$(VENV_CRM)/bin/pip install -U pip wheel setuptools
	$(VENV_MS)/bin/pip install -U pip wheel setuptools
	$(VENV_BOT)/bin/pip install -U pip wheel setuptools
	$(VENV_AUDIO)/bin/pip install -r app-audio/requirements.txt
	$(VENV_CRM)/bin/pip install -r app-crm/requirements.txt
	$(VENV_MS)/bin/pip install -r app-ms/requirements.txt
	$(VENV_BOT)/bin/pip install -r requirements.txt

start:
	./start_all.sh

stop:
	tmux kill-session -t audio 2>/dev/null || true
	tmux kill-session -t crm 2>/dev/null || true
	tmux kill-session -t ms 2>/dev/null || true
	tmux kill-session -t bot 2>/dev/null || true

health:
	curl -fsS http://127.0.0.1:8001/health
	curl -fsS http://127.0.0.1:8010/healthz
	curl -fsS http://127.0.0.1:8000/healthz

test:
	$(VENV_MS)/bin/python -m pytest -q app-ms/tests tests/unit
	$(VENV_CRM)/bin/python -m pytest -q tests/app_crm app-crm/scripts/test_append_sheet.py

smoke-pdf:
	@if [[ -z "$${REQUEST_DIR:-}" ]]; then echo "Set REQUEST_DIR=/path/to/request_dir"; exit 2; fi
	PYTHONPATH=app-ms $(VENV_MS)/bin/python app-ms/scripts/smoke_pdf_stages.py --request-dir "$$REQUEST_DIR" --stage all

deploy-old:
	ssh $(PROD_SSH) 'set -euo pipefail; cd $(PROD_PATH); git remote -v; git fetch origin; git pull --ff-only origin $(PROD_BRANCH); bash ./start_all.sh'

deploy-old-hard:
	@echo "WARNING: this will reset and delete untracked files in $(PROD_PATH) on $(PROD_SSH)"
	ssh $(PROD_SSH) 'set -euo pipefail; cd $(PROD_PATH); git fetch origin; git reset --hard origin/$(PROD_BRANCH); git clean -fd; bash ./start_all.sh'

health-old:
	ssh $(PROD_SSH) 'set -euo pipefail; curl -fsS http://127.0.0.1:8001/health; echo; curl -fsS http://127.0.0.1:8010/healthz; echo; curl -fsS http://127.0.0.1:8000/healthz; echo'
