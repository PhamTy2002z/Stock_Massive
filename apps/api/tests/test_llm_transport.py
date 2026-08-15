"""A complete request round-trips through the configured route.

The route is a mock transport rather than a network, which is the point: what
is under test is the contract this client keeps with an OpenAI-compatible
route — forced `tool_choice`, parallel tool calls through streaming, strict
`json_schema`, and the five error classes — not whether a socket works.
"""

from __future__ import annotations

import json
from datetime import date

import httpx
import pytest

from src.core.config import Settings
from src.core.llm.errors import (
    AuthUnavailable,
    GatewayTimeout,
    LLMError,
    MalformedArguments,
    ModelRefusal,
    ToolAttempts,
    llm_metrics,
    tool_error_result,
)
from src.core.llm.config import llm_config_from_settings
from src.core.llm.protocol import (
    CompletionRequest,
    JsonSchemaFormat,
    Message,
    Role,
    ToolSchema,
)
from src.core.llm.transport import OpenAICompatibleTransport

PRICE_TOOL = ToolSchema(
    name="get_price",
    description="The latest stored close for a symbol",
    parameters={
        "type": "object",
        "properties": {"symbol": {"type": "string"}},
        "required": ["symbol"],
        "additionalProperties": False,
    },
)

ANALYSIS_SCHEMA = JsonSchemaFormat(
    name="analysis",
    schema={
        "type": "object",
        "properties": {"headline": {"type": "string"}},
        "required": ["headline"],
        "additionalProperties": False,
    },
)


def config():
    return llm_config_from_settings(
        Settings(
            _env_file=None,
            alpha_desk_enabled=True,
            llm_base_url="https://route.test/v1",
            llm_api_key="a-token",
            llm_model_session="model-session",
            llm_pricing_version="2026-08",
            llm_pricing_effective_date=date(2026, 8, 1),
        )
    )


def sse(*chunks: dict) -> bytes:
    lines = [f"data: {json.dumps(chunk)}\n\n" for chunk in chunks]
    lines.append("data: [DONE]\n\n")
    return "".join(lines).encode()


class TransportHarness:
    """Exercise the internal transport without making it an application client."""

    def __init__(self, transport: OpenAICompatibleTransport) -> None:
        self.transport = transport

    async def complete(self, completion_request):
        return await self.transport.dispatch(completion_request)


def client(handler) -> TransportHarness:
    transport = httpx.MockTransport(handler)
    return TransportHarness(
        OpenAICompatibleTransport(
            config(), http_client=httpx.AsyncClient(transport=transport)
        )
    )


def request(**overrides) -> CompletionRequest:
    base = dict(
        model="model-session",
        messages=[Message(role=Role.USER, content="what is VCB worth?")],
    )
    base.update(overrides)
    return CompletionRequest(**base)


def text_chunk(content: str) -> dict:
    return {"model": "model-session", "choices": [{"delta": {"content": content}}]}


def usage_chunk(**counts) -> dict:
    return {"choices": [], "usage": counts}


class TestAPlainCompletion:
    pytestmark = pytest.mark.asyncio

    async def test_a_streamed_answer_comes_back_as_text(self):
        subject = client(
            lambda _request: httpx.Response(
                200,
                content=sse(
                    text_chunk("VCB closed at "),
                    text_chunk("59,700."),
                    {"choices": [{"delta": {}, "finish_reason": "stop"}]},
                ),
            )
        )

        result = await subject.complete(request())

        assert result.text == "VCB closed at 59,700."
        assert result.finish_reason == "stop"
        assert result.tool_calls == ()

    async def test_the_route_is_addressed_where_it_was_configured(self):
        seen = {}

        def handler(http_request: httpx.Request) -> httpx.Response:
            seen["url"] = str(http_request.url)
            seen["auth"] = http_request.headers.get("Authorization")
            return httpx.Response(200, content=sse(text_chunk("hello")))

        await client(handler).complete(request())

        assert seen["url"] == "https://route.test/v1/chat/completions"
        assert seen["auth"] == "Bearer a-token"

    async def test_a_non_streamed_answer_works_too(self):
        subject = client(
            lambda _request: httpx.Response(
                200,
                json={
                    "model": "model-session",
                    "choices": [
                        {"message": {"content": "VCB closed at 59,700."},
                         "finish_reason": "stop"}
                    ],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 20},
                },
            )
        )

        result = await subject.complete(request(stream=False))

        assert result.text == "VCB closed at 59,700."
        assert result.usage.input_tokens == 100
        assert result.usage.output_tokens == 20


