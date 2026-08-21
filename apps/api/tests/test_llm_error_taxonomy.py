"""What a refused request is, and what a log line may say about it.

Two things under test, both of them Phase 1 of the route-resilience work.

`classify_status` used to answer four questions and shrug at the fifth: every
4xx that was not a 401, 403, 408 or 429 came back a bare `LLMError`, so a
retired model, a transcript over the context window and a tool schema the route
would not accept were the same event in the log and the same key in the ops
snapshot. The five classes here are what that catch-all split into, and the
tests assert both directions: a body that names a condition gets its class, and
a body that names nothing keeps the shape it had.

`redact` is the other half. An error body is the one string in this system that
is copied verbatim into a log line, and a route that quotes the request it
refused quotes the `Authorization` header with it.
"""

from __future__ import annotations

import pytest

from src.core.llm.errors import (
    REDACTED,
    AuthUnavailable,
    ContentPolicyBlocked,
    ContextOverflow,
    GatewayTimeout,
    LLMError,
    ModelUnavailable,
    OutputCapExceeded,
    RouteAttempt,
    RouteRateLimited,
    llm_metrics,
    SchemaRejected,
    classify_status,
    redact,
)


class TestTheFourStatusClassesStillAnswerFirst:
    """The pre-existing branches are untouched by the 400 taxonomy below."""

    @pytest.mark.parametrize("status", [401, 403])
    def test_a_credential_rejection_is_auth_unavailable(self, status):
        assert isinstance(classify_status(status, "invalid api key"), AuthUnavailable)

    def test_a_429_is_a_rate_limit_even_when_its_body_names_tokens(self):
        # The body of a rate limit routinely mentions tokens per minute, which
        # is a marker the 400 taxonomy reads. Status wins, and has to: a 429 is
        # the route working, and answering it by shrinking the transcript would
        # spend a request to be told the same thing.
        error = classify_status(429, "rate limit: max_tokens per minute exceeded")
        assert isinstance(error, RouteRateLimited)

    @pytest.mark.parametrize("status", [408, 502, 503, 504, 500])
    def test_a_server_side_failure_is_a_gateway_timeout(self, status):
        assert isinstance(classify_status(status, "upstream"), GatewayTimeout)


class TestARefusedRequestGetsAClass:
    def test_an_oversized_output_ceiling_is_its_own_class(self):
        error = classify_status(
            400,
            "max_tokens is too large: 100000. This model supports at most "
            "16384 completion tokens",
        )
        assert isinstance(error, OutputCapExceeded)

    def test_an_oversized_transcript_is_the_other_class(self):
        error = classify_status(
            400,
            "This model's maximum context length is 8192 tokens. However, you "
            "requested 9000 tokens.",
        )
        assert isinstance(error, ContextOverflow)

    def test_the_anthropic_wording_for_an_oversized_transcript_lands_there_too(self):
        error = classify_status(400, "prompt is too long: 250000 tokens > 200000 maximum")
        assert isinstance(error, ContextOverflow)

    def test_an_output_cap_complaint_is_not_read_as_an_oversized_transcript(self):
        """The one ordering that is load bearing.

        A route complaining about the output ceiling says so in a sentence that
        also names the context window, because the sum is what overflowed. Read
        as a `ContextOverflow` it would be answered by trimming a transcript
        that fits — losing evidence the Turn already paid for and fixing
        nothing.
        """
        error = classify_status(
            400,
            "max_tokens is too large. The maximum context length is 8192 and "
            "your input is 1000 tokens.",
        )
        assert isinstance(error, OutputCapExceeded)
        assert not isinstance(error, ContextOverflow)

    def test_a_filtered_request_is_its_own_class(self):
        error = classify_status(400, '{"error":{"code":"content_policy_violation"}}')
        assert isinstance(error, ContentPolicyBlocked)

    def test_a_retired_model_is_its_own_class(self):
        error = classify_status(400, "model_not_found: nemotron-nano-9b-v2")
        assert isinstance(error, ModelUnavailable)

    def test_a_404_naming_a_model_is_a_model_that_is_not_served(self):
        """404 is in scope beside 400, because routes disagree about which to send."""
        error = classify_status(
            404,
            "The model `qwen-3-plus` does not exist or you do not have access to it.",
        )
        assert isinstance(error, ModelUnavailable)

    def test_a_refused_tool_schema_is_its_own_class(self):
        error = classify_status(400, "invalid schema for function 'get_analysis'")
        assert isinstance(error, SchemaRejected)

    def test_a_refused_tool_choice_lands_there_too(self):
        error = classify_status(400, '{"error":"tool_choice is not supported"}')
        assert isinstance(error, SchemaRejected)


