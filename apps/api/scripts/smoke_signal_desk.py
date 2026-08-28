"""Five real questions against a running deployment, and where the time goes.

Two things this measures that nothing in the suite can.

**Whether the model finds the tool.** The suite proves ``run_study`` works when
it is called; it cannot prove a model reaches for it. The chain worth having is
one round of ``run_study`` and one of prose, and the thing that breaks it is a
question phrased differently from the one the description was written against.
So the five questions below are deliberately not paraphrases of each other.

**Where the seconds go.** The plan budgets question → ``signal_desk.ready`` at eight
seconds on a warm store and twelve on a cold one, and the only honest way to
know is to read the timestamps off a real stream. The route's own latency is
part of that number and is not separable here — which is the point: a budget
that excluded the slowest component would not be a budget.

Run by hand against a dev deployment. It spends real money on real model calls,
so it is not in the suite and not in CI.

    export SMOKE_EMAIL=… SMOKE_PASSWORD=…
    make smoke-signal-desk                     # or: python -m scripts.smoke_signal_desk

``SMOKE_BASE`` overrides the API root (default ``http://127.0.0.1:8000/api/v1``).
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from dataclasses import dataclass, field

import httpx

BASE = os.environ.get("SMOKE_BASE", "http://127.0.0.1:8000/api/v1")
EMAIL = os.environ.get("SMOKE_EMAIL", "")
PASSWORD = os.environ.get("SMOKE_PASSWORD", "")

#: The five, and why each one is here.
#:
#: One names the study's own vocabulary; one asks for the picture without naming
#: an analysis; one asks in the words a trader uses; one asks for a chart
#: outright; and one is a question about a *number*, which ``run_study`` should
#: not answer — a run there is a false positive, and the score has to be able to
#: catch that as well as a miss.
QUESTIONS = (
    ("Thanh khoản của STB tập trung vào khung giờ nào?", True),
    ("STB 30 phiên gần đây khung giờ nào khớp mạnh nhất?", True),
    ("Vẽ cho tôi biểu đồ thanh khoản trong phiên của SHS", True),
    ("Buổi sáng hay buổi chiều STB giao dịch nhiều hơn?", True),
    ("ADTV của STB là bao nhiêu?", False),
)


@dataclass
class Timeline:
    """When each thing happened, measured from the moment the question went out."""

    question: str
    expected_study: bool
    started: float = field(default_factory=time.monotonic)
    admitted: float | None = None
    first_tool: float | None = None
    signal_desk: float | None = None
    completed: float | None = None
    study_calls: list[dict] = field(default_factory=list)
    other_calls: list[str] = field(default_factory=list)

    def at(self, moment: float | None) -> str:
        return "—" if moment is None else f"{moment - self.started:5.1f}s"

    @property
    def scored(self) -> bool:
        """Whether the model did the right thing with this question."""
        ran = bool(self.study_calls)
        return ran is self.expected_study


def login(client: httpx.Client) -> dict[str, str]:
    if not EMAIL or not PASSWORD:
        sys.exit("set SMOKE_EMAIL and SMOKE_PASSWORD to an account on this deployment")
    response = client.post(
        f"{BASE}/auth/login", json={"email": EMAIL, "password": PASSWORD}
    )
    response.raise_for_status()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def ask(client: httpx.Client, auth: dict[str, str], thread_id: str, question: str,
        expected_study: bool) -> Timeline:
    """Send one question and follow its stream to a terminal event."""
    timeline = Timeline(question=question, expected_study=expected_study)
    turn_id = str(uuid.uuid4())
    created = client.post(
        f"{BASE}/threads/{thread_id}/turns",
        json={"turn_id": turn_id, "text": question, "symbols": []},
        headers=auth,
    )
    created.raise_for_status()
    timeline.admitted = time.monotonic()

    with client.stream(
        "GET", f"{BASE}/turns/{turn_id}/events", headers=auth, timeout=120
    ) as stream:
        for line in stream.iter_lines():
            if not line.startswith("data:"):
                continue
            event = json.loads(line[5:].strip())
            kind, data = event.get("type"), event.get("data") or {}
            if kind == "tool.call":
                if timeline.first_tool is None:
                    timeline.first_tool = time.monotonic()
                if data.get("name") == "run_study":
                    timeline.study_calls.append(dict(data))
                elif data.get("name"):
                    timeline.other_calls.append(str(data["name"]))
            elif kind == "signal_desk.ready":
                timeline.signal_desk = time.monotonic()
            elif kind and kind.startswith("turn.") and kind != "turn.snapshot":
                timeline.completed = time.monotonic()
                break
    return timeline


def main() -> int:
    with httpx.Client(timeout=30) as client:
        auth = login(client)
        thread = client.post(f"{BASE}/threads", json={"title": "smoke signal desk"},
                             headers=auth)
        thread.raise_for_status()
        thread_id = thread.json()["id"]

        results = [
            ask(client, auth, thread_id, question, expected)
            for question, expected in QUESTIONS
        ]

    print(f"{'admitted':>9} {'tool':>6} {'signal_desk':>7} {'done':>6}  question")
    for line in results:
        print(
            f"{line.at(line.admitted):>9} {line.at(line.first_tool):>6} "
            f"{line.at(line.signal_desk):>7} {line.at(line.completed):>6}  "
            f"{'ok ' if line.scored else 'MISS'} {line.question}"
        )
        if line.study_calls:
            for call in line.study_calls:
                print(f"{'':>32}↳ {call.get('summary') or call.get('name')}")
        elif line.other_calls:
            print(f"{'':>32}↳ called instead: {', '.join(line.other_calls)}")

    scored = sum(1 for line in results if line.scored)
    print(f"\ntool choice: {scored}/{len(results)} (budget: 4/5)")
    drawn = [line for line in results if line.signal_desk is not None]
    if drawn:
        slowest = max(line.signal_desk - line.started for line in drawn)  # type: ignore[operator]
        print(f"slowest question → signal_desk.ready: {slowest:.1f}s (budget: 8s warm, 12s cold)")
    return 0 if scored >= 4 else 1


if __name__ == "__main__":
    raise SystemExit(main())
