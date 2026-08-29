# API Development Commands

.PHONY: dev run test lint clean contracts smoke-signal-desk backfill-daily

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
	$(PYTHON) -c "import json;from src.studies import widgets;print(json.dumps(widgets.catalog_payload(),ensure_ascii=False,indent=2))" > ../../contracts/signal-desk-widget-catalog.json
	$(PYTHON) -m tests.studies.artifact_fixture > ../../contracts/fixtures/artifact-intraday-liquidity.json

# Five real questions against a running deployment: does the model reach for
# run_study, and where do the seconds go. Spends real model calls, so it is run
# by hand and never in CI. Needs SMOKE_EMAIL and SMOKE_PASSWORD.
smoke-signal-desk:
	$(PYTHON) -m scripts.smoke_signal_desk

# Does the configured route actually read an image, measured through the same
# serializer production uses. Spends three real model calls, so it is run by
# hand and never in CI. Turn LLM_VISION_ENABLED on only after this passes, and
# copy the model it passed on into LLM_VISION_MEASURED_MODEL.
probe-vision:
	$(PYTHON) -m scripts.probe_vision

# Fill the daily spine the Trading Day calendar is derived from. This is the
# one way bar_daily stays current: there is no scheduler inside the app, so it
# is driven from outside, after the close.
#
#   make backfill-daily SCOPE=index      # VNINDEX — defines the calendar
#   make backfill-daily SCOPE=declared   # the 30 Universe symbols
#   make backfill-daily SCOPE=market     # every listed share, 52 weeks
#
# Run index first: every other scope's window ends on a day the calendar names.
# The run exits non-zero when a symbol failed *or* when the spine is still not
# current afterwards, so cron reports a market that has stopped moving instead
# of succeeding quietly. A crontab entry at 16:00 Asia/Ho_Chi_Minh, weekdays:
#
#   0 16 * * 1-5 cd <repo>/apps/api && make backfill-daily SCOPE=index && \
#                make backfill-daily SCOPE=declared
backfill-daily:
	@test -n "$(SCOPE)" || (echo "SCOPE=index|declared|market is required" >&2; exit 2)
	$(PYTHON) -m src.stocks.backfill_daily --scope "$(SCOPE)" $(if $(SESSIONS),--sessions "$(SESSIONS)",)

# Type check
lint:
	$(PYTHON) -m py_compile src/main.py

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
