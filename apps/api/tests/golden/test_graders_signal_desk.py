from __future__ import annotations

import copy
import uuid
from types import SimpleNamespace

import pytest
from golden import graders_signal_desk as graders


def _case() -> dict:
    from src.studies import composer, contracts, grammar, lint

    frame = {
        "kind": "table",
        "columns": ["label", "a", "b", "c"],
        "rows": [["FPT", 123.0, 456.0, 789.0]],
        "unit": None,
        "labels": {"label": "Mã", "a": "A", "b": "B", "c": "C"},
        "columnRoles": {},
        "pointRoles": [],
        "cellRoles": [],
    }
    arguments = {
        "title": "FPT profile",
        "archetype": "profile",
        "kpis": [
            {"label": name.upper(), "value": {"frame_id": "f0", "column": name, "row": 0}}
            for name in ("a", "b", "c")
        ],
        "sections": [
            {
                "heading": "Overview",
                "blocks": [
                    {"kind": "visual", "frame_id": "f0"},
                    {
                        "kind": "caption",
                        "template": "A là {a}.",
                        "refs": {"a": {"frame_id": "f0", "column": "a", "row": 0}},
                    },
                ],
            }
        ],
        "appendix_frame_id": None,
    }
    board = grammar.parse(arguments)
    compiled = composer.compile_board(board, {"f0": frame}, {"f0": {"source": "store"}})
    report = lint.score(compiled.sections, len(compiled.kpis))
    spec = contracts.BoardSpec(
        title=board.title,
        archetype="profile",
        kpis=compiled.kpis,
        sections=compiled.sections,
        appendix=compiled.appendix,
        lint=report.to_payload(),
        auto_composed=False,
    ).to_payload()
    composition = {
        "artifact_id": "artifact-1",
        "spec": spec,
        "frames": {"f0": frame},
        "frame_metadata": [
            {
                "key": "f0",
                "kind": "table",
                "columns": list(frame["columns"]),
                "row_count": 1,
                "unit": None,
                "source": "store",
            }
        ],
        "replay_arguments": arguments,
    }
    composition["ref_proof"] = graders.build_ref_proof(composition)
    composition["replay_proof"] = graders.build_replay_proof(composition)
    return {
        "id": "sd-001",
        "mode": "signal_desk",
        "expect": {"board": True, "min_kpi": 3, "archetype": "profile"},
        "composition": composition,
        "model_visible_text": "Question and shape-only summaries",
        "tool_calls": [
            {
                "id": "ev-1",
                "name": "frame_from_evidence",
                "kind": "store",
                "arguments": {"rows": [{"label": "x", "value": 9}]},
                "result_text": '{"matched":1,"refusedCount":0}',
            },
            {
                "id": "compute-1",
                "name": "compute",
                "kind": "store",
                "arguments": {"code": "result = frames[0]"},
                "result_text": '{"frameId":"computed"}',
            },
        ],
        "cost": {"micro_usd": 100},
        "turn": {"wall_ms": 250},
    }


def test_fixed_graders_pass_and_each_has_a_real_failure() -> None:
    case = _case()
    assert all(getattr(graders, f"grade_{name}")(case).passed for name in graders.FIXED_GRADERS)

    broken = copy.deepcopy(case)
    broken["composition"] = None
    assert graders.grade_board_present(broken).passed is False

    broken = copy.deepcopy(case)
    broken["composition"]["frames"]["f0"]["rows"][0][1] = 124.0
    assert graders.grade_refs_resolve(broken).passed is False

    broken = copy.deepcopy(case)
    broken["model_visible_text"] = "the hidden frame contained 123.0"
    assert graders.grade_frames_absent(broken).passed is False

    broken = copy.deepcopy(case)
    broken["tool_calls"][1]["arguments"]["code"] = "result = frames[0] * 0.07"
    assert graders.grade_compute_literal_free(broken).passed is False

    broken = copy.deepcopy(case)
    broken["tool_calls"][0]["result_text"] = '{"matched":0,"refusedCount":1}'
    assert graders.grade_evidence_on_page(broken).passed is False

    broken = copy.deepcopy(case)
    broken["composition"]["spec"]["title"] = "mutated after proof"
    assert graders.grade_replay_identical(broken).passed is False


