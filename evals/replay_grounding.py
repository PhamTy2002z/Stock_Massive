"""Re-decide a stored Turn's answer with the grounding code in the working tree.

    cd apps/api && .venv/bin/python ../../evals/replay_grounding.py ../../evals/runs/r1

The stored tool results are what the model was shown (a long result is a preview), so both
passes see the same, possibly shorter, sources: compare the two columns, not either with the
live Turn. "before" disables the table-header context to stand in for the previous code.
"""

import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, ".")
from src.agent.evidence import grounding  # noqa: E402
from src.agent.messages import ToolCallStatus, TurnToolCall  # noqa: E402


def calls(turn):
    return [
        TurnToolCall(id=c["tool_call_id"] or str(c["id"]), name=c["tool_name"], arguments=c["arguments"] or {},
                     status=ToolCallStatus.OK if c["status"] == "ok" else ToolCallStatus.ERROR,
                     result_text=(c["result"] or {}).get("text"))
        for c in turn["tool_calls"]
    ]


def raw(text):
    body = re.split(r"\n-{3,}\s*\n+\*\*Nguồn số liệu\*\*", text)[0]
    return re.sub(r" ?\[(?:\d{1,3} · [^\]\n]{1,80}|chưa kiểm chứng)\]", "", body)


def run(turn, header):
    saved = grounding._table_header
    if not header:
        grounding._table_header = lambda *a: None
    try:
        src = grounding.collect_sources(calls(turn), user_text=turn["question"]["text"])
        today = date.fromisoformat(turn["turn"]["started_at"][:10])
        rep = grounding.check_answer(grounding.normalise(raw(turn["response"].get("answer") or turn["response"]["text"])), src, today=today)
        return {(f.start, f.text): (f.status.value, f.reason, str(f.source_date)) for f in rep.figures}
    finally:
        grounding._table_header = saved


for p in sorted(Path(sys.argv[1]).glob("[AN]*.full.json")):
    t = json.loads(p.read_text())
    if not (t.get("response") or {}).get("text"):
        continue
    before, after = run(t, False), run(t, True)
    changed = [(k, before.get(k), after.get(k)) for k in after if before.get(k) != after.get(k)]
    nb = sum(v[0] == "unverified" for v in before.values())
    na = sum(v[0] == "unverified" for v in after.values())
    print(f"{p.stem.split(".")[0]}: figures={len(after)} unverified {nb} -> {na}; changed {len(changed)}")
    for (start, text), b, a in changed:
        print(f"    {text!r}: {b} -> {a}")