class TestForcedToolChoice:
    pytestmark = pytest.mark.asyncio

    async def test_a_named_tool_is_forced_on_the_wire(self):
        seen = {}

        def handler(http_request: httpx.Request) -> httpx.Response:
            seen["body"] = json.loads(http_request.content)
            return httpx.Response(200, content=sse(text_chunk("ok")))

        await client(handler).complete(
            request(tools=[PRICE_TOOL], tool_choice="get_price")
        )

        assert seen["body"]["tool_choice"] == {
            "type": "function",
            "function": {"name": "get_price"},
        }
        assert seen["body"]["tools"][0]["function"]["name"] == "get_price"
        assert seen["body"]["tools"][0]["function"]["strict"] is True

    async def test_the_plain_choices_travel_as_themselves(self):
        seen = {}

        def handler(http_request: httpx.Request) -> httpx.Response:
            seen["body"] = json.loads(http_request.content)
            return httpx.Response(200, content=sse(text_chunk("ok")))

        await client(handler).complete(request(tools=[PRICE_TOOL], tool_choice="none"))

        assert seen["body"]["tool_choice"] == "none"

    async def test_a_forced_call_round_trips_with_parsed_arguments(self):
        subject = client(
            lambda _request: httpx.Response(
                200,
                content=sse(
                    {
                        "choices": [
                            {
                                "delta": {
                                    "tool_calls": [
                                        {
                                            "index": 0,
                                            "id": "call_a",
                                            "function": {
                                                "name": "get_price",
                                                "arguments": '{"symbol": "VCB"}',
                                            },
                                        }
                                    ]
                                }
                            }
                        ]
                    },
                    {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]},
                ),
            )
        )

        result = await subject.complete(
            request(tools=[PRICE_TOOL], tool_choice="get_price")
        )

        (call,) = result.tool_calls
        assert call.name == "get_price"
        assert call.arguments == {"symbol": "VCB"}
        assert result.finish_reason == "tool_calls"


class TestParallelToolCallsThroughStreaming:
    pytestmark = pytest.mark.asyncio

    async def test_two_calls_survive_an_interleaved_stream(self):
        """The failure that earned the hand-rolled transport, end to end."""
        subject = client(
            lambda _request: httpx.Response(
                200,
                content=sse(
                    _tool_chunk(0, id="call_a", name="get_price", arguments='{"sym'),
                    _tool_chunk(1, id="call_b", name="get_price", arguments='{"sy'),
                    _tool_chunk(0, arguments='bol": "VCB"}'),
                    _tool_chunk(1, arguments='mbol": "FPT"}'),
                    {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]},
                    usage_chunk(prompt_tokens=1_000, completion_tokens=50),
                ),
            )
        )

        result = await subject.complete(request(tools=[PRICE_TOOL]))

        assert [call.arguments["symbol"] for call in result.tool_calls] == [
            "VCB",
            "FPT",
        ]
        assert result.usage.input_tokens == 1_000

    async def test_parallel_calls_are_asked_for(self):
        seen = {}

        def handler(http_request: httpx.Request) -> httpx.Response:
            seen["body"] = json.loads(http_request.content)
            return httpx.Response(200, content=sse(text_chunk("ok")))

        await client(handler).complete(request(tools=[PRICE_TOOL]))

        assert seen["body"]["parallel_tool_calls"] is True

    async def test_unparseable_arguments_raise_rather_than_return(self):
        subject = client(
            lambda _request: httpx.Response(
                200,
                content=sse(
                    _tool_chunk(0, id="call_a", name="get_price", arguments='{"symbol"'),
                    {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]},
                ),
            )
        )

        with pytest.raises(MalformedArguments):
            await subject.complete(request(tools=[PRICE_TOOL]))


