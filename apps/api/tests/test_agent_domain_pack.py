"""What a domain pack promises, held against the domain it claims to describe.

Every assertion here bridges *two* sources. A test comparing a declaration to
itself is a test that cannot go red, and a declaration is exactly the kind of
thing that rots quietly: it is right on the day it is written and nobody reads
it again. So the pack's Study names are held against the Study registry, its
Universe against the callable the tools actually call, its toolsets against the
table that expands them, and its refusal vocabulary against the closed enum the
signals module owns.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from src.agent import domain, toolsets
from src.agent.domain.pack import DomainPack, DomainPackInvalid
from src.agent.domain.vn_equity import PACK
from src.agent.prompt import PromptSection
from src.agent.toolsets import resolve_toolset
from src.stocks.universe import build_universe

_DOMAIN_DIR = Path(domain.__file__).parent


def test_the_active_pack_is_the_one_this_deployment_declares():
    assert domain.active_pack() is PACK
    assert PACK.name == "vn-equity"
    assert domain.ACTIVE_PACK in domain.PACKS
    # The key cannot disagree with the pack, because the pack supplies it.
    assert all(name == pack.name for name, pack in domain.PACKS.items())


def test_every_toolset_the_pack_names_is_a_toolset_somebody_registered():
    # The pack declares names, not tools, and never checks them: that check
    # belongs to the table that owns the names. This is where the two meet.
    assert PACK.toolsets == ("signals", "studies")
    for name in PACK.toolsets:
        assert name in toolsets.TOOLSETS, name


def test_the_written_down_selection_is_core_plus_the_pack_and_nothing_else():
    assert toolsets.CORE_TOOLSETS == ("web", "memory")
    assert toolsets.CHAT_TOOLSETS == (*toolsets.CORE_TOOLSETS, *PACK.toolsets)
    # And it still expands to the twelve tools a conversation has always had:
    # splitting the selection into core and pack is a change of *authorship*,
    # not of surface.
    assert len(toolsets.resolve_toolset(toolsets.CHAT_TOOLSETS)) == 12


def test_a_selection_that_drifts_from_the_pack_cannot_be_imported(monkeypatch):
    """The gate fires, rather than being a comment about what should hold.

    Proven by breaking one side and re-running the check — a gate nobody has
    watched fail is a gate nobody knows the polarity of.
    """
    monkeypatch.setattr(toolsets, "CHAT_TOOLSETS", ("web", "memory", "signals"))
    with pytest.raises(toolsets.ChatSelectionDisagreesWithPackError) as refused:
        toolsets._check_the_selection_matches_the_pack()

    # The message names both sides, because the fix is to change one of them.
    message = str(refused.value)
    assert "'web', 'memory', 'signals'" in message
    assert "studies" in message
    assert "agent/toolsets.py" in message and "agent/domain/" in message


def test_breaking_the_other_side_fires_the_same_gate(monkeypatch):
    other = DomainPack(
        name="vn-equity",
        version="1.0.0",
        toolsets=("signals",),
    )
    monkeypatch.setitem(domain.PACKS, "vn-equity", other)
    with pytest.raises(toolsets.ChatSelectionDisagreesWithPackError):
        toolsets._check_the_selection_matches_the_pack()


def test_the_pack_names_the_studies_the_registry_actually_offers():
    # Imported here rather than at module scope on purpose: ``REGISTRY`` is
    # filled by the act of importing ``src.studies``, so reading it at import
    # time is reading whatever happened to be registered first. The pack writes
    # its names out for that reason; this is the check that keeps them true.
    from src import studies

    assert PACK.study_names == tuple(sorted(studies.REGISTRY))


def test_the_pack_holds_the_universe_callable_rather_than_a_copy_of_it():
    # Identity, not equality: a pack holding a list of tickers would be a pack
    # that lies the first time anyone changes a configuration variable.
    assert PACK.universe is build_universe


def test_identity_moves_when_the_version_moves_and_when_the_prose_does():
    from src.agent.prompt.sections import PromptSection

    baseline = PACK.identity
    assert replace(PACK, version="9.9.9").identity != baseline
    # And a prose edit with no version bump still voids it — which is the whole
    # reason the hash covers the body as well as the hand-written number.
    section = PromptSection(key="k", title="3. So lieu", body="B")
    with_body = replace(PACK, prompt_sections=(section,))
    assert with_body.identity != baseline

    # The body is rendered the way ``contract._static_text`` renders the core:
    # heading, blank line, prose. So a *title* edited with no version bump moves
    # the identity too — which it must, because it moves the text that ships.
    assert with_body.body_text == "## 3. So lieu\n\nB"
    retitled = replace(with_body, prompt_sections=(replace(section, title="3. Gia"),))
    assert retitled.identity != with_body.identity

    # So does the refusal vocabulary: two packs that refuse different things are
    # not the same pack, whatever their prose says.
    assert replace(PACK, refusal_vocabulary=frozenset({"x"})).identity != baseline
    # Stable across calls: a cache key that moved on its own would never hit.
    assert PACK.identity == baseline


def test_a_pack_is_frozen_so_two_turns_cannot_observe_each_other():
    with pytest.raises(Exception):
        PACK.name = "something-else"  # type: ignore[misc]


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({"name": "  "}, "needs a name"),
        ({"version": ""}, "needs a version"),
        ({"toolsets": ()}, "declares no toolsets"),
        ({"study_names": ("a", "a")}, "more than once"),
    ],
)
def test_a_malformed_pack_is_refused_at_import_not_at_serve(kwargs, expected):
    with pytest.raises(DomainPackInvalid) as refused:
        replace(PACK, **kwargs)
    assert expected in str(refused.value)


def _imported_names(source: str) -> set[str]:
    """Every module name a source file imports, relative forms resolved.

    Parsed rather than pattern-matched. A regex over ``from|import`` captures
    only the first token, which reads ``from .. import toolsets`` as an import
    of ``..`` — and that is precisely the form a future edit inside a package
    ``__init__`` would reach for. It also matches inside docstrings, so a
    reflowed paragraph beginning with the word "import" would fail a structural
    gate for a typographic reason.
    """
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            names.add(base)
            # ``from .. import toolsets`` carries the interesting name in the
            # alias, not in ``module``.
            names.update(
                f"{base}.{alias.name}" if base else alias.name
                for alias in node.names
            )
    return {name for name in names if name}


def test_the_frame_imports_no_domain():
    """``pack.py`` and ``__init__.py`` must not name the thing they frame.

    A frame that knew the shape of the thing it frames would have to be edited
    to hold the next one, which is the whole failure the split exists to
    prevent. ``vn_equity.py`` is exempt — it *is* the domain.
    """
    for name in ("pack.py", "__init__.py"):
        for module in _imported_names((_DOMAIN_DIR / name).read_text()):
            leaf = module.rsplit(".", 1)[-1]
            for forbidden in ("stocks", "studies", "toolsets"):
                assert forbidden not in module.split("."), f"{name} imports {module}"
                assert leaf != forbidden, f"{name} imports {module}"


def test_that_import_check_catches_the_form_a_regex_would_miss():
    """Polarity, proven on the three shapes that actually get written."""
    assert "toolsets" in {
        n.rsplit(".", 1)[-1] for n in _imported_names("from .. import toolsets")
    }
    assert "stocks" in {
        n.rsplit(".", 1)[-1] for n in _imported_names("from src import stocks")
    }
    assert "src.studies.registry" in _imported_names(
        "from src.studies.registry import REGISTRY"
    )
    # And a docstring that opens with the word is not an import.
    assert _imported_names('"""\nimport this paragraph carefully\n"""') == set()


def test_the_loop_names_no_particular_domain():
    """Where the hardcoding would show up if it came back.

    The gate moved once, and the move is worth stating. It used to be that
    ``loop.py`` reached for no pack at all; since the loop learned to hand a
    Turn the active pack's half of the prompt, it reaches for ``active_pack``
    by design. What must never come back is the loop knowing *which* pack:
    naming the domain, its module, or one of its tools is how "swap the pack"
    becomes "swap the pack and edit the loop", and the second domain then costs
    what the first one did.

    So the check is about the specific rather than the general. ``active_pack``
    is the seam and is allowed; ``vn_equity`` and ``get_field`` are the domain
    and are not.

    Scoped to named symbols rather than to the word "domain" anywhere in the
    file. The repository's vocabulary uses that word constantly —
    ``web_domain_denylist``, deduplicating results by domain — and a bare
    substring check would turn a structural gate into a spelling gate the first
    time a comment mentions any of them.
    """
    source = (Path(domain.__file__).parents[1] / "loop.py").read_text()

    for symbol in ("vn_equity", "vn-equity", "PACKS", "ACTIVE_PACK"):
        assert symbol not in source, f"loop.py names {symbol}"

    # And no tool of the domain, which is the form the hardcoding would most
    # plausibly take: a literal list of the names that mean "this Turn is about
    # a stock", copied into the loop instead of read off the pack.
    #
    # Two exceptions, and they are named rather than excused. ``CATALOG_TOOL``
    # and ``RUN_TOOL`` were already there before any of this: they are how the
    # loop logs a Turn that read the analysis catalog and ran nothing from it,
    # which is a record of a *missing recipe* rather than a decision about which
    # domain is loaded. They are debt against the same principle and they are
    # not this change's to pay — moving them means moving that log onto the
    # pack, which is a different piece of work with a different reviewer. What
    # this test does is keep the debt at exactly two lines: any third mention of
    # a domain tool, or a mention of either of these outside its own constant,
    # goes red.
    allowed = {
        'CATALOG_TOOL = "list_studies"',
        'RUN_TOOL = "run_study"',
    }
    scrubbed = source
    for line in allowed:
        assert line in scrubbed, f"the known exception {line!r} moved; re-read it"
        scrubbed = scrubbed.replace(line, "")

    for tool in resolve_toolset(domain.active_pack().toolsets):
        assert tool not in scrubbed, f"loop.py names the domain tool {tool}"


def test_swapping_the_pack_moves_the_tool_surface_without_touching_the_loop(
    monkeypatch,
):
    """The acceptance gate of this whole change, proven on the loop itself.

    A second domain must arrive as a second declaration, not as an edit to the
    loop that runs every domain. So: install a pack that names a different
    bundle, move the written-down selection with it, and watch the surface a
    Turn would actually be handed change — while ``loop.py``, which is where the
    old hardcoding would have lived, says nothing about any of it.

    ``loop`` binds ``CHAT_TOOLSETS`` by value at import (``loop.py:153``), so the
    test moves that binding too. That is not a workaround for the test's sake:
    in production a pack swap is a source edit and a restart, which rebinds it
    the same way. What the test must not do is *derive* the surface from the
    pack itself — that would be asserting its own setup.
    """
    from src.agent import definitions
    from src.agent import loop as loop_module

    # Only the two attributes ``AgentLoop.__init__`` reads. A full ``LLMConfig``
    # would be copied prose about pricing and lanes, none of which this test is
    # about, and copied prose is what goes stale.
    class _Route:
        vision = False

    class _Config:
        route = _Route()

        @staticmethod
        def model_for(_workload):
            return "model-under-test"

    monkeypatch.setitem(
        toolsets.TOOLSETS,
        "admin",
        {"description": "Another domain's bundle.", "tools": ("hidden",)},
    )
    monkeypatch.setitem(
        domain.PACKS,
        "other",
        DomainPack(name="other", version="0.1.0", toolsets=("admin",)),
    )
    monkeypatch.setattr(domain, "ACTIVE_PACK", "other")
    swapped = ("web", "memory", "admin")
    monkeypatch.setattr(toolsets, "CHAT_TOOLSETS", swapped)
    monkeypatch.setattr(loop_module, "CHAT_TOOLSETS", swapped)
    toolsets.clear_memo()
    try:
        # The gate is satisfied by the two moving together, which is the point:
        # it is not a lock on one domain, it is a lock on the pair agreeing.
        toolsets._check_the_selection_matches_the_pack()

        # And the loop's own default follows, with no line in it naming a pack.
        instance = loop_module.AgentLoop(client=object(), config=_Config())
        assert instance._toolsets == swapped
        assert toolsets.resolve_toolset(instance._toolsets) == (
            "web_search",
            "fetch_url",
            "session_search",
            "remember_fact",
            "recall_facts",
            "hidden",
        )
        assert "get_field" not in definitions._selection(instance._toolsets)
    finally:
        toolsets.clear_memo()


def test_importing_a_pack_reads_no_settings_and_opens_no_session():
    """A declaration that consulted its environment would not be one.

    Run in a fresh interpreter rather than by reloading modules in this one.
    Reloading rebinds the ``DomainPack`` class object, so every later
    ``isinstance``/``is`` comparison in the session compares against a class
    that no longer exists — and no ``finally`` block can put that back, because
    restoring it means reloading again, which makes a third generation. A
    subprocess is also the honest model of the claim: what is being asserted is
    what a *cold import* does.

    ``get_settings`` is ``lru_cache``d, so its miss count is the evidence: a
    module that read configuration at import would have forced exactly one.
    """
    probe = (
        "import sys; import src.agent.domain;"
        "import src.core.config as c;"
        "print(c.get_settings.cache_info().misses,"
        "'src.core.database' in sys.modules)"
    )
    finished = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parents[1],
    )
    assert finished.returncode == 0, finished.stderr[-2000:]
    misses, database_imported = finished.stdout.strip().split()
    assert misses == "0"
    assert database_imported == "False"


def test_that_probe_would_notice_a_pack_that_did_read_settings():
    """Polarity of the check above, on the same interpreter it uses."""
    probe = (
        "import src.core.config as c; c.get_settings();"
        "print(c.get_settings.cache_info().misses)"
    )
    finished = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parents[1],
    )
    assert finished.returncode == 0, finished.stderr[-2000:]
    assert finished.stdout.strip() == "1"


# --- Refusal vocabulary: one closed set, two sets of prose, both held ---------
#
# The codes live in ``stocks/signals/issues.py`` and the sentences do not: the
# English ones are in ``alpha/reasons.py`` for the artifact a model is handed,
# the Vietnamese ones in ``apps/web/src/lib/signal-issues.ts`` for the surfaces
# a person reads. The web side has held its half since it was written
# (``signal-issues.test.ts``, which reads the Python enum file directly). The
# Python side named a test that no longer exists, so its half was unheld — the
# checks below are that half, restored.

_ISSUES_SOURCE = Path(__file__).parents[1] / "src/stocks/signals/issues.py"


def _codes_the_enum_file_declares() -> set[str]:
    """The closed set, read back out of its source.

    Read rather than imported, and the reason is the same one the web-side guard
    has: the pack builds its vocabulary by comprehension over ``SignalIssue``,
    so comparing the two objects would compare a set to itself. Only a second,
    independent reading of the codes can notice one being added.
    """
    source = _ISSUES_SOURCE.read_text()
    return set(re.findall(r'^\s+[A-Z][A-Z_0-9]* = "([a-z_0-9.]+)"', source, re.M))


def _codes_without_sentences(codes: set[str]) -> set[str]:
    """Which of these codes the model-facing prose has nothing to say about.

    Written as a function over an argument rather than as a bare assertion so
    the check can be aimed at a code that is deliberately absent. A guard nobody
    has watched go red is a guard of unknown polarity.
    """
    from src.alpha.reasons import SIGNAL_ISSUE_SENTENCES

    return codes - {issue.value for issue in SIGNAL_ISSUE_SENTENCES}


def test_the_pack_declares_the_closed_set_of_codes_it_can_refuse_with():
    declared = _codes_the_enum_file_declares()

    assert len(declared) == 42
    assert PACK.refusal_vocabulary == declared


def test_every_code_the_pack_can_emit_has_a_sentence_for_the_model():
    """The guard ``alpha/reasons.py`` claimed for a week that it had.

    Its docstring pointed at ``tests/test_envelope.py``, removed in the
    2026-08-25 rip-out. A refusal reaching the artifact with no sentence is a
    ``value: null`` with nothing next to it, and that reads as the figure being
    absent rather than as this system declining to state it.
    """
    assert _codes_without_sentences(_codes_the_enum_file_declares()) == set()


def test_that_guard_goes_red_for_a_code_nobody_wrote_a_sentence_for():
    absent = "a_code_from_the_future"
    assert _codes_without_sentences({absent}) == {absent}
    assert _codes_without_sentences(PACK.refusal_vocabulary | {absent}) == {absent}


def test_no_sentence_tells_the_reader_what_to_do():
    """Held on this side too, for the rule the web side already holds.

    ``reasons.py`` states it — a reason that advised a reader would be the
    recommendation the whole citation contract exists to keep out of a figure —
    and until now only the Vietnamese half of the prose was checked against it.
    The patterns differ from the web side's because the prose does: these
    sentences are English, so ``nên mua``/``khuyến nghị`` cannot appear in them
    and matching for them would be theatre. What is checked instead is the
    English shape of the same mistake, hedged forms included — "consider
    reducing", "avoid buying" — because those are advice with the verb softened.
    """
    from src.alpha.reasons import SIGNAL_ISSUE_SENTENCES

    advice = re.compile(
        r"\b(should|must|ought to|may want to)\s+"
        r"(buy|sell|hold|reduc|increas|exit|enter|avoid|trim|add)"
        r"|\b(consider|recommend|suggest|advis)\w*\s+"
        r"(buy|sell|hold|reduc|increas|exit|enter|avoid|trim|add|tak)"
        r"|\bavoid\s+(buying|selling|holding)",
        re.I,
    )
    offenders = [
        issue.value
        for issue, sentence in SIGNAL_ISSUE_SENTENCES.items()
        if advice.search(sentence)
    ]
    assert offenders == []


def test_that_advice_check_catches_the_hedged_forms_too():
    """Polarity, on the shapes a well-meaning edit would actually produce."""
    advice = re.compile(
        r"\b(should|must|ought to|may want to)\s+"
        r"(buy|sell|hold|reduc|increas|exit|enter|avoid|trim|add)"
        r"|\b(consider|recommend|suggest|advis)\w*\s+"
        r"(buy|sell|hold|reduc|increas|exit|enter|avoid|trim|add|tak)"
        r"|\bavoid\s+(buying|selling|holding)",
        re.I,
    )
    for sentence in (
        "Traders should reduce size until the figure returns.",
        "Consider reducing exposure while this holds.",
        "Avoid buying until the session confirms.",
        "We suggest taking the other side of this.",
    ):
        assert advice.search(sentence), sentence
    # And it does not fire on a sentence that only says what is missing.
    assert not advice.search(
        "The store holds no closed session for this symbol, so no figure exists."
    )


def test_swapping_the_pack_swaps_the_prompt_body_with_no_edit_to_the_loop(
    monkeypatch,
):
    """The other half of the acceptance gate, on the prose rather than the tools.

    The tool surface following the pack was proven above. This is the same claim
    about the half of the prompt a Turn carries: install a second pack with its
    own prose, and what the loop hands a Turn changes, while nothing in the loop
    mentions either pack.
    """
    from src.agent.loop import domain_body_note, domain_tool_names

    other = DomainPack(
        name="other",
        version="0.1.0",
        toolsets=("web",),
        prompt_sections=(
            PromptSection(key="other_body", title="Khác", body="Một luật khác."),
        ),
    )
    monkeypatch.setitem(domain.PACKS, "other", other)
    monkeypatch.setattr(domain, "ACTIVE_PACK", "other")
    toolsets.clear_memo()
    try:
        assert domain_body_note() == other.body_text
        assert "Một luật khác." in domain_body_note()
        assert "Signal Field" not in domain_body_note()
        # And what counts as "this Turn asked about the domain" follows too:
        # the second pack's trigger is its own bundle, not the first pack's.
        assert domain_tool_names() == {"web_search", "fetch_url"}
    finally:
        toolsets.clear_memo()
