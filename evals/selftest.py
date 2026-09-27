"""Ask the running Agent a round of questions as the selftest account, then dump each Turn's log.

    SELFTEST_PASSWORD=... apps/api/.venv/bin/python evals/selftest.py ask  evals/questions/r1.json evals/runs/r1
    apps/api/.venv/bin/python evals/selftest.py dump <turn_id> evals/runs/r1/X.json

The selftest account *is* the tag: every selftest Turn lives under its user id, so it never
mixes with a real reader's Threads (CreateTurnRequest has no tag field and is extra="forbid").
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

API = "http://localhost:8000/api/v1"
EMAIL = "selftest.agent@example.com"
# The selftest account is local to the dev database; its password is not kept in the repo.
PASSWORD = os.environ["SELFTEST_PASSWORD"]
ROOT = Path(__file__).resolve().parent.parent


def token() -> str:
    body = {"email": EMAIL, "password": PASSWORD}
    r = httpx.post(f"{API}/auth/login", json=body, timeout=30)
    if r.status_code == 401:
        r = httpx.post(f"{API}/auth/register", json={**body, "full_name": "selftest"}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def psql_json(sql: str):
    out = subprocess.run(
        ["docker", "compose", "exec", "-T", "db", "psql", "-U", "postgres", "-d", "stockmassive", "-At", "-c", sql],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.strip()
    return json.loads(out) if out else None


def dump(turn_id: str) -> dict:
    """Everything the grader needs about one Turn, straight from the database."""
    return psql_json(f"""
    select json_build_object(
      'turn', (select row_to_json(t) from (select id, thread_id, status, terminal_reason, started_at, finished_at
               from agent_turn where id='{turn_id}') t),
      'question', (select m.content from agent_turn t join agent_message m on m.id=t.request_message_id where t.id='{turn_id}'),
      'response', (select m.content from agent_turn t join agent_message m on m.id=t.response_message_id where t.id='{turn_id}'),
      'tool_calls', (select coalesce(json_agg(row_to_json(c) order by c.id), '[]') from (
               select c.id, c.tool_name, c.tool_call_id, c.arguments, c.result, c.status, c.error, c.latency_ms, c.started_at
               from agent_tool_call c join agent_turn t on t.request_message_id=c.request_message_id
               where t.id='{turn_id}') c),
      'ledger', (select row_to_json(l) from (select policy_version, payload from agent_claim_ledger where turn_id='{turn_id}') l),
      'trajectory_stages', (select coalesce(json_agg(stage order by id), '[]') from agent_evidence_trajectory where turn_id='{turn_id}')
    )""")


def ask_one(tok: str, q: dict, out_dir: Path) -> dict:
    h = {"Authorization": f"Bearer {token()}"}
    with httpx.Client(timeout=60, headers=h) as c:
        th = c.post(f"{API}/threads", json={"title": f"selftest {out_dir.name} {q['id']}"})
        th.raise_for_status()
        turn_id = str(uuid.uuid4())
        body = {"turn_id": turn_id, "text": q["text"], "mode": q.get("mode", "chat")}
        r = c.post(f"{API}/threads/{th.json()['id']}/turns", json=body)
        r.raise_for_status()
        t0 = time.time()
        while True:
            time.sleep(5)
            try:
                resp = c.get(f"{API}/turns/{turn_id}")
                if resp.status_code == 401:  # the access token is short-lived
                    c.headers["Authorization"] = f"Bearer {token()}"
                    continue
                s = resp.json()
            except (httpx.HTTPError, ValueError):
                continue
            if s["status"] not in ("admitted", "running"):
                break
            if time.time() - t0 > 3900:
                break
    data = dump(turn_id)
    data["meta"] = {**q, "elapsed_s": round(time.time() - t0)}
    (out_dir / f"{q['id']}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1))
    print(f"{q['id']} {turn_id} {s['status']} {s.get('terminal_reason')} {data['meta']['elapsed_s']}s", flush=True)
    return data


def ask(questions_path: str, out_dir: str, workers: int = 2) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    qs = json.loads(Path(questions_path).read_text())
    tok = token()
    # ponytail: 2 Turns at once — the vnstock quota (48/min with the key) is the real ceiling.
    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(lambda q: ask_one(tok, q, out), qs))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "ask":
        ask(sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 2)
    elif cmd == "dump":
        Path(sys.argv[3]).write_text(json.dumps(dump(sys.argv[2]), ensure_ascii=False, indent=1))
