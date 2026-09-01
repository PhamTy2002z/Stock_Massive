"""Contracts for the web-first Vietnamese-equity domain declaration."""

from __future__ import annotations

import ast
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from src.agent import domain, toolsets
from src.agent.domain.pack import DomainPack, DomainPackInvalid
from src.agent.domain.vn_equity import PACK, WEB_FIRST_RESEARCH
from src.agent.prompt import PromptSection

_DOMAIN_DIR = Path(domain.__file__).parent


def test_active_pack_is_web_first_and_adds_no_local_analysis_tools():
    assert domain.active_pack() is PACK
    assert PACK.name == "vn-equity"
    assert PACK.toolsets == ()
    assert toolsets.CHAT_TOOLSETS == toolsets.CORE_TOOLSETS == ("web", "memory")
    assert toolsets.resolve_toolset(toolsets.CHAT_TOOLSETS) == ("web_search", "fetch_url", "session_search", "remember_fact", "recall_facts")


def test_pack_guidance_requires_web_evidence_and_rejects_fake_local_analysis():
    body = WEB_FIRST_RESEARCH.body
    assert "web_search" in body and "fetch_url" in body
    assert "không có kho chỉ báo" in body.lower()
    assert "không đủ hoặc mâu thuẫn" in body.lower()


def test_selection_drift_from_pack_is_refused(monkeypatch):
    monkeypatch.setattr(toolsets, "CHAT_TOOLSETS", ("web",))
    with pytest.raises(toolsets.ChatSelectionDisagreesWithPackError):
        toolsets._check_the_selection_matches_the_pack()


def test_identity_moves_with_version_and_prompt_text():
    baseline = PACK.identity
    assert replace(PACK, version="9.9.9").identity != baseline
    section = PromptSection(key="other", title="Khác", body="Luật khác.")
    assert replace(PACK, prompt_sections=(section,)).identity != baseline
    assert PACK.identity == baseline


def test_pack_is_frozen_and_requires_name_and_version():
    with pytest.raises(Exception):
        PACK.name = "other"  # type: ignore[misc]
    for field, value, message in (("name", " ", "needs a name"), ("version", "", "needs a version")):
        with pytest.raises(DomainPackInvalid, match=message):
            replace(PACK, **{field: value})


def test_a_question_that_names_a_listing_or_the_market_asks_for_the_body():
    for question, reason in (
        ("VCB thanh khoản thế nào?", "symbol:VCB"),
        ("VN30F1M đáo hạn khi nào?", "symbol:VN30F1M"),
        ("Thị trường hôm nay ra sao?", "topic:thị trường"),
        ("What is the dividend policy?", "topic:dividend"),
    ):
        assert PACK.body_reason(question) == (True, reason)


def test_only_a_question_about_the_assistant_itself_goes_without_the_body():
    for question, reason in (
        ("Bạn là ai?", "off_topic:bạn là ai"),
        ("Giải thích cách bạn hoạt động.", "off_topic:bạn hoạt động"),
        ("Xin chào!", "off_topic:xin chào"),
    ):
        assert PACK.body_reason(question) == (False, reason)


def test_a_question_the_pack_recognises_nothing_in_still_gets_the_body():
    """Ambiguity resolves towards the playbook: the two errors cost differently."""
    assert PACK.body_reason("Hôm nay có tin gì mới không?") == (True, "default")
    assert PACK.body_reason("") == (True, "default")


def test_naming_the_domain_outranks_asking_about_the_assistant():
    """Same words, and the difference is that one of them names the market."""
    assert PACK.body_reason("Bạn là ai và VCB có tốt không?") == (True, "symbol:VCB")
    assert PACK.body_reason("bạn là ai, và thị trường thì sao?") == (True, "topic:thị trường")


def test_the_reason_names_the_first_marker_declared_however_often_it_is_asked():
    """A vocabulary read in tuple order answers the same way on every run."""
    question = "Cổ tức và cổ phiếu và thị trường?"
    assert [PACK.body_reason(question) for _ in range(3)] == [(True, "topic:cổ phiếu")] * 3


def test_a_symbol_shape_that_is_not_a_pattern_is_refused_at_declaration():
    with pytest.raises(DomainPackInvalid, match="not a regular expression"):
        replace(PACK, symbol_shape="[")


def test_what_a_question_is_read_with_is_not_what_a_cached_prefix_is_keyed_by():
    """The vocabulary decides whether the body ships, never what it says."""
    baseline = PACK.identity
    assert replace(PACK, topic_markers=(), off_topic_markers=(), symbol_shape="").identity == baseline


def _imported_names(source: str) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            names.add(base)
            names.update(f"{base}.{alias.name}" if base else alias.name for alias in node.names)
    return {name for name in names if name}


def test_domain_frame_does_not_import_subject_runtime_or_toolsets():
    for name in ("pack.py", "__init__.py"):
        for imported in _imported_names((_DOMAIN_DIR / name).read_text()):
            assert not {"stocks", "studies", "toolsets"}.intersection(imported.split("."))


def test_pack_import_reads_no_settings_and_opens_no_session():
    probe = "import sys; import src.agent.domain; import src.core.config as c; print(c.get_settings.cache_info().misses, 'src.core.database' in sys.modules)"
    finished = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, cwd=Path(__file__).parents[1])
    assert finished.returncode == 0, finished.stderr[-2000:]
    assert finished.stdout.strip() == "0 False"


def test_swapping_pack_swaps_prompt_body_without_changing_loop(monkeypatch):
    from src.agent.loop import domain_body_note

    other = DomainPack(name="other", version="0.1.0", prompt_sections=(PromptSection(key="other", title="Khác", body="Một luật khác."),))
    monkeypatch.setitem(domain.PACKS, "other", other)
    monkeypatch.setattr(domain, "ACTIVE_PACK", "other")
    assert domain_body_note() == other.body_text
