"""The replay is only worth its file if it is pure and if it adds up.

Two properties, and both are the kind that fail silently. A replay that reads
the clock produces a different prompt every morning, so a token delta measured
across two days is a delta in the date. And a breakdown whose layers do not sum
to the total the request was charged is a diagnosis of a system nobody ran.

No database and no network here: ``replay`` is a pure function of a corpus, and
this file proves that by handing it one it built itself.
"""

from __future__ import annotations

import json
from datetime import date
from urllib.parse import urlsplit

import pytest

from golden.context_replay import (
    CORPUS_SCHEMA,
    REPLAY_DATE,
    REPLAY_USER_NAME,
    REPORT_SCHEMA,
    replay,
    replay_case,
)
from src.agent.loop import MAX_TOOL_ROUNDS
from src.agent.messages import CONTEXT_LAYERS


RUNTIME = {"today": REPLAY_DATE.isoformat(), "user_name": REPLAY_USER_NAME}


def call(
    identifier: str,
    name: str = "web_search",
    *,
    round_index: int = 0,
    text: str = "kết quả " * 40,
    urls: tuple[str, ...] = ("https://cafef.vn/a",),
    refused: bool = False,
) -> dict[str, object]:
    """One recorded call, shaped the way the web tools actually record one.

    ``result_text`` carries the links inside it, because the real payload does:
    a fixture whose body did not name its own URLs would let the retention
    assertions below pass on a context that had lost every link.
    """
    body = json.dumps(
        {"results": [{"url": url, "text": text} for url in urls]},
        ensure_ascii=False,
    )
    return {
        "id": identifier,
        "name": name,
        "round": round_index,
        "status": "error" if refused else "ok",
        "outcome": None,
        "kind": "external",
        "arguments": {} if refused else {"query": "lãi suất"},
        "result_text": "" if refused else body,
        "refused": refused,
        "results": [
            {"url": url, "title": "t", "source": urlsplit(url).netloc, "snippet": "s"}
            for url in urls
        ],
    }


def corpus(*cases: dict[str, object]) -> dict[str, object]:
    return {
        "schema": CORPUS_SCHEMA,
        "exported_at": "2026-08-29T00:00:00+00:00",
        "source_artifact": "web-first-v1-final.json",
        "identity": {"prompt_version": "3.0.0"},
        "runtime": RUNTIME,
        "cases": list(cases),
    }


def one_case(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": "wf-001",
        "question": "Lãi suất huy động đang bao nhiêu?",
        "family": "web_first",
        "calls": [call("c0"), call("c1", round_index=1)],
    }
    base.update(overrides)
    return base


def test_a_turn_constructs_one_context_per_model_call() -> None:
    """Two rounds of tools is three paid calls, not two."""
    played = replay_case(one_case(), RUNTIME)

    assert played["rounds"] == 2
    assert len(played["constructed"]) == 3
    assert [item["call"] for item in played["constructed"]] == [0, 1, 2]


def test_a_round_sees_only_the_results_that_came_before_it() -> None:
    """The first call has no evidence; every later one has what came back.

    It does not follow that each call is larger than the last, and after the
    ageing rung it usually is not: the third call reads round one's results in
    full and round zero's as a handle, so it can be *smaller* than the second
    while still carrying strictly more of the Turn.
    """
    played = replay_case(one_case(), RUNTIME)
    constructed = played["constructed"]

    assert constructed[0]["source_urls"] == []
    assert constructed[0]["estimated_tokens"] < constructed[1]["estimated_tokens"]
    assert constructed[2]["source_urls"] == ["https://cafef.vn/a"]
    assert constructed[2]["results_collapsed"] == 1


def test_every_constructed_context_has_layers_that_sum_to_its_total() -> None:
    played = replay_case(one_case(), RUNTIME)

    for item in played["constructed"]:
        assert sum(item["composition"].values()) == item["estimated_tokens"]
        assert list(item["composition"]) == list(CONTEXT_LAYERS)


def test_the_replay_reads_no_clock() -> None:
    """The pinned date is in the prompt, so a clock here would move the number."""
    pinned = replay_case(one_case(), RUNTIME)
    tomorrow = replay_case(
        one_case(), {"today": date(2026, 12, 31).isoformat(), "user_name": None}
    )

    assert pinned["constructed"][0]["estimated_tokens"] != (
        tomorrow["constructed"][0]["estimated_tokens"]
    )
    assert replay_case(one_case(), RUNTIME) == pinned


def test_a_domain_call_loads_the_pack_body_from_the_next_call_onward() -> None:
    """The loop reads what the model asked for before dispatching it."""
    played = replay_case(
        one_case(calls=[call("c0", "get_field"), call("c1", round_index=1)]),
        RUNTIME,
    )
    body = [item["composition"]["domain_body"] for item in played["constructed"]]

    assert body[0] == 0
    assert body[1] > 0 and body[1] == body[2]


def test_a_turn_that_never_touches_the_domain_never_pays_for_the_body() -> None:
    played = replay_case(one_case(), RUNTIME)

    assert all(item["composition"]["domain_body"] == 0 for item in played["constructed"])


