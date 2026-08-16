# API Development Commands

.PHONY: dev run test lint clean eval eval-smoke eval-fixture eval-fixture-load eval-rubric

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
# docs/adr/0010 lives here and the Eval Battery does not.
test:
	$(PYTEST) tests/ -v

# The Eval Battery (docs/adr/0016). Separate from `test` because it costs money
# and minutes: `gate` runs the production route under a hard $2.5 ceiling, and
# only a gate run may be attached to a pull request.
#
# Everything below reads EVAL_DATABASE_URL and refuses if it is unset or points
# at the database the API serves from.
eval:
	$(PYTHON) -m src.eval run --mode gate

# The dev route at zero cost. Proves the harness and the deterministic
# assertions still work, and has no gating value.
eval-smoke:
	$(PYTHON) -m src.eval run --mode smoke

# Freeze one Trading Day of the real store into a new seed. Reads DATABASE_URL
# and writes a file; it never writes to the store.
eval-fixture:
	$(PYTHON) -m src.eval capture

# Load the newest seed into the eval database and re-check its properties.
eval-fixture-load:
	$(PYTHON) -m src.eval load

# Combine a filled blind rubric sheet with the run it was written from. Pass the
# sheet a gate run left beside its report:
#
#   make eval-rubric SHEET=docs/eval/2026-08-16-1.2.0.rubric.md
#
# It touches no database. An unfinished sheet is refused rather than defaulted:
# a default is a score nobody gave.
eval-rubric:
	$(PYTHON) -m src.eval rubric --sheet $(SHEET)

# Run specific test file
test-file:
	@read -p "Test file: " file; pytest tests/$$file -v

# Type check
lint:
	python -m py_compile src/main.py

# Clean cache files
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