class TestStrictStructuredOutput:
    pytestmark = pytest.mark.asyncio

    async def test_the_schema_is_sent_strict(self):
        seen = {}

        def handler(http_request: httpx.Request) -> httpx.Response:
            seen["body"] = json.loads(http_request.content)
            return httpx.Response(200, content=sse(text_chunk('{"headline": "flat"}')))

        await client(handler).complete(request(response_format=ANALYSIS_SCHEMA))

        assert seen["body"]["response_format"]["type"] == "json_schema"
        assert seen["body"]["response_format"]["json_schema"]["strict"] is True
        assert seen["body"]["response_format"]["json_schema"]["name"] == "analysis"

    async def test_a_conforming_answer_round_trips(self):
        subject = client(
            lambda _request: httpx.Response(
                200, content=sse(text_chunk('{"headline": "VCB was flat"}'))
            )
        )

        result = await subject.complete(request(response_format=ANALYSIS_SCHEMA))

        assert json.loads(result.text) == {"headline": "VCB was flat"}


class TestTheErrorTaxonomy:
    pytestmark = pytest.mark.asyncio

    async def test_a_401_is_auth_unavailable_and_is_never_retried(self):
        attempts = {"count": 0}

        def handler(_request: httpx.Request) -> httpx.Response:
            attempts["count"] += 1
            return httpx.Response(401, text="token expired")

        with pytest.raises(AuthUnavailable):
            await client(handler).complete(request())

        assert attempts["count"] == 1

    async def test_a_403_is_auth_unavailable_too(self):
        with pytest.raises(AuthUnavailable):
            await client(lambda _r: httpx.Response(403, text="forbidden")).complete(
                request()
            )

    async def test_a_504_is_a_gateway_timeout_and_is_retried_twice(self):
        attempts = {"count": 0}

        def handler(_request: httpx.Request) -> httpx.Response:
            attempts["count"] += 1
            return httpx.Response(504, text="upstream timeout")

        with pytest.raises(GatewayTimeout):
            await client(handler).complete(request())

        assert attempts["count"] == 2

    async def test_a_timeout_on_the_socket_is_the_same_class(self):
        attempts = {"count": 0}

        def handler(http_request: httpx.Request):
            attempts["count"] += 1
            raise httpx.ReadTimeout("too slow", request=http_request)

        with pytest.raises(GatewayTimeout):
            await client(handler).complete(request())

        assert attempts["count"] == 2

    async def test_a_retry_that_succeeds_returns_the_answer(self):
        attempts = {"count": 0}

        def handler(_request: httpx.Request) -> httpx.Response:
            attempts["count"] += 1
            if attempts["count"] == 1:
                return httpx.Response(503, text="try again")
            return httpx.Response(200, content=sse(text_chunk("second time lucky")))

        result = await client(handler).complete(request())

        assert result.text == "second time lucky"
        assert attempts["count"] == 2

    async def test_a_refusal_is_surfaced_verbatim(self):
        subject = client(
            lambda _r: httpx.Response(
                200,
                content=sse(
                    {"choices": [{"delta": {"refusal": "I can't help with that."}}]}
                ),
            )
        )

        with pytest.raises(ModelRefusal) as exc_info:
            await subject.complete(request())

        assert exc_info.value.refusal == "I can't help with that."

    async def test_a_refusal_in_a_whole_response_is_surfaced_too(self):
        subject = client(
            lambda _r: httpx.Response(
                200,
                json={
                    "model": "model-session",
                    "choices": [{"message": {"refusal": "No."}, "finish_reason": "stop"}],
                },
            )
        )

        with pytest.raises(ModelRefusal, match="No."):
            await subject.complete(request(stream=False))

    async def test_a_400_is_not_retried_and_is_not_one_of_the_five(self):
        attempts = {"count": 0}

        def handler(_request: httpx.Request) -> httpx.Response:
            attempts["count"] += 1
            return httpx.Response(400, text="unknown parameter")

        with pytest.raises(LLMError) as exc_info:
            await client(handler).complete(request())

        assert not isinstance(exc_info.value, GatewayTimeout)
        assert attempts["count"] == 1


