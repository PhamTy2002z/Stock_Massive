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
