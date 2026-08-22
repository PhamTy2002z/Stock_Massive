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
        today=date(2026, 8, 16),
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
        # ``docs/adr/0022`` seats each 1.8.0 section beside the one whose rule
        # it extends: the figure rule after the invariants that state
        # provenance, batching after the tool-use policy it paces.
        "figures",
        "recommendation_gate",
        "tool_use",
        "batched_lookups",
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
    assert "Vietnamese is the default only where" in rendered
    assert "the data is insufficient" in rendered


def test_the_answer_follows_the_language_of_the_latest_user_message():
    """A Thread that opened in Vietnamese must still answer English in English.

    The instruction it replaced said "answer in the user's language, default to
    Vietnamese", and both halves were read as one: an English question inside a
    Thread whose first exchange was Vietnamese came back in Vietnamese. What the
    model needs stated is which message decides, and that a greeting decides it
    too.
    """
    rendered = render(context())

    assert "language of the user's latest message" in rendered
    assert "whatever language the" in rendered
    assert '"Hello" is' in rendered


def test_scope_is_decided_before_lookup_and_refusals_do_not_echo_figures():
    rendered = " ".join(render(context()).lower().split())

    assert "decide whether the request is within scope before any tool call" in rendered
    assert "do not call market, company, news or web tools" in rendered
    assert "do not repeat an amount, percentage or leverage ratio" in rendered
    assert "does not make a prohibited request answerable" in rendered


def test_the_prompt_says_how_today_is_read_against_the_trading_day():
    """The instruction the second injected date exists to support.

    Injecting the date is half of it. Without prose saying what to do with it,
    "phân tích giá STB hiện tại" asked on a Sunday still reads as a question
    about a session that does not exist, and the answer says so instead of
    answering from Friday's.
    """
    rendered = render(context())
    section = rendered.split("## 10.")[1]

    assert "hôm nay" in section
    assert "the most recent data there is" in section
    assert "reason to tell the user there is no data" in section
    # And both values are there to be read against each other.
    assert "- today: 2026-08-16" in rendered
    assert "- trading_day: 2026-08-14" in rendered


def test_the_figure_rule_answers_in_part_rather_than_hedging():
    """``docs/adr/0022``: the prose that has to keep a Turn from going blank.

    Three claims, and the third is the one the Contract did not make before
    1.8.0. Saying *a figure you cannot reference is a figure you do not state*
    without saying what to do next is how a model arrives at one hedged
    sentence, which is the outcome ADR-0021 measured at 58% of Turns.
    """
    section = render(context()).split("## 3. Figures and the gaps in them")[1]
    section = section.split("## 4.")[0]
    lowered = " ".join(section.lower().split())

    # 1. a figure comes from a tool call, and arithmetic in prose is not one.
    assert "came back from a tool call in this turn" in lowered
    assert "a ratio you divided yourself" in lowered
    # 2. an unreferenced figure ends a sentence, and the answer goes on.
    assert "a figure you cannot reference is a figure you do not state" in lowered
    assert "that ends a sentence, never an answer" in lowered
    assert "you answer in part" in lowered
    # 3. naming the obstacle beats a plausible number, and beats a hedge.
    assert "naming the obstacle is the answer at that point" in lowered
    assert "hedging is not a substitute" in lowered

    # The gap is named inside the sentence it affects. Contract 1.6.0 forbids a
    # closing note about sources, and this section must not reopen that door.
    assert "inside the sentence it affects" in lowered


def test_the_batching_rule_bounds_itself_to_independent_lookups():
    """The high-leverage half of 1.8.0, and the guard that keeps it cheap.

    ``loop.py`` has always dispatched a round concurrently; the model was never
    told to emit the calls together. Unbounded, the same instruction produces a
    first round of guessed arguments — so the block says what independence
    means and what it is not.
    """
    section = render(context()).split("## 6. Batching lookups")[1]
    section = section.split("## 7.")[0]
    lowered = " ".join(section.lower().split())

    assert "emit those calls together in one turn" in lowered
    assert "genuinely depends on an earlier one's result" in lowered
    assert "not about the order you would read the answers in" in lowered
    # The anti-thrash half: a round of invented arguments is a round spent.
    assert "together does not mean everything you can imagine" in lowered


def test_the_new_sections_add_no_field_the_model_could_set():
    """Prose carries the rule; nothing gives the model a compliance switch.

    ``docs/adr/0015``'s invariant is the one thing ADR-0022 does not touch, and
    the way it would be broken is a field — in the injected context or in the
    marker vocabulary — that a model could write to claim it had complied.
    """
    assert set(RuntimeContext.__annotations__) == {
        "user_id",
        "trading_day",
        "today",
        "market_state",
        "active_symbol",
    }

    for section in SECTIONS:
        if section.key not in ("figures", "batched_lookups"):
            continue
        lowered = section.body.lower()
        # No marker vocabulary: the reference markers of the output protocol are
        # the only structured thing the model writes, and neither new section
        # may add a sixth kind.
        for invented in ("the word ", "square-bracket", "declare", "mark it as"):
            assert invented not in lowered


def test_no_section_body_has_a_formatting_hole():
    for section in SECTIONS:
        assert "{" not in section.body
        assert "}" not in section.body


def test_the_renderer_takes_only_the_five_trusted_values():
    rendered = render(context())
    tail = rendered[len(prefix()) :]

    assert tail.strip().splitlines() == [
        "- user_id: 7",
        "- today: 2026-08-16",
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
            today=date(2026, 8, 16),
            market_state="continuous — VCB 95.4",  # type: ignore[arg-type]
        )
    with pytest.raises(TypeError):
        # A day the caller could not resolve is not a day to render as one.
        context(today="hôm nay")
    with pytest.raises(StockServiceError):
        context(active_symbol="not a symbol")


def test_no_figure_watchlist_or_tool_result_can_reach_the_prompt():
    fields = {name for name in RuntimeContext.__annotations__}

    assert fields == {
        "user_id",
        "trading_day",
        "today",
        "market_state",
        "active_symbol",
    }

    rendered = render(context())
    for absent in ("watchlist", "Watchlist", "tool_call_id:", "price:"):
        assert absent not in rendered.split("## 10.")[1]


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
    # protocol the Recommendation Validator reads (#82), and 1.2.0 added the
    # Widget selection protocol (#89). Version 1.3.0 injected today's date and
    # distinguished it from the Trading Day; 1.4.0 classifies downgraded,
    # external, and derived evidence without weakening the Recommendation Gate.
    # 1.8.0 gives the Contract the no-fabrication rule and the batching rule
    # (``docs/adr/0022``), which is a minor bump because two sections arrived.
    # 1.9.0 hands the answer's shape back to the model, says a message asking
    # for nothing factual is answered without a lookup, and raises the visual
    # ceiling to three (``docs/adr/0023``) — no section arrived or left, so the
    # section list is unchanged and only prose inside existing sections moved.
    # 1.10.0 tells the model the reader has a past it can look up rather than
    # ask about again, splits saving a sourced fact from saving one the reader
    # stated, and says a block the system marked as carrying an instruction is
    # still evidence to read (``docs/adr/0025``) — again prose only.
    assert PROMPT_VERSION == "1.10.0"
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