class TestToolErrors:
    def test_a_failed_tool_answers_the_model_with_a_shape(self):
        result = tool_error_result("call_a", "get_price", "no snapshot for VCB")

        assert result["status"] == "tool_error"
        assert result["tool_call_id"] == "call_a"
        assert result["error"] == "no snapshot for VCB"

    def test_the_same_tool_gets_two_attempts_and_no_more(self):
        attempts = ToolAttempts()

        assert attempts.may_attempt("get_price")
        attempts.record_failure("get_price")
        assert attempts.may_attempt("get_price")
        attempts.record_failure("get_price")
        assert attempts.exhausted("get_price")

    def test_one_exhausted_tool_does_not_exhaust_another(self):
        attempts = ToolAttempts()

        attempts.record_failure("get_price")
        attempts.record_failure("get_price")

        assert attempts.exhausted("get_price")
        assert attempts.may_attempt("get_news")


class TestNoAutoDisable:
    @pytest.mark.asyncio
    async def test_malformed_arguments_are_counted_and_change_nothing_else(self):
        """Counted and logged loudly; the operator flips the flag by hand."""
        llm_metrics().reset()
        subject = client(
            lambda _r: httpx.Response(
                200,
                content=sse(
                    _tool_chunk(0, id="call_a", name="get_price", arguments="{oops"),
                ),
            )
        )

        for _ in range(3):
            with pytest.raises(MalformedArguments):
                await subject.complete(request(tools=[PRICE_TOOL]))

        assert llm_metrics().malformed_arguments == 3
        # Still enabled, still the same route: nothing here may disable one.
        assert subject.transport._config.enabled is True
        llm_metrics().reset()

    def test_nothing_in_the_package_writes_the_feature_flag(self):
        from pathlib import Path

        package = Path(__file__).resolve().parents[1] / "src" / "core" / "llm"
        writers = [
            path.name
            for path in package.glob("*.py")
            if "alpha_desk_enabled =" in path.read_text(encoding="utf-8")
        ]

        assert writers == []


class TestUsageAccounting:
    pytestmark = pytest.mark.asyncio

    async def test_cached_and_reasoning_tokens_are_not_counted_twice(self):
        subject = client(
            lambda _r: httpx.Response(
                200,
                content=sse(
                    text_chunk("answered"),
                    usage_chunk(
                        prompt_tokens=1_000,
                        completion_tokens=300,
                        prompt_tokens_details={"cached_tokens": 400},
                        completion_tokens_details={"reasoning_tokens": 250},
                    ),
                ),
            )
        )

        usage = (await subject.complete(request())).usage

        assert usage.input_tokens == 600
        assert usage.cached_input_tokens == 400
        assert usage.output_tokens == 50
        assert usage.reasoning_tokens == 250
        assert usage.total_tokens == 1_300

    async def test_a_cache_write_is_its_own_counter(self):
        subject = client(
            lambda _r: httpx.Response(
                200,
                content=sse(
                    text_chunk("answered"),
                    usage_chunk(
                        prompt_tokens=1_000,
                        completion_tokens=10,
                        prompt_tokens_details={"cache_write_tokens": 900},
                    ),
                ),
            )
        )

        usage = (await subject.complete(request())).usage

        assert usage.cache_write_tokens == 900
        assert usage.input_tokens == 100

    async def test_usage_is_asked_for_on_a_stream(self):
        seen = {}

        def handler(http_request: httpx.Request) -> httpx.Response:
            seen["body"] = json.loads(http_request.content)
            return httpx.Response(200, content=sse(text_chunk("ok")))

        await client(handler).complete(request())

        assert seen["body"]["stream_options"] == {"include_usage": True}


class TestNoSdkOrFramework:
    def test_requirements_gained_no_provider_sdk(self):
        from pathlib import Path

        requirements = (
            Path(__file__).resolve().parents[1] / "requirements.txt"
        ).read_text(encoding="utf-8").lower()

        for forbidden in (
            "openai",
            "anthropic",
            "langchain",
            "langgraph",
            "pydantic-ai",
            "litellm",
            "instructor",
        ):
            assert forbidden not in requirements, forbidden


def _tool_chunk(index: int, *, id=None, name=None, arguments=None) -> dict:
    function = {}
    if name is not None:
        function["name"] = name
    if arguments is not None:
        function["arguments"] = arguments
    call: dict = {"index": index}
    if id is not None:
        call["id"] = id
    if function:
        call["function"] = function
    return {"choices": [{"delta": {"tool_calls": [call]}}]}
