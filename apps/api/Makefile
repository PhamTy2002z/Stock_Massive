# API Development Commands

.PHONY: dev run test lint clean golden-run golden-grade golden-context-export golden-context-replay probe-prompt-cache probe-vision

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

# The golden harness (apps/api/golden). Running and grading are two targets on
# purpose: a run spends real money, and a score has to be repeatable for free.
#
# CEILING_USD has no default and the runner refuses to start without it. The
# whole model envelope is $45 a month, so an unbounded run is not a thing this
# repository knows how to do.
golden-run:
	@test -n "$(CEILING_USD)" || (echo "CEILING_USD is required: a run spends real money" >&2; exit 2)
	$(PYTHON) -m golden.run --ceiling-usd "$(CEILING_USD)" $(if $(MODE),--mode "$(MODE)",) $(GOLDEN_ARGS)

# Rebuild every context one finished run constructed, from its own trace. Two
# halves on purpose: ``golden-context-export`` reads the store once, and
# ``golden-context-replay`` is pure — no network, no model, no clock — so a
# number from before a change and a number from after it differ only by the
# change.
golden-context-export:
	@test -n "$(ARTIFACT)" || (echo "ARTIFACT=<path> is required" >&2; exit 2)
	$(PYTHON) -m golden.context_replay export --artifact "$(ARTIFACT)" $(if $(CORPUS),--out "$(CORPUS)",)

golden-context-replay:
	@test -n "$(OUT)" || (echo "OUT=<path> is required" >&2; exit 2)
	$(PYTHON) -m golden.context_replay replay $(if $(CORPUS),--corpus "$(CORPUS)",) --out "$(OUT)"

# Reads one artifact file. No network, no database, no model.
golden-grade:
	@test -n "$(ARTIFACT)" || (echo "ARTIFACT=path/to/artifact.json is required" >&2; exit 2)
	$(PYTHON) -m golden.grade "$(ARTIFACT)" $(GRADE_ARGS)
