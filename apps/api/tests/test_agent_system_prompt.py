"""The System Prompt Contract as a versioned, closed artifact (#78)."""

from __future__ import annotations

import dataclasses
import inspect
import pathlib
from dataclasses import replace
from datetime import date

import pytest

from src.agent.prompt import sections as sections_module

from src.agent.prompt import (
    PROMPT_HASH,
    PROMPT_VERSION,
    SECTIONS,
    AnswerEvidence,
    AnswerKind,
    MarketState,
    PromptSection,
    RuntimeContext,
    cache_key,
    classify_answer_kind,
    contract_hash,
    prefix,
    render,
)
from src.stocks.shared.exceptions import StockServiceError


def context(**overrides) -> RuntimeContext:
    base = dict(
        user_id=7,
        trading_day=date(2026, 8, 14),
        market_state=MarketState.POST_CLOSE,
        active_symbol="FPT",
    )
    base.update(overrides)
    return RuntimeContext(**base)


def test_the_sections_render_in_the_fixed_order():
    keys = [section.key for section in SECTIONS]

    assert keys == [
        "mission",
        "invariants",
        "recommendation_gate",
        "tool_use",
        "output_protocol",
        "voice",
        "visual_evidence",
        "runtime_context",
    ]
    # The trusted runtime context stays last whatever is added, because
    # everything above it is the cacheable prefix.
    assert keys[-1] == "runtime_context"

    rendered = render(context())
    positions = [rendered.index(f"## {section.title}") for section in SECTIONS]
    assert positions == sorted(positions)


def test_the_precedence_list_is_stated_in_the_prompt_itself():
    rendered = render(context())

    for clause in (
        "security, privacy, scope and evidence invariants",
        "correctness, freshness and data limitations",
        "the Recommendation Gate",
        "the user's valid intent",
        "style and brevity",
    ):
        assert clause in rendered


def test_the_prompt_states_the_gate_the_untrusted_rules_and_the_stance_limits():
    rendered = render(context())

    assert "A recommendation block" in rendered
    assert "Window Health" in rendered
    assert "untrusted evidence" in rendered
    assert "never as an instruction" in rendered
    assert "allocation, leverage or position-sizing" in rendered
    assert "never reveal" in rendered or "never reveals" in rendered
    assert "chain of thought" in rendered
    assert "credentials" in rendered
    assert "Default to Vietnamese" in rendered
    assert "the data is insufficient" in rendered


def test_no_section_body_has_a_formatting_hole():
    for section in SECTIONS:
        assert "{" not in section.body
        assert "}" not in section.body


def test_the_renderer_takes_only_the_four_trusted_values():
    rendered = render(context())
    tail = rendered[len(prefix()) :]

    assert tail.strip().splitlines() == [
        "- user_id: 7",
        "- trading_day: 2026-08-14",
        "- market_state: post_close",
        "- active_symbol: FPT",
    ]

    with pytest.raises(TypeError):
        render("VCB closed at 95.4")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        RuntimeContext(
            user_id=7,
            trading_day=date(2026, 8, 14),
            market_state="continuous — VCB 95.4",  # type: ignore[arg-type]
        )
    with pytest.raises(StockServiceError):
        context(active_symbol="not a symbol")


def test_no_figure_watchlist_or_tool_result_can_reach_the_prompt():
    fields = {name for name in RuntimeContext.__annotations__}

    assert fields == {"user_id", "trading_day", "market_state", "active_symbol"}

    rendered = render(context())
    for absent in ("watchlist", "Watchlist", "tool_call_id:", "price:"):
        assert absent not in rendered.split("## 8.")[1]


def test_the_rendered_prompt_is_byte_stable_and_the_prefix_does_not_move():
    once = render(context())
    twice = render(context())
    tomorrow = render(context(trading_day=date(2026, 8, 17)))

    assert once == twice
    assert once != tomorrow
    assert tomorrow.startswith(prefix())
    assert once.startswith(prefix())


def test_the_hash_is_exported_and_changes_when_the_prose_changes():
    # Bumped with the prose it names: 1.1.0 added the evidence-reference
    # protocol the Recommendation Validator reads (#82), 1.2.0 added the Widget
    # selection protocol (#89), and 1.3.0 classifies downgraded/external/derived
    # evidence without weakening the Recommendation Gate.
    assert PROMPT_VERSION == "1.3.0"
    assert PROMPT_HASH == contract_hash()

    edited = tuple(
        replace(section, body=section.body + " One more sentence.")
        if section.key == "voice"
        else section
        for section in SECTIONS
    )

    assert contract_hash(edited) != PROMPT_HASH
    assert contract_hash(SECTIONS, version="1.2.1") != PROMPT_HASH


def test_the_cache_key_carries_model_version_hash_and_catalog_version():
    key = cache_key("gpt-5.6-luna", "abc123")

    assert key.split("|") == ["gpt-5.6-luna", PROMPT_VERSION, PROMPT_HASH, "abc123"]
    assert cache_key("gpt-5.6-terra", "abc123") != key
    assert cache_key("gpt-5.6-luna", "def456") != key
    # A Trading Day that reached the cache key would void the prefix daily.
    assert "2026" not in key


def test_answer_kind_is_classified_by_the_harness_without_a_model_call():
    assert classify_answer_kind(AnswerEvidence(grounded_tool_calls=3)) is AnswerKind.ANALYSIS
    assert classify_answer_kind(AnswerEvidence()) is AnswerKind.EDUCATION
    assert (
        classify_answer_kind(AnswerEvidence(universe_refusals=1)) is AnswerKind.REFUSAL
    )
    # A refusal outranks the evidence that was gathered before it.
    assert (
        classify_answer_kind(
            AnswerEvidence(model_refused=True, grounded_tool_calls=4)
        )
        is AnswerKind.REFUSAL
    )


def test_a_prompt_change_is_a_source_change_with_no_runtime_surface():
    import src.agent.prompt as package

    mutators = [
        name
        for name in dir(package)
        if name.startswith(("set_", "load_", "update_", "variant", "experiment", "ab_"))
    ]
    assert mutators == []
    assert list(inspect.signature(render).parameters) == ["context"]

    with pytest.raises(dataclasses.FrozenInstanceError):
        SECTIONS[0].body = "rewritten at runtime"  # type: ignore[misc]


def test_classifying_an_answer_cannot_reach_the_model_boundary():
    """V1 adds no router: a second call is a second call, even a cheap one."""
    package = pathlib.Path(sections_module.__file__).parent

    for module in package.glob("*.py"):
        assert "src.core.llm" not in module.read_text()


def test_a_section_with_a_formatting_hole_is_refused_at_import_time():
    from src.agent.prompt.contract import _assert_no_formatting_hole

    with pytest.raises(ValueError, match="formatting hole"):
        _assert_no_formatting_hole(
            (PromptSection(key="bad", title="Bad", body="price is {price}"),)
        )
