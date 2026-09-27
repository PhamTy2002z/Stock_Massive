# API Development Commands

.PHONY: dev run test lint clean probe-prompt-cache probe-vision

# Use venv python if exists
PYTHON := $(shell if [ -d ".venv" ]; then echo ".venv/bin/python"; else echo "python"; fi)
UVICORN := $(shell if [ -d ".venv" ]; then echo ".venv/bin/uvicorn"; else echo "uvicorn"; fi)
PYTEST := $(shell if [ -d ".venv" ]; then echo ".venv/bin/pytest"; else echo "pytest"; fi)

# Settings default to ENVIRONMENT=production; these local targets run as
# development unless the caller says otherwise. `run` is left out on purpose:
# it is the production-like one and must be told explicitly.
dev test test-file test-one probe-vision probe-prompt-cache: export ENVIRONMENT ?= development

# Development server with hot reload (recommended)
dev:
	$(UVICORN) src.main:app --reload --reload-dir src --host 0.0.0.0 --port 8000

# Production-like server (no reload)
run:
	$(UVICORN) src.main:app --host 0.0.0.0 --port 8000

# Run tests. Free and offline, which is why the null-calibration harness of
# docs/adr/0010 lives here.
test:
	$(PYTEST) tests/ -v

# Run specific test file
test-file:
	@read -p "Test file: " file; pytest tests/$$file -v

# Run a named subset non-interactively:  make test-one T=tests/test_agent_loop.py -K "tool"
test-one:
	@test -n "$(T)" || (echo "T=<path> is required" >&2; exit 2)
	$(PYTEST) $(T) -q $(if $(K),-k "$(K)",)

# Does the configured route actually read an image, measured through the same
# serializer production uses. Spends three real model calls, so it is run by
# hand and never in CI. Turn LLM_VISION_ENABLED on only after this passes, and
# copy the model it passed on into LLM_VISION_MEASURED_MODEL.
probe-vision:
	$(PYTHON) -m scripts.probe_vision

# Type check
lint:
	$(PYTHON) -m py_compile src/main.py

# Clean cache files
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Does the route's automatic prefix cache read back the head C2 builds. Spends
# real model calls, so it is run by hand and never in CI, and it refuses to
# start without a ceiling. It changes no configuration: it says whether the
# 2026-08-23 measurement still holds now that the prompt has two blocks.
probe-prompt-cache:
	@test -n "$(CEILING_USD)" || (echo "CEILING_USD=<amount> is required" >&2; exit 2)
	$(PYTHON) -m scripts.probe_prompt_cache --ceiling-usd "$(CEILING_USD)" $(PROBE_ARGS)