def test_the_last_call_of_a_turn_that_spent_every_round_carries_the_note() -> None:
    played = replay_case(
        one_case(
            calls=[
                call(f"c{index}", round_index=index)
                for index in range(MAX_TOOL_ROUNDS)
            ]
        ),
        RUNTIME,
    )
    dynamic = [item["composition"]["system_dynamic"] for item in played["constructed"]]

    assert len(dynamic) == MAX_TOOL_ROUNDS + 1
    assert dynamic[-1] > dynamic[-2]


def test_a_refused_call_is_still_part_of_the_context_and_is_counted() -> None:
    """It never reached a tool, and the model was still shown that it asked."""
    played = replay_case(
        one_case(calls=[call("c0"), call("c1", round_index=1, refused=True)]),
        RUNTIME,
    )

    assert played["refused_calls"] == 1
    assert played["calls"] == 2


def test_the_report_totals_are_the_sum_of_its_cases() -> None:
    report = replay(corpus(one_case(), one_case(id="wf-002")))
    totals = report["totals"]

    assert report["schema"] == REPORT_SCHEMA
    assert totals["cases"] == 2
    assert totals["constructed_tokens"] == sum(
        case["constructed_tokens"] for case in report["cases"]
    )
    assert sum(totals["layers"].values()) == totals["constructed_tokens"]


def test_the_report_names_both_identities_so_a_mismatch_is_visible() -> None:
    report = replay(corpus(one_case()))

    assert report["corpus"]["identity"]["prompt_version"] == "3.0.0"
    assert report["replayed_under"]["prompt_version"]
    assert report["replayed_under"]["pack_identity"]


def test_a_corpus_of_another_schema_is_refused_rather_than_guessed_at() -> None:
    with pytest.raises(SystemExit, match=CORPUS_SCHEMA):
        replay({"schema": "golden.artifact@1", "cases": []})


def test_the_exported_corpus_carries_no_identity_of_this_system() -> None:
    """What it must not carry is an account, an id or a credential.

    Not "no email anywhere". The corpus holds the *pages the run read*, and a
    news article's byline is part of the bytes the model was given — scrubbing
    it would change the token count this corpus exists to measure, which is the
    one thing a replay may not do. The tape beside it already holds the same
    text for the same reason.

    What the corpus is not allowed to hold is anything about *this* deployment:
    the runner's account, an owner id, a route, a key. Those are all things the
    export chooses to write, and each of them is asserted absent here.
    """
    from golden.run import GOLDEN_EMAIL

    path = "golden/artifacts/context-replay-v1.json"
    try:
        raw = open(path, encoding="utf-8").read()
    except FileNotFoundError:  # pragma: no cover - only before the first export
        pytest.skip(f"{path} has not been exported")

    exported = json.loads(raw)

    assert GOLDEN_EMAIL not in raw
    assert "@stockmassive" not in raw
    assert "api_key" not in raw and "Bearer " not in raw
    assert "runner_user_id" not in raw and "runner_email" not in raw
    # The one name it carries is the constant in this directory, not a row.
    assert exported["runtime"]["user_name"] == REPLAY_USER_NAME
    assert set(exported["cases"][0]) == {"id", "question", "family", "calls"}
    assert set(exported["identity"]) == {
        "prompt_version",
        "prompt_hash",
        "pack",
        "pack_identity",
        "toolsets",
        "tool_surface",
        "model",
    }


def test_retention_is_measured_on_the_text_the_model_reads() -> None:
    """A handle that kept a link in ``results`` and dropped it from the message
    would pass a check on the projection and be the failure this phase is about.
    """
    played = replay_case(
        one_case(
            calls=[
                call("c0", urls=("https://cafef.vn/a",)),
                call("c1", round_index=1, urls=("https://vnexpress.net/b",)),
                call("c2", "fetch_url", round_index=2, urls=("https://tuoitre.vn/c",)),
            ]
        ),
        RUNTIME,
    )

    for item in played["constructed"]:
        assert item["source_urls_in_context"] == item["source_urls"]
        assert item["intent_in_context"] is True
    assert played["urls_reachable"] == played["urls_offered"]


def test_a_search_result_ages_into_a_handle_and_keeps_its_link() -> None:
    """The saving comes from the prose, and the link is not the prose."""
    played = replay_case(
        one_case(
            calls=[
                call("c0", text="đoạn dài " * 500, urls=("https://cafef.vn/a",)),
                call("c1", "fetch_url", round_index=1),
                call("c2", "fetch_url", round_index=2),
            ]
        ),
        RUNTIME,
    )
    calls = played["constructed"]

    # Read once on call one, a handle from call two onward.
    assert calls[1]["results_collapsed"] == 0
    assert calls[2]["results_collapsed"] == 1
    assert calls[2]["estimated_tokens"] < calls[1]["estimated_tokens"]
    assert "https://cafef.vn/a" in calls[2]["source_urls_in_context"]
