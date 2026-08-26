# API Development Commands

.PHONY: dev run test lint clean eval-validate eval-smoke eval-run eval-compare eval-gate

# Use venv python if exists
PYTHON := $(shell if [ -d ".venv" ]; then echo ".venv/bin/python"; else echo "python"; fi)
UVICORN := $(shell if [ -d ".venv" ]; then echo ".venv/bin/uvicorn"; else echo "uvicorn"; fi)
PYTEST := $(shell if [ -d ".venv" ]; then echo ".venv/bin/pytest"; else echo "pytest"; fi)

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

# Run a named subset non-interactively:  make test-one T=tests/studies -K "refusal"
test-one:
	@test -n "$(T)" || (echo "T=<path> is required" >&2; exit 2)
	$(PYTEST) $(T) -q $(if $(K),-k "$(K)",)

# Regenerate the contract files both apps read. Deterministic: a synthetic
# window and a pinned as-of, so no code change means no diff.
contracts:
	$(PYTHON) -c "import json;from src.studies import widgets;print(json.dumps(widgets.catalog_payload(),ensure_ascii=False,indent=2))" > ../../contracts/canvas-widget-catalog.json
	$(PYTHON) -m tests.studies.artifact_fixture > ../../contracts/fixtures/artifact-intraday-liquidity.json

# Type check
lint:
	python -m py_compile src/main.py

# Clean cache files
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

eval-validate:
	$(PYTHON) -m src.eval validate

eval-smoke:
	$(PYTHON) -m src.eval smoke

eval-run:
	@test -n "$(EVAL_ROUTE)" || (echo "EVAL_ROUTE is required" >&2; exit 2)
	@test -n "$(EVAL_CEILING)" || (echo "EVAL_CEILING is required" >&2; exit 2)
	$(PYTHON) -m src.eval run --route "$(EVAL_ROUTE)" --ceiling "$(EVAL_CEILING)"

eval-compare:
	@test -n "$(EVAL_BASELINE)" || (echo "EVAL_BASELINE is required" >&2; exit 2)
	@test -n "$(EVAL_CANDIDATE)" || (echo "EVAL_CANDIDATE is required" >&2; exit 2)
	$(PYTHON) -m src.eval compare "$(EVAL_BASELINE)" "$(EVAL_CANDIDATE)"

eval-gate:
	@test -n "$(EVAL_ROUTE)" || (echo "EVAL_ROUTE is required" >&2; exit 2)
	@test -n "$(EVAL_CEILING)" || (echo "EVAL_CEILING is required" >&2; exit 2)
	@test -n "$(EVAL_BASELINE)" || (echo "EVAL_BASELINE is required" >&2; exit 2)
	$(PYTHON) -m src.eval gate --route "$(EVAL_ROUTE)" --ceiling "$(EVAL_CEILING)" --baseline-artifact "$(EVAL_BASELINE)"
