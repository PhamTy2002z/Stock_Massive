# Backend: user Settings (27/09/2026)

Status: done and ready for an api restart. The coordinator does the restart. Nothing is committed.

## Routes (all under `/api/v1`, all authenticated)

| Method + path | Body / query | Response |
|---|---|---|
| `GET /auth/me` | – | `UserResponse`, which now carries `preferences` |
| `PATCH /auth/me` | `UpdateMeRequest` | 200 `UserResponse`; 422 on validation failure |
| `POST /auth/password` | `{current_password, new_password}` | 200 `TokenPair`; 400 `"Current password is incorrect"`; 422 if the new password is the same as the current one, shorter than 8, or longer than 72 bytes |
| `POST /auth/logout-all` | – | 204 |
| `GET /memory/facts?limit=50&offset=0` | limit 1..100, offset ≥ 0 | `{items: [{id,title,body,symbol,source_url,source_name,as_of,created_at}], total}`, newest first |
| `DELETE /memory/facts/{id}` | – | 204, or 404 when the note is missing or belongs to someone else |
| `DELETE /memory/facts` | – | 200 `{deleted}` |
| `DELETE /threads` | – | 200 `{deleted}` |

## Schemas

- `UserPreferences` (extra forbid) has four fields: `nickname` (≤64), `investing_style` (`long_term|growth|dividend|swing|learning`), `custom_instructions` (≤1500) and `memory_enabled` (default true). `from_stored()` checks each stored key on its own. Unknown keys are ignored, and a key with an invalid value falls back to its default.
- `UpdateMeRequest` / `UserPreferencesPatch`: only the keys the client sends are written (`model_fields_set`), and strings are stripped.
  - `full_name` must be 1..255 characters after stripping. An empty string is a 422, and `null` clears the name.
  - For `nickname` and `custom_instructions`, an empty string is stored as null.
  - `memory_enabled: null` means "leave unchanged", the same rule `pinned` follows on `PATCH /threads/{id}`.
- `source_url` in a memory fact is `null` when the note came from the conversation. The stored value in that case is the placeholder `memory://conversation`, which is not a page anyone could open.

## Migration and backups

- Revision `ce858b22360a` (down: `e6a21b7c4d90`) adds `users.preferences JSONB NOT NULL DEFAULT '{}'`. It has been applied to the Docker DB, and `alembic current` there reports `ce858b22360a (head)`.
- Docker DB backup: `backups/stockmassive-before-user-preferences-20260927-133109.dump` (pg_dump -Fc, 28 TABLE DATA entries).
- Host DB (Homebrew Postgres, used by pytest) backup: `backups/hostdb-before-user-preferences-20260927-133146.dump`. The column on that DB was added by the user with an ALTER.

## Prompt

- `PROMPT_VERSION` goes from 5.4.0 to 5.5.0.
- `RuntimeContext` gains `investing_style` and `custom_instructions`. `_runtime` now uses `nickname or full_name` for the name.
- The runtime tail gets two new lines in fixed order after `user_name`: `- investing_style:` and `- user_instructions:`.
- `sanitise_instructions` works in this order:
  1. NFKC normalisation and removal of invisible characters.
  2. Removal of control characters and of `< > { }`.
  3. Collapsing all whitespace, newlines included, to single spaces.
  4. A cap of 1500 characters.
  5. A threat-pattern check: on any finding the instructions are dropped for that Turn, and a warning logs only the finding names.
- New prose was added to the CONTEXT and MEMORY sections, kept as short as possible because of the token ceiling in `test_agent_context_engine`.

## Memory toggle

The switch is enforced inside the `remember_fact` and `recall_facts` handlers. When it is off, they return a normal result with `reason: "memory_disabled"` and write nothing. The tools stay on the Turn's tool list because taking them off would mean changing `turns.py`, `loop.py` and `registry.py`, and this change was not allowed to touch those files.

## Tests

- New: `tests/test_user_settings.py` (23 tests, run on its own throwaway DB). `tests/test_agent_prompt.py` has 14 new tests and its version pin now says 5.5.0.
- Full suite: `make test` gives 2764 passed, 3 deselected. `python -m compileall -q src tests` is clean.