def test_expectations_are_case_owned_and_can_pass_or_fail() -> None:
    case = _case()
    assert graders.grade_expect_board(case).passed is True
    assert graders.grade_expect_min_kpi(case).passed is True
    assert graders.grade_expect_archetype(case).passed is True

    case["expect"] = {
        "board": False,
        "min_kpi": 9,
        "archetype": "comparison",
        "refusal": "not_in_store",
    }
    assert graders.grade_expect_board(case).passed is False
    assert graders.grade_expect_min_kpi(case).passed is False
    assert graders.grade_expect_archetype(case).passed is False
    assert graders.grade_expect_refusal(case).passed is False

    case["tool_calls"].append(
        {
            "id": "refusal",
            "name": "query",
            "kind": "store",
            "arguments": {},
            "result_text": '{"error":"not_in_store"}',
        }
    )
    assert graders.grade_expect_refusal(case).passed is True


def test_metric_graders_measure_without_becoming_case_gates() -> None:
    case = _case()
    findings = {finding.grader: finding for finding in graders.grade_case(case)}
    assert findings["visual_ratio"].value == 0.5
    assert findings["narrative_chars"].value == len("A là {a}.")
    assert findings["kpi_count"].value == 3
    assert findings["widget_variety"].value == 1
    assert findings["auto_composed_rate"].value == 0
    assert findings["cost_micro_usd"].value == 100
    assert findings["latency"].value == 250
    assert findings["external_calls"].value == 0
    assert all(findings[name].passed is None for name in graders.METRIC_GRADERS)


def test_signal_desk_dispatch_preserves_fixed_and_cost_gates() -> None:
    from golden.grade import grade

    report = grade(
        {
            "schema": "golden.artifact@1",
            "run": {"status": "complete", "mode": "signal_desk", "corpus_cases": 1},
            "cases": [_case()],
        }
    )
    gate = report.run["signal_desk_gate"]
    assert gate["fixed_invariants_pass"] is True
    assert gate["case_pass_rate"] == 1.0
    assert gate["cost_ceiling_micro_usd"] == 84_362
    assert gate["passed"] is True


def test_runner_maps_signal_desk_to_the_persisted_turn_mode() -> None:
    from golden.run import _turn_mode
    from src.agent.loop import CHAT_MODE, SIGNAL_DESK_MODE

    assert _turn_mode("web_first") == CHAT_MODE
    assert _turn_mode("signal_desk") == SIGNAL_DESK_MODE


@pytest.mark.asyncio
async def test_signal_desk_projection_reads_public_persisted_seams(monkeypatch) -> None:
    from golden.run import read_case

    source = _case()
    composition = source["composition"]
    arguments = composition["replay_arguments"]
    artifact_id = uuid.uuid4()
    call_id = "render-1"
    message = SimpleNamespace(
        role="assistant",
        content={
            "answer": "Board ready",
            "status": "complete",
            "signal_desks": [{"artifact_id": str(artifact_id), "title": "FPT profile"}],
            "tool_calls": [
                {
                    "id": call_id,
                    "name": "render_signal_desk",
                    "round": 0,
                    "status": "ok",
                    "kind": "store",
                    "results": [],
                }
            ],
        },
    )
    trace = SimpleNamespace(
        tool_call_id=call_id,
        arguments=arguments,
        result={"text": f'{{"artifactId":"{artifact_id}"}}'},
    )
    artifact = SimpleNamespace(
        id=artifact_id,
        study_name="composed_signal_desk",
        study_version=1,
        signal_desk_spec=composition["spec"],
        frames=composition["frames"],
        provenance={"source": "store"},
    )

    class Store:
        async def read_thread(self, _user_id, _thread_id):
            return SimpleNamespace(messages=(message,))

        async def traces_for_request(self, _request_message_id):
            return (trace,)

        async def read_artifact(self, _user_id, wanted):
            return artifact if wanted == str(artifact_id) else None

    monkeypatch.setattr("golden.run.spend_for", lambda _message_id: {"micro_usd": 7})
    projected = await read_case(
        Store(),
        case={"id": "sd-001", "question": "FPT?", "expect": {"board": True}},
        user_id=1,
        thread_id=uuid.uuid4(),
        turn_id=uuid.uuid4(),
        request_message_id=1,
        wall_ms=3,
        mode="signal_desk",
    )

    assert projected["mode"] == "signal_desk"
    assert projected["signal_desks"][0]["artifact_id"] == str(artifact_id)
    assert projected["tool_calls"][0]["arguments"] == arguments
    assert projected["composition"]["spec"]["specVersion"] == 2
    assert projected["composition"]["ref_proof"]["all_resolved"] is True
    assert projected["composition"]["replay_proof"]["identical"] is True
    assert "rows" not in {key for key in projected if key != "composition"}
