"""Re-run a stored Turn's data tools to recover their whole results (the trace keeps a preview).

    docker compose exec -T api python - < evals/refetch_tools.py  # reads a JSON list of calls on stdin? no:

Only the deterministic data tools are re-run (market, statements, company, screen, calculate);
web results stay as stored. `now` is the Turn's start, so "today" windows match the live Turn.
Writes <id>.full.json beside each Turn.
"""

import json
import subprocess
import sys
from pathlib import Path

INNER = r'''
import json, sys
from datetime import datetime
from src.agent.tools import register_all
from src.agent import registry
from src.agent.registry import ToolContext
register_all()
job = json.load(sys.stdin)
now = datetime.fromisoformat(job["now"])
out = {}
for c in job["calls"]:
    entry = registry.get(c["tool_name"])
    try:
        res = entry.handler(ToolContext(now=now), c["arguments"] or {})
        out[str(c["id"])] = json.dumps(res, ensure_ascii=False, default=str) if not isinstance(res, str) else res
    except Exception as e:
        out[str(c["id"])] = None
        print(f"{c['tool_name']}: {type(e).__name__}: {e}", file=sys.stderr)
print(json.dumps(out, ensure_ascii=False))
'''
DATA = {"get_market_data", "get_financial_ratios", "get_company_events", "get_company_news", "screen_stocks", "calculate"}
ROOT = Path(__file__).resolve().parent.parent

for p in sorted(q for q in Path(sys.argv[1]).glob("[AN]*.json") if ".full." not in q.name):
    turn = json.loads(p.read_text())
    calls = [c for c in turn["tool_calls"] if c["tool_name"] in DATA and c["status"] == "ok"]
    if not calls:
        continue
    job = json.dumps({"now": turn["turn"]["started_at"], "calls": calls}, ensure_ascii=False)
    r = subprocess.run(["docker", "compose", "exec", "-T", "api", "python", "-c", INNER], input=job,
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        print(p.stem, "FAILED", r.stderr[-400:])
        continue
    full = json.loads(r.stdout.strip().splitlines()[-1])
    for c in turn["tool_calls"]:
        if full.get(str(c["id"])):
            c["result"] = {"text": full[str(c["id"])]}
    p.with_suffix(".full.json").write_text(json.dumps(turn, ensure_ascii=False, indent=1))
    print(p.stem, "refetched", sum(1 for v in full.values() if v), "of", len(calls), r.stderr.strip()[-200:])
