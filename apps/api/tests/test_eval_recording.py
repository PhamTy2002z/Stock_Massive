"""Phase 2 model and trajectory recording contracts."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.core.llm import (
    Completion,
    CompletionRequest,
    ContextOverflow,
    Message,
    Role,
    ToolCall,
    Usage,
)
from src.eval.recording import (
    RecordingLLMClient,
    RecordingTraceWriter,
    ScriptedLLMClient,
    SingleAttemptEvalLLMClient,
    TrajectoryRecorder,
)

NOW = datetime(2026, 8, 23, 13, 0, tzinfo=timezone.utc)


def request() -> CompletionRequest:
    return CompletionRequest(
        model="eval-session-model",
        messages=(
            Message(role=Role.SYSTEM, content="stable contract"),
            Message(role=Role.USER, content="sk-proj-abcdefghijklmnopqrstuvwxyz"),
        ),
        max_output_tokens=400,
        stream=False,
        metadata={"case_id": "conversation-fpt", "private": "do-not-record"},
    )


@pytest.mark.asyncio
async def test_recording_client_keeps_normalized_success_without_raw_content():
    scripted = ScriptedLLMClient(
        [
            Completion(
                model="eval-session-model",
                text="The private answer is intentionally not retained.",
                tool_calls=(
                    ToolCall(
                        id="call-1",
                        name="get_field",
                        arguments={"field_id": "price.close"},
                    ),
                ),
                usage=Usage(input_tokens=12, output_tokens=7),
                finish_reason="tool_calls",
                request_id="req-eval-1",
            )
        ]
    )
    recorder = TrajectoryRecorder(clock=lambda: NOW)
    client = RecordingLLMClient(
        scripted,
        recorder=recorder,
        monotonic=iter((10.0, 10.025)).__next__,
    )

    completion = await client.complete(request())

    assert completion.request_id == "req-eval-1"
    event = recorder.events[0]
    assert event.kind == "model_attempt"
    assert event.payload["status"] == "completed"
    assert event.payload["latency_ms"] == 25
    assert event.payload["usage_tokens"] == 19
    assert event.payload["request_id"] == "req-eval-1"
    assert event.payload["tool_calls"] == [
        {"id": "call-1", "name": "get_field", "arguments": {"field_id": "price.close"}}
    ]
    assert event.payload["request"]["message_roles"] == ["system", "user"]
    assert event.payload["request"]["metadata"] == {"case_id": "conversation-fpt"}
    rendered = repr(event.payload)
    assert "The private answer" not in rendered
    assert "sk-proj-" not in rendered
    assert "do-not-record" not in rendered


@pytest.mark.asyncio
async def test_recording_client_reraises_the_same_typed_failure():
    failure = ContextOverflow("Bearer should-not-survive")
    recorder = TrajectoryRecorder(clock=lambda: NOW)
    client = RecordingLLMClient(
        ScriptedLLMClient([failure]),
        recorder=recorder,
        monotonic=iter((20.0, 20.010)).__next__,
    )

    with pytest.raises(ContextOverflow) as raised:
        await client.complete(request())

    assert raised.value is failure
    assert recorder.events[0].payload == {
        "status": "failed",
        "request": {
            "model": "eval-session-model",
            "message_roles": ["system", "user"],
            "message_chars": [15, 34],
            "tools": [],
            "tool_choice": "auto",
            "parallel_tool_calls": True,
            "response_format": None,
            "max_output_tokens": 400,
            "temperature": None,
            "stream": False,
            "metadata": {"case_id": "conversation-fpt"},
        },
        "latency_ms": 10,
        "error_type": "ContextOverflow",
        "error": "[REDACTED]",
        "usage_tokens": 0,
    }


@pytest.mark.asyncio
async def test_single_attempt_eval_client_never_retries_empty_completion():
    class Admission:
        reservations = 0
        reconciliations = 0

        def reserve(self, _spend, _model):
            self.reservations += 1
            return "reservation-1"

        def reconcile(self, _reservation, _usage):
            self.reconciliations += 1

    class Transport:
        dispatches = 0

        async def dispatch(self, _request):
            self.dispatches += 1
            return Completion(
                model="eval-session-model",
                text="",
                usage=Usage(input_tokens=2, output_tokens=0),
            )

    admission = Admission()
    transport = Transport()
    completion = await SingleAttemptEvalLLMClient(
        transport, admission
    ).complete(request(), object())

    assert completion.text == ""
    assert transport.dispatches == 1
    assert admission.reservations == 1
    assert admission.reconciliations == 1


@pytest.mark.asyncio
async def test_tool_trace_records_only_allowed_arguments_and_evidence_references():
    persisted = []

    async def write(trace):
        persisted.append(dict(trace))
        return "stored"

    recorder = TrajectoryRecorder(clock=lambda: NOW)
    writer = RecordingTraceWriter(
        write,
        recorder=recorder,
        argument_allowlists={"get_field": frozenset({"field_id"})},
    )
    result = await writer(
        {
            "thread_id": "00000000-0000-0000-0000-000000000001",
            "request_message_id": 9,
            "tool_name": "get_field",
            "tool_call_id": "call-1",
            "arguments": {
                "field_id": "price.close",
                "api_key": "sk-proj-abcdefghijklmnopqrstuvwxyz",
            },
            "result": {
                "text": "untrusted body must not enter the eval trace",
                "chars": 44,
                "dispatched": True,
                "evidence_references": ["snapshot:price-close"],
            },
            "status": "ok",
            "error": None,
            "outcome": "answered",
            "latency_ms": 4,
        }
    )

    assert result == "stored"
    assert len(persisted) == 1
    event = recorder.events[0]
    assert event.kind == "tool_call"
    assert event.payload == {
        "call_id": "call-1",
        "tool_name": "get_field",
        "arguments": {"field_id": "price.close"},
        "status": "ok",
        "outcome": "answered",
        "duration_ms": 4,
        "error": None,
        "evidence_references": ["snapshot:price-close"],
    }
    assert "untrusted body" not in repr(event.payload)
    assert "api_key" not in repr(event.payload)


def test_trajectory_sequence_is_shared_and_stable():
    recorder = TrajectoryRecorder(clock=lambda: NOW)

    first = recorder.emit("guardrail", {"status": "blocked"})
    second = recorder.emit("terminal", {"status": "incomplete"})

    assert (first.seq, second.seq) == (0, 1)
    assert recorder.events == (first, second)


def test_interleaved_analysis_tool_error_is_redacted():
    recorder = TrajectoryRecorder(clock=lambda: NOW)
    recorder.emit(
        "model_attempt",
        {"tool_calls": [{"id": "call-1", "name": "get_field", "arguments": {}}]},
    )
    recorder.interleave_tool_events(
        (
            (
                "call-1",
                {
                    "call_id": "call-1",
                    "tool_name": "get_field",
                    "error": "route echoed sk-proj-abcdefghijklmnopqrstuvwxyz",
                },
                NOW,
            ),
        )
    )

    rendered = repr(recorder.events)
    assert "sk-proj-" not in rendered
    assert "[REDACTED]" in rendered