class TestNamingAParameterIsNotComplainingAboutItsSize:
    """The false positives the first cut of these markers produced.

    All three are bodies real routes send, and all three used to classify as
    `OutputCapExceeded` — which would send Phase 4's recovery to lower a ceiling
    that was never too high, and tell the reader to ask a narrower question about
    what is a request-builder bug.
    """

    @pytest.mark.parametrize(
        "body",
        [
            # A real OpenAI 400: the parameter is the wrong name, not too big.
            "Unsupported parameter: 'max_tokens' is not supported with this "
            "model. Use 'max_completion_tokens' instead.",
            "Invalid value for max_tokens: must be a positive integer",
            # A route echoing the request it refused — the premise `redact`
            # exists for, so the common case rather than the exotic one.
            '{"error":{"message":"Invalid request","request":'
            '{"model":"m","max_completion_tokens":4000}}}',
        ],
    )
    def test_a_parameter_name_without_a_size_word_is_not_an_output_cap(self, body):
        assert type(classify_status(400, body)) is LLMError

    def test_a_retired_parameter_is_not_a_retired_model(self):
        """`deprecated` beside the word `model` is not the model deprecated.

        "for this model" is a prepositional phrase, and reading it as the subject
        would make Phase 4 switch models over a parameter this repository sends.
        """
        error = classify_status(
            400, "The parameter temperature has been deprecated for this model"
        )
        assert type(error) is LLMError

    @pytest.mark.parametrize(
        "body",
        [
            "model gpt-4-32k has been deprecated",
            "The model gpt-4-32k is deprecated; use gpt-4o",
        ],
    )
    def test_the_model_as_the_subject_still_classifies(self, body):
        assert isinstance(classify_status(400, body), ModelUnavailable)

    def test_a_model_that_produced_a_bad_tool_call_is_not_a_refused_schema(self):
        """Groq's `tool_use_failed` is the model failing, not our catalog.

        Logged as a refused schema it reads as a defect in this repository, at
        ERROR, and sends whoever reads it to inspect schemas the route accepted.
        """
        error = classify_status(
            400, "tool_use_failed: the model generated an invalid tool call"
        )
        assert type(error) is LLMError


class TestAnUnrecognisedBodyKeepsTheShapeItHad:
    """The fallthrough, which is the whole safety argument for the taxonomy.

    Recognition is done on the body, and a body is a string a route may reword
    at any time. A misread that produced the wrong class would send a recovery
    path after the wrong remedy; a misread that produces no class ends the Turn
    exactly as it did before any of this existed.
    """

    @pytest.mark.parametrize(
        "body",
        [
            "unknown parameter",
            "Bad Request",
            "",
            '{"error":{"message":"something the route has never said before"}}',
        ],
    )
    def test_it_is_an_llm_error_and_nothing_more_specific(self, body):
        error = classify_status(400, body)
        assert type(error) is LLMError

    def test_every_new_class_is_catchable_as_the_old_one(self):
        """A pure addition: `except LLMError` written before these still holds."""
        for body in (
            "max_tokens is too large",
            "maximum context length",
            "content_policy",
            "model_not_found",
            "invalid schema",
        ):
            with pytest.raises(LLMError):
                raise classify_status(400, body)


