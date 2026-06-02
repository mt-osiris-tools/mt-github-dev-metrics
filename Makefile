.PHONY: install test ui

HOST ?= 127.0.0.1
PORT ?= 8501

install:
	python3 -m venv .venv
	.venv/bin/python scripts/bootstrap_venv.py --project-root . --with dev

test:
	.venv/bin/python -m pytest -q

ui:
	.venv/bin/python -m github_dev_metrics.web_app --host $(HOST) --port $(PORT)
