"""The invariant the whole hand-rolled boundary exists for.

A gateway was measured keying streamed tool calls on a local counter instead of
the upstream index, concatenating two calls' arguments into invalid JSON under
the wrong id — while returning 200. That failure never surfaces at runtime. The
tests here are the assertion a framework would have hidden.
"""

from __future__ import annotations

import pytest

from src.core.llm.errors import LLMError, MalformedArguments, llm_metrics
from src.core.llm.streaming import StreamAssembler, parse_tool_calls


def fragment(index: int, *, id=None, name=None, arguments=None) -> dict:
    function = {}
    if name is not None:
        function["name"] = name
    if arguments is not None:
        function["arguments"] = arguments
    payload: dict = {"index": index}
    if id is not None:
        payload["id"] = id
    if function:
        payload["function"] = function
    return payload


class TestInterleavedParallelCalls:
    def test_two_calls_streamed_interleaved_stay_apart(self):
        """The measured failure, written as a test.

        Fragments arrive out of order and alternating between calls, which is
        what parallel tool calls look like on the wire. Keyed on the upstream
        index they reassemble exactly; keyed on arrival they would not.
        """
        assembler = StreamAssembler()

        for chunk in [
            fragment(0, id="call_a", name="get_price", arguments='{"sym'),
            fragment(1, id="call_b", name="get_news", arguments='{"sy'),
            fragment(0, arguments='bol": "VCB"'),
            fragment(1, arguments='mbol": "FPT", "days"'),
            fragment(0, arguments="}"),
            fragment(1, arguments=": 7}"),
        ]:
            assembler.add_tool_call_fragment(chunk)

        first, second = assembler.tool_calls()

        assert first.id == "call_a"
        assert first.name == "get_price"
        assert first.arguments == {"symbol": "VCB"}
        assert second.id == "call_b"
        assert second.name == "get_news"
        assert second.arguments == {"symbol": "FPT", "days": 7}

    def test_calls_come_back_in_upstream_index_order(self):
        """Arrival order is not call order once fragments interleave."""
        assembler = StreamAssembler()

        assembler.add_tool_call_fragment(
            fragment(2, id="third", name="c", arguments="{}")
        )
        assembler.add_tool_call_fragment(
            fragment(0, id="first", name="a", arguments="{}")
        )
        assembler.add_tool_call_fragment(
            fragment(1, id="second", name="b", arguments="{}")
        )

        assert [call.id for call in assembler.tool_calls()] == [
            "first",
            "second",
            "third",
        ]
        assert [call.output_index for call in assembler.tool_calls()] == [0, 1, 2]

    def test_the_responses_api_spelling_of_the_index_works_too(self):
        assembler = StreamAssembler()

        assembler.add_tool_call_fragment(
            {
                "output_index": 3,
                "id": "call_a",
                "function": {"name": "get_price", "arguments": '{"symbol": "VCB"}'},
            }
        )

        (call,) = assembler.tool_calls()
        assert call.output_index == 3
        assert call.arguments == {"symbol": "VCB"}

    def test_a_fragment_with_no_index_is_refused_rather_than_counted(self):
        """The bug is the fallback, so there is no fallback."""
        assembler = StreamAssembler()

        with pytest.raises(LLMError, match="no upstream index"):
            assembler.add_tool_call_fragment(
                {"id": "call_a", "function": {"name": "x", "arguments": "{}"}}
            )

    def test_a_repeated_name_does_not_concatenate(self):
        """Routes that resend id and name on every fragment are common."""
        assembler = StreamAssembler()

        assembler.add_tool_call_fragment(
            fragment(0, id="call_a", name="get_price", arguments='{"a":')
        )
        assembler.add_tool_call_fragment(
            fragment(0, id="call_a", name="get_price", arguments="1}")
        )

        (call,) = assembler.tool_calls()
        assert call.name == "get_price"
        assert call.arguments == {"a": 1}


class TestTheJsonParseInvariant:
    def test_unparseable_arguments_raise_immediately(self):
        assembler = StreamAssembler()
        assembler.add_tool_call_fragment(
            fragment(0, id="call_a", name="get_price", arguments='{"symbol": "VCB"')
        )

        with pytest.raises(MalformedArguments):
            assembler.tool_calls()

    def test_nothing_unparseable_is_ever_handed_back(self):
        """Not "returned with a flag" — not returned."""
        assembler = StreamAssembler()
        assembler.add_tool_call_fragment(
            fragment(0, id="good", name="a", arguments='{"ok": true}')
        )
        assembler.add_tool_call_fragment(
            fragment(1, id="bad", name="b", arguments="{oops")
        )

        with pytest.raises(MalformedArguments):
            assembler.tool_calls()

    def test_arguments_that_are_not_an_object_are_refused(self):
        assembler = StreamAssembler()
        assembler.add_tool_call_fragment(
            fragment(0, id="call_a", name="get_price", arguments='"just a string"')
        )

        with pytest.raises(MalformedArguments):
            assembler.tool_calls()

    def test_a_tool_with_no_parameters_is_not_a_parse_failure(self):
        assembler = StreamAssembler()
        assembler.add_tool_call_fragment(fragment(0, id="call_a", name="get_watchlist"))

        (call,) = assembler.tool_calls()
        assert call.arguments == {}

    def test_a_failure_is_counted_and_logged(self, caplog):
        llm_metrics().reset()
        assembler = StreamAssembler()
        assembler.add_tool_call_fragment(
            fragment(0, id="call_a", name="get_price", arguments="{oops")
        )

        with caplog.at_level("ERROR"):
            with pytest.raises(MalformedArguments):
                assembler.tool_calls()

        assert llm_metrics().malformed_arguments == 1
        assert any("not JSON" in record.message for record in caplog.records)
        llm_metrics().reset()


class TestTextAndFinish:
    def test_content_fragments_join_in_arrival_order(self):
        assembler = StreamAssembler()

        for part in ("Hello", ", ", "world"):
            assembler.add_chunk({"choices": [{"delta": {"content": part}}]})

        assert assembler.text == "Hello, world"

    def test_a_stream_with_no_content_has_no_text(self):
        assert StreamAssembler().text is None

    def test_the_finish_reason_is_carried(self):
        assembler = StreamAssembler()

        assembler.add_chunk({"choices": [{"delta": {}, "finish_reason": "tool_calls"}]})

        assert assembler.finish_reason == "tool_calls"

    def test_usage_arrives_on_its_own_chunk(self):
        assembler = StreamAssembler()

        assembler.add_chunk({"choices": [], "usage": {"prompt_tokens": 10}})

        assert assembler.usage_payload == {"prompt_tokens": 10}


class TestTheWholeResponsePath:
    def test_a_complete_response_is_read_under_the_same_rule(self):
        calls = parse_tool_calls(
            [
                {
                    "id": "call_a",
                    "index": 0,
                    "function": {"name": "get_price", "arguments": '{"symbol": "VCB"}'},
                },
                {
                    "id": "call_b",
                    "index": 1,
                    "function": {"name": "get_news", "arguments": '{"symbol": "FPT"}'},
                },
            ]
        )

        assert [call.name for call in calls] == ["get_price", "get_news"]
        assert calls[0].arguments == {"symbol": "VCB"}

    def test_unparseable_arguments_raise_there_too(self):
        with pytest.raises(MalformedArguments):
            parse_tool_calls(
                [{"id": "call_a", "function": {"name": "x", "arguments": "{oops"}}]
            )

    def test_no_tool_calls_is_not_a_failure(self):
        assert parse_tool_calls(None) == ()
        assert parse_tool_calls([]) == ()