class TestNothingCredentialShapedReachesALog:
    @pytest.mark.parametrize(
        "secret",
        [
            "Authorization: Bearer sk-abc123def456ghi789jkl",
            "authorization=eyJhbGciOiJIUzI1NiJ9.payload",
            'api_key: "kt-live-9f8e7d6c5b4a3210"',
            "access-token=abcdefghijklmnop",
            "sk-proj-0123456789abcdefghij",
        ],
    )
    def test_the_value_is_gone_and_something_says_so(self, secret):
        scrubbed = redact(f'{{"error":"refused","echo":"{secret}"}}')
        assert REDACTED in scrubbed
        # The secret's own characters, not merely its field name.
        for token in ("sk-abc123def456ghi789jkl", "eyJhbGciOiJIUzI1NiJ9", "9f8e7d6c5b4a3210", "abcdefghijklmnop", "0123456789abcdefghij"):
            assert token not in scrubbed

    @pytest.mark.parametrize(
        ("header", "credential"),
        [
            ("Authorization: Basic dXNlcjpwYXNzd29yZA==", "dXNlcjpwYXNzd29yZA=="),
            ("Authorization: Token abcdef1234567890", "abcdef1234567890"),
            ("Authorization: ApiKey kt-live-9f8e7d6c5b4a", "kt-live-9f8e7d6c5b4a"),
            ("authorization=eyJhbGciOiJIUzI1NiJ9.body.sig", "eyJhbGciOiJIUzI1NiJ9"),
        ],
    )
    def test_a_scheme_that_is_not_bearer_loses_its_credential_too(
        self, header, credential
    ):
        """The failure mode this replaced was worse than no redaction.

        Matched as `authorization\\s*[:=]\\s*\\S+`, the `\\S+` stopped at the first
        space — so for Basic, Token or ApiKey the *scheme word* was redacted and
        the credential survived, on a line that read as though it had been
        scrubbed.
        """
        scrubbed = redact(header)
        assert credential not in scrubbed
        assert REDACTED in scrubbed

    @pytest.mark.parametrize(
        ("body", "credential"),
        [
            ("GET /v1/models?key=AIzaSyABCDEFGH12345678", "AIzaSyABCDEFGH12345678"),
            ("cookie: session=eyJhbGciOiJIUzI1NiJ9.x.y", "eyJhbGciOiJIUzI1NiJ9"),
            ("token=ghp_0123456789abcdefghij", "ghp_0123456789abcdefghij"),
        ],
    )
    def test_a_credential_arriving_without_a_header_name_is_caught(
        self, body, credential
    ):
        assert credential not in redact(body)

    def test_a_body_with_no_credential_survives_intact(self):
        body = "max_tokens is too large: 100000, and this model supports 16384"
        assert redact(body) == body

    def test_a_classified_error_can_be_logged_after_redaction(self):
        """The path the loop actually takes: classify, then redact, then log."""
        error = classify_status(
            400,
            'refused this request: {"headers":{"Authorization":"Bearer sk-secretvalue123"}}',
        )
        line = redact(str(error))
        assert "sk-secretvalue123" not in line
        # Redacting must not cost the classification: the operator still learns
        # which condition this was.
        assert isinstance(error, LLMError)


class TestTheMetricsLogLinesAreRedactedToo:
    """A 401 body is the densest credential surface in the whole system.

    The route was asked to accept a key and answered that the key is bad — and
    routes name the key when they say so. Naming a dead credential in a log is
    the point of the log line; naming it in a way that requires rotating it is
    not.
    """

    @pytest.mark.parametrize(
        "record",
        [
            "record_auth_failure",
            "record_rate_limit",
            "record_gateway_timeout",
            "record_malformed_arguments",
            "record_refusal",
        ],
    )
    def test_no_metrics_line_carries_a_credential(self, record, caplog):
        with caplog.at_level("INFO"):
            getattr(llm_metrics(), record)(
                "the route rejected the credential (401): invalid api key "
                "sk-livekey0123456789"
            )

        assert caplog.records
        for entry in caplog.records:
            assert "sk-livekey0123456789" not in entry.getMessage()


class TestATimeoutCarriesWhatWasSpentReachingIt:
    def test_the_defaults_are_honest_about_knowing_nothing(self):
        attempt = RouteAttempt()
        assert (attempt.attempts, attempt.elapsed_seconds, attempt.bytes_received) == (
            1,
            0.0,
            0,
        )

    def test_a_timeout_without_measurements_still_raises(self):
        """Diagnostics are additive: nothing branches on their absence."""
        assert GatewayTimeout("the route did not answer").attempt is None

    def test_an_unmeasured_attempt_does_not_claim_the_route_went_quiet(self):
        """A 5xx is a `GatewayTimeout` that arrives with no measurements.

        The route answered, quickly, with a body. Reporting its zeros as "0
        bytes received" would assert the one thing that number exists to rule
        out, so the log line has to be able to tell the two apart.
        """
        assert RouteAttempt(attempts=2).measured is False
        assert RouteAttempt(attempts=1, elapsed_seconds=4.2).measured is True

    def test_the_numbers_separate_two_incidents_with_one_class(self):
        silent = GatewayTimeout(
            "the route did not answer",
            attempt=RouteAttempt(attempts=2, elapsed_seconds=120.0, bytes_received=0),
        )
        cut_off = GatewayTimeout(
            "the route did not answer",
            attempt=RouteAttempt(attempts=1, elapsed_seconds=4.2, bytes_received=8_192),
        )
        assert silent.attempt.bytes_received == 0
        assert cut_off.attempt.bytes_received == 8_192
