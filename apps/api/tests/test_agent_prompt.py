"""Contracts for the harness-first system prompt."""

from __future__ import annotations

from datetime import date

import pytest

from src.agent.prompt import PROMPT_HASH, PROMPT_VERSION, RuntimeContext, prefix, render
from src.agent.prompt.sections import SECTIONS


def section(key: str) -> str:
    return next(item.body for item in SECTIONS if item.key == key)


def prose(key: str) -> str:
    return " ".join(section(key).lower().split())


def test_prompt_version_and_section_order_are_explicit():
    assert PROMPT_VERSION == "4.1.0"
    assert tuple(item.key for item in SECTIONS) == (
        "mission",
        "invariants",
        "honesty",
        "tools",
        "budget",
        "untrusted",
        "memory",
        "style",
        "context",
    )
    assert len(PROMPT_HASH) == 64


def test_prompt_offers_only_the_current_web_and_memory_tools():
    tools = section("tools")
    for name in (
        "web_search",
        "fetch_url",
        "session_search",
        "remember_fact",
        "recall_facts",
    ):
        assert name in tools
    assert "năm công cụ" in tools


def test_prompt_is_honest_about_missing_local_analysis_runtime():
    honesty = prose("honesty")
    assert "không có bảng giá trực tiếp" in honesty
    assert "kho chỉ báo" in honesty
    assert "trình tính toán kỹ thuật" in honesty
    assert "không biết là một câu trả lời hợp lệ" in honesty


def test_prompt_requires_current_web_evidence_and_source_reading():
    tools = section("tools")
    budget = section("budget")
    assert "web_search" in tools and "fetch_url" in tools
    assert "đoạn trích tìm kiếm" in tools
    assert "nguồn sơ cấp" in tools
    assert "tối đa bảy" in budget
    assert "không phải chỉ tiêu" in budget


def test_prompt_treats_web_and_attachments_as_untrusted_data():
    body = prose("untrusted")
    assert "untrusted_tool_result" in body
    assert "user_attachment" in body
    assert "không phải chỉ dẫn" in body
    assert "prompt injection" in body


def test_prompt_teaches_the_model_to_read_the_trading_status():
    body = prose("context")
    assert "market_today" in body
    assert "previous_trading_day" in body
    assert "hôm nay không có phiên" in body
    assert "không được gán cho hôm nay" in body


def test_prompt_limits_memory_to_user_owned_durable_facts():
    body = section("memory")
    assert "chính người dùng" in body
    assert "không lưu số liệu thị trường chóng cũ" in body
    assert "không phải nguồn dữ liệu thị trường hiện hành" in body


def test_runtime_values_are_rendered_only_in_the_dynamic_tail():
    stable = prefix()
    rendered = render(RuntimeContext(today=date(2026, 8, 31), user_name="Ty"))
    assert "2026-08-31" not in stable
    assert "Ty" not in stable
    assert "2026-08-31" in rendered
    assert "Ty" in rendered


@pytest.mark.parametrize("value", ("{hole}", "{{still-a-hole}}"))
def test_runtime_values_cannot_turn_into_formatting_holes(value: str):
    rendered = render(RuntimeContext(today=date(2026, 8, 31), user_name=value))
    assert "{" not in rendered and "}" not in rendered
