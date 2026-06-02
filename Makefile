.PHONY: install test run ui help

HOST ?= 127.0.0.1
PORT ?= 8501

install:
	python3 -m venv .venv
	.venv/bin/python scripts/bootstrap_venv.py --project-root . --with dev

test:
	.venv/bin/python -m pytest -q

run:
	.venv/bin/python -m github_dev_metrics.cli $(ARGS)

ui:
	.venv/bin/python -m github_dev_metrics.web_app --host $(HOST) --port $(PORT)

help:
	@printf '%s\n' \
		'Targets:' \
		'  make install  Create .venv and install the package plus test dependencies' \
		'  make test     Run the test suite from .venv' \
		'  make run      Run the CLI, pass arguments with ARGS="..."' \
		'  make ui       Start the local web UI, override HOST and PORT as needed' \
		'  make help     Show this help'
