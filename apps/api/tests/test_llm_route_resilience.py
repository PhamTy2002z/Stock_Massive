"""Phase 4: every route failure has an action, and every guard fails open.

Phase 1 gave the failures names. These are the tests for what is done about
them — the recovery table, the shared rate-limit breaker, the deterministic-empty
guard, the split between our deadline and the route's, and the bounded read of a
refused body.

The through-line, and the reason each test says it out loud: **no guard added
here may end a Turn that would otherwise have survived.** A breaker that cannot
reach Redis admits the call, an empty answer with no usage keeps its retry, and a
transport that cannot be rebuilt is asked again anyway.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone

import httpx
from types import MappingProxyType

import pytest

from src.core.llm import (
    AuthUnavailable,
    BudgetLane,
    CallOwner,
    Completion,
    CompletionRequest,
    ContentPolicyBlocked,
    ContentSegment,
    ContextOverflow,
    DeadlineExpired,
    GatewayTimeout,
    LLMError,
    MalformedArguments,
    Message,
    ModelRefusal,
    ModelUnavailable,
    OutputCapExceeded,
    OwnerType,
    Reservation,
    Role,
    RouteAction,
    RouteBreaker,
    RouteRateLimited,
    SchemaRejected,
    SpendRequest,
    Usage,
    Workload,
    recovery_for,
    route_key,
)
from src.core.llm.breaker import DEFAULT_HOLD_SECONDS, MAX_HOLD_SECONDS
from src.core.llm.client import (
    EMPTY_RUN_FOR_DETERMINISM,
    MAX_EMPTY_ATTEMPTS,
    MAX_ROUTE_ATTEMPTS,
    ReservedLLMClient,
)
from src.core.llm.config import (
    BudgetLanes,
    LLMConfig,
    LLMRoute,
    MAX_TIMEOUT_SECONDS,
    MIN_TIMEOUT_SECONDS,
    PricingTable,
    TokenPrices,
    clamp_timeout,
)
from src.core.llm.errors import MAX_GATEWAY_ATTEMPTS
from src.core.llm.transport import OpenAICompatibleTransport
from src.core.llm.recovery import RECOVERIES, UNCOVERED, route_error_classes
from tests.fake_redis import FakeRedis, PositionalFakeRedis

SESSION_MODEL = "session-model"
BATCH_MODEL = "batch-model"
BASE_URL = "https://llm.example/v1"


def config(**overrides) -> LLMConfig:
    base = dict(
        enabled=True,
        route=LLMRoute(base_url=BASE_URL, api_key="secret"),
        models=MappingProxyType(
            {Workload.BATCH: BATCH_MODEL, Workload.SESSION: SESSION_MODEL}
        ),
        pricing=PricingTable(
            version="2026-08",
            effective_from=date(2026, 8, 1),
            batch=TokenPrices(input=0.5, cached_input=0.1, cache_write=0.5, output=1.0),
            session=TokenPrices(input=2.0, cached_input=0.2, cache_write=2.0, output=5.0),
        ),
        lanes=BudgetLanes(
            monthly_envelope_usd=45,
            analysis_usd=10,
            turn_usd=30,
            emergency_usd=5,
        ),
    )
    base.update(overrides)
    return LLMConfig(**base)


class Ledger:
    """Admission reduced to what these tests assert about it."""

    def __init__(self) -> None:
        self.reserved: list[tuple[SpendRequest, str]] = []
        self.reconciled: list[Usage] = []

    def reserve(self, candidate: SpendRequest, model: str) -> Reservation:
        self.reserved.append((candidate, model))
        return Reservation(
            id=len(self.reserved),
            owner=candidate.owner,
            lane=candidate.lane,
            model=model,
            reserved_micro_usd=1_000,
            provider_called_at=datetime(2026, 8, 21, tzinfo=timezone.utc),
        )

    def reconcile(self, reservation: Reservation, usage: Usage) -> None:
        self.reconciled.append(usage)


class Script:
    """A transport that answers from a list, and counts its rebuilds."""

    def __init__(self, *items) -> None:
        self.items = list(items)
        self.seen: list[CompletionRequest] = []
        self.rebuilds = 0

    async def dispatch(self, request: CompletionRequest) -> Completion:
        self.seen.append(request)
        item = self.items.pop(0) if self.items else answer()
        if isinstance(item, BaseException):
            raise item
        return item

    async def rebuild(self) -> bool:
        self.rebuilds += 1
        return True


def answer(text: str = "xong") -> Completion:
    return Completion(
        model=SESSION_MODEL,
        text=text,
        usage=Usage(input_tokens=100, output_tokens=20),
    )


def empty(
    model: str = SESSION_MODEL,
    usage: Usage | None = Usage(input_tokens=100, output_tokens=0),
    finish_reason: str = "stop",
) -> Completion:
    return Completion(
        model=model, text="", usage=usage, finish_reason=finish_reason
    )


def spend() -> SpendRequest:
    return SpendRequest(
        owner=CallOwner(OwnerType.TURN_REQUEST_MESSAGE, "42", user_id=7),
        lane=BudgetLane.TURN,
        workload=Workload.SESSION,
        input_tokens=1_000,
        output_tokens=500,
    )


def request(model: str = SESSION_MODEL) -> CompletionRequest:
    return CompletionRequest(
        model=model, messages=(Message(role=Role.USER, content="FPT?"),)
    )


def client(transport, *, breaker=None, cfg=None) -> ReservedLLMClient:
    # ``sleep`` is stubbed everywhere: the jitter is asserted on its own, and a
    # suite that actually waits for backoff is a suite nobody runs.
    return ReservedLLMClient(
        transport,
        Ledger(),
        config=cfg or config(),
        breaker=breaker or RouteBreaker(enabled=False),
        sleep=lambda _seconds: asyncio.sleep(0),
    )


# --- the table ------------------------------------------------------------


def test_every_route_failure_has_an_action_or_a_stated_reason():
    """The success criterion, as a test rather than a claim.

    Walked from the **class tree** rather than from the table's own keys: a
    completeness check that reads what it is checking proves only that the table
    equals itself, and a class added to ``errors.py`` next month would inherit
    ``LLMError``'s terminal entry in silence — which is the Phase-1 shapelessness
    returning through a new door.
    """
    classes = route_error_classes()
    assert len(classes) >= 12, "the walk stopped finding the taxonomy"

    for klass in classes:
        assert klass in RECOVERIES, (
            f"{klass.__name__} has no recovery; add one, or name it in "
            "recovery.UNCOVERED with the reason it never reaches the table"
        )
        recovery = RECOVERIES[klass]
        assert recovery.reason.strip(), f"{klass.__name__} has no stated reason"
        assert len(recovery.reason) > 40, f"{klass.__name__} has a placeholder reason"

    # And the exclusion is a decision, not an oversight.
    assert "ToolError" in UNCOVERED


@pytest.mark.parametrize(
    ("error", "action"),
    [
        (ContextOverflow("x"), RouteAction.COMPRESS),
        (OutputCapExceeded("x"), RouteAction.LOWER_OUTPUT_CAP),
        (DeadlineExpired("x"), RouteAction.REBUILD_AND_RETRY),
        (GatewayTimeout("x"), RouteAction.REBUILD_AND_RETRY),
        (ModelUnavailable("x"), RouteAction.SWITCH_MODEL),
        (RouteRateLimited("x"), RouteAction.TERMINAL),
        (ContentPolicyBlocked("x"), RouteAction.TERMINAL),
        (SchemaRejected("x"), RouteAction.TERMINAL),
        (AuthUnavailable("x"), RouteAction.TERMINAL),
        (ModelRefusal("x"), RouteAction.TERMINAL),
        (MalformedArguments("x"), RouteAction.TERMINAL),
        (LLMError("x"), RouteAction.TERMINAL),
    ],
)
def test_each_class_maps_to_the_action_the_table_declares(error, action):
    assert recovery_for(error).action is action


def test_an_unknown_failure_is_terminal_rather_than_retried():
    """The pre-existing behaviour, kept as the fallback.

    Guessing a recovery for a failure nobody has classified is how a recovery
    path ends up lowering a ceiling that was never too high.
    """

    class NovelFailure(LLMError):
        pass

    assert recovery_for(NovelFailure("x")).action is RouteAction.TERMINAL
    assert recovery_for(RuntimeError("not ours")).action is RouteAction.TERMINAL


def test_a_deadline_expiry_inherits_nothing_it_should_not():
    """``DeadlineExpired`` is a ``GatewayTimeout``, and has its own entry.

    The subclassing is what keeps every ``except GatewayTimeout`` written before
    it working; the entry is what lets the two be told apart.
    """
    assert isinstance(DeadlineExpired("x"), GatewayTimeout)
    assert recovery_for(DeadlineExpired("x")) is not recovery_for(GatewayTimeout("x"))


# --- the client's recoveries ---------------------------------------------


class TestRecoveryInTheClient:
    pytestmark = pytest.mark.asyncio

    async def test_our_expired_deadline_rebuilds_the_transport_before_retrying(self):
        transport = Script(DeadlineExpired("we stopped waiting"), answer())

        result = await client(transport).complete(request(), spend())

        assert result.text == "xong"
        assert transport.rebuilds == 1
        assert len(transport.seen) == 2

    async def test_a_route_that_times_out_twice_is_not_asked_a_third_time(self):
        transport = Script(
            GatewayTimeout("504"), GatewayTimeout("504"), answer()
        )

        with pytest.raises(GatewayTimeout) as raised:
            await client(transport).complete(request(), spend())

        assert len(transport.seen) == MAX_GATEWAY_ATTEMPTS
        # Stamped where the count is knowable, for the line the loop logs.
        assert raised.value.attempt is not None
        assert raised.value.attempt.attempts == MAX_GATEWAY_ATTEMPTS

    async def test_a_retry_is_funded_from_the_emergency_lane(self):
        transport = Script(DeadlineExpired("we stopped waiting"), answer())
        ledger = Ledger()
        reserved = ReservedLLMClient(
            transport,
            ledger,
            config=config(),
            breaker=RouteBreaker(enabled=False),
            sleep=lambda _seconds: asyncio.sleep(0),
        )

        await reserved.complete(request(), spend())

        assert [candidate.lane for candidate, _ in ledger.reserved] == [
            BudgetLane.TURN,
            BudgetLane.EMERGENCY,
        ]

    async def test_an_unserved_model_fails_over_to_the_other_of_the_pair(self):
        """And the workload moves with it, or the ledger prices the wrong lane.

        ``SpendAdmission.reserve`` refuses a model that is not the one configured
        for the workload it was handed, which is the check that makes this a
        reservation rather than the silent swap the transport refuses to do.
        """
        transport = Script(ModelUnavailable("no such model"), answer())
        ledger = Ledger()
        reserved = ReservedLLMClient(
            transport,
            ledger,
            config=config(),
            breaker=RouteBreaker(enabled=False),
            sleep=lambda _seconds: asyncio.sleep(0),
        )

        await reserved.complete(request(), spend())

        assert [model for _, model in ledger.reserved] == [SESSION_MODEL, BATCH_MODEL]
        assert [candidate.workload for candidate, _ in ledger.reserved] == [
            Workload.SESSION,
            Workload.BATCH,
        ]
        assert transport.seen[1].model == BATCH_MODEL

    async def test_a_failover_happens_once_and_then_the_failure_stands(self):
        transport = Script(
            ModelUnavailable("no such model"), ModelUnavailable("nor that one")
        )

        with pytest.raises(ModelUnavailable):
            await client(transport).complete(request(), spend())

        assert len(transport.seen) == 2

    async def test_a_route_with_one_configured_model_has_nowhere_to_fail_over_to(self):
        one_model = config(
            models=MappingProxyType(
                {Workload.BATCH: SESSION_MODEL, Workload.SESSION: SESSION_MODEL}
            )
        )
        transport = Script(ModelUnavailable("no such model"))

        with pytest.raises(ModelUnavailable):
            await client(transport, cfg=one_model).complete(request(), spend())

        assert len(transport.seen) == 1

    async def test_the_caller_owns_compression_and_the_output_ceiling(self):
        """Two actions the client must hand up rather than act on.

        The transcript and the output ceiling are the caller's. A client that
        shrank either would be editing a request it was asked to send, and the
        agent loop — which owns both — would never learn the route refused.
        """
        for failure in (ContextOverflow("too long"), OutputCapExceeded("too big")):
            transport = Script(failure, answer())
            with pytest.raises(type(failure)):
                await client(transport).complete(request(), spend())
            assert len(transport.seen) == 1

    async def test_a_terminal_failure_is_never_retried(self):
        for failure in (
            AuthUnavailable("401"),
            ContentPolicyBlocked("filtered"),
            SchemaRejected("bad schema"),
            MalformedArguments("not json"),
        ):
            transport = Script(failure, answer())
            with pytest.raises(type(failure)):
                await client(transport).complete(request(), spend())
            assert len(transport.seen) == 1, type(failure).__name__

    async def test_usage_on_a_failed_attempt_is_still_reconciled(self):
        """A refused call that burned tokens burned them (``docs/adr/0014``)."""
        failure = GatewayTimeout("504", usage=Usage(input_tokens=90))
        ledger = Ledger()
        reserved = ReservedLLMClient(
            Script(failure, failure),
            ledger,
            config=config(),
            breaker=RouteBreaker(enabled=False),
            sleep=lambda _seconds: asyncio.sleep(0),
        )

        with pytest.raises(GatewayTimeout):
            await reserved.complete(request(), spend())

        assert ledger.reconciled == [Usage(input_tokens=90)] * 2


class TestJitteredBackoff:
    pytestmark = pytest.mark.asyncio

    async def test_the_wait_between_attempts_is_jittered_and_bounded(self):
        """Fixed backoff is what turns one rate limit into a thundering herd.

        Every session that failed at the same moment comes back at the same
        moment, and the route refuses the whole cohort a second time. So the wait
        is drawn from a range rather than computed, and the range is bounded so a
        retry cannot outlive the reader's patience.
        """
        waits: list[float] = []

        async def record(seconds: float) -> None:
            waits.append(seconds)

        reserved = ReservedLLMClient(
            Script(DeadlineExpired("we stopped waiting"), answer()),
            Ledger(),
            config=config(),
            breaker=RouteBreaker(enabled=False),
            sleep=record,
        )

        await reserved.complete(request(), spend())

        assert len(waits) == 1
        assert 0 <= waits[0] <= 0.5


# --- the deterministic-empty guard ---------------------------------------


class TestEmptyAnswerGuard:
    pytestmark = pytest.mark.asyncio

    async def test_two_empties_with_the_same_signature_change_model(self):
        """NS-503, the measured version: ~$2.33 charged for an empty answer.

        Two empties from one model with the same finish reason and no output
        tokens is one thing happening twice. A third identical request buys a
        third identical answer, so what changes is the model rather than the
        number of attempts.
        """
        transport = Script(empty(), empty(), answer())
        ledger = Ledger()
        reserved = ReservedLLMClient(
            transport,
            ledger,
            config=config(),
            breaker=RouteBreaker(enabled=False),
            sleep=lambda _seconds: asyncio.sleep(0),
        )

        result = await reserved.complete(request(), spend())

        assert result.text == "xong"
        assert len(transport.seen) == EMPTY_RUN_FOR_DETERMINISM + 1
        assert transport.seen[-1].model == BATCH_MODEL

    async def test_an_empty_answer_with_no_usage_keeps_its_retry(self):
        """Fail-open, and the exact place it matters.

        The evidence that the route generated nothing is the usage that is
        missing. Calling that deterministic would give up on a model over a
        counter the route declined to send.
        """
        transport = Script(empty(usage=None), answer())

        result = await client(transport).complete(request(), spend())

        assert result.text == "xong"
        assert len(transport.seen) == 2

    async def test_reasoning_tokens_count_as_generation(self):
        """A thinking model that spent its ceiling on hidden thinking is not empty.

        It is a truncation, and the remedy for a truncation is not to give up on
        the route that produced it. So the retry stands and the run never becomes
        conclusive, however many of these arrive.
        """
        thinking = empty(usage=Usage(input_tokens=100, reasoning_tokens=800))

        retried = Script(thinking, answer())
        assert (await client(retried).complete(request(), spend())).text == "xong"

        transport = Script(thinking, thinking, answer())
        result = await client(transport).complete(request(), spend())

        # The budget runs out before the run is ever called conclusive, so the
        # model is never switched on this evidence.
        assert result.text == ""
        assert len(transport.seen) == MAX_EMPTY_ATTEMPTS
        assert all(seen.model == SESSION_MODEL for seen in transport.seen)

    async def test_empties_from_different_models_are_two_incidents(self):
        transport = Script(empty(model="a"), empty(model="b"), answer())

        await client(transport).complete(request(), spend())

        assert all(seen.model == SESSION_MODEL for seen in transport.seen)

    async def test_an_empty_answer_is_returned_rather_than_raised(self):
        """The guard bounds spend; it does not invent a way to end a Turn.

        An empty answer is what the route returned. A new exception class here
        would end Turns that today survive on their partial answer and traces.
        """
        transport = Script(*[empty()] * (MAX_ROUTE_ATTEMPTS + 2))
        one_model = config(
            models=MappingProxyType(
                {Workload.BATCH: SESSION_MODEL, Workload.SESSION: SESSION_MODEL}
            )
        )

        result = await client(transport, cfg=one_model).complete(request(), spend())

        assert result.text == ""
        assert len(transport.seen) <= MAX_EMPTY_ATTEMPTS


# --- the shared breaker ---------------------------------------------------


class TestRouteBreaker:
    def test_a_rate_limit_holds_the_route_for_what_the_headers_said(self):
        now = [1_000_000.0]
        shared = FakeRedis(clock=lambda: now[0])
        breaker = RouteBreaker(redis_factory=lambda: shared, clock=lambda: now[0])
        key = route_key(BASE_URL, SESSION_MODEL)

        held = breaker.record_rate_limit(key, retry_after=30.0)

        assert 29 <= held <= 30
        assert 29 <= breaker.open_for(key) <= 30

        now[0] += 31
        assert breaker.open_for(key) == 0.0

    def test_the_collector_and_an_interactive_turn_read_one_answer(self):
        """The whole point of the module, as two clients over one Redis.

        Before it, each process discovered the rate limit for itself at the cost
        of one refused request, and the Collector and a Turn could refuse each
        other all night.
        """
        now = [1_000_000.0]
        key = route_key(BASE_URL, SESSION_MODEL)

        # Both client dialects this deployment can be configured with: Upstash
        # over REST takes keyword lists, redis-py takes the key count
        # positionally, and one of them being untested is how that breaks in
        # production only.
        for server in (
            FakeRedis(clock=lambda: now[0]),
            PositionalFakeRedis(clock=lambda: now[0]),
        ):
            collector = RouteBreaker(
                redis_factory=lambda bound=server: bound, clock=lambda: now[0]
            )
            interactive = RouteBreaker(
                redis_factory=lambda bound=server: bound, clock=lambda: now[0]
            )

            collector.record_rate_limit(key, retry_after=45.0)

            assert interactive.open_for(key) > 0

    def test_a_fractional_clock_still_opens_and_extends_the_hold(self):
        """Redis parses ``PX`` as a strict integer and refuses a fractional one.

        A clock in milliseconds is fractional, and the value the script stores
        becomes the next caller's ``held`` — so the *extend* path is where an
        unfloored millisecond count fails on a real server. ``tests/fake_redis``
        refuses a fractional ``PX`` for exactly this reason, which is what makes
        this test able to fail.
        """
        now = [1_755_000_020.123_456]
        shared = FakeRedis(clock=lambda: now[0])
        breaker = RouteBreaker(redis_factory=lambda: shared, clock=lambda: now[0])
        key = route_key(BASE_URL, SESSION_MODEL)

        assert breaker.record_rate_limit(key, retry_after=30.5) > 0
        # The extend: a second 429 read back through the value just stored.
        assert breaker.record_rate_limit(key, retry_after=45.25) > 0
        assert breaker.open_for(key) > 40

        # And the reset-epoch path, whose hold is a difference of two floats.
        breaker.clear(key)
        assert breaker.record_rate_limit(key, reset_at=now[0] + 12.75) > 0

    def test_a_second_caller_cannot_shorten_the_hold(self):
        now = [1_000_000.0]
        shared = FakeRedis(clock=lambda: now[0])
        breaker = RouteBreaker(redis_factory=lambda: shared, clock=lambda: now[0])
        key = route_key(BASE_URL, SESSION_MODEL)

        breaker.record_rate_limit(key, retry_after=120.0)
        breaker.record_rate_limit(key, retry_after=5.0)

        assert breaker.open_for(key) > 100

    def test_a_hold_is_capped_however_far_off_the_reset_is(self):
        now = [1_000_000.0]
        shared = FakeRedis(clock=lambda: now[0])
        breaker = RouteBreaker(redis_factory=lambda: shared, clock=lambda: now[0])
        key = route_key(BASE_URL, SESSION_MODEL)

        breaker.record_rate_limit(key, reset_at=now[0] + 8 * 3600)

        assert breaker.open_for(key) <= MAX_HOLD_SECONDS

    def test_a_429_with_no_headers_still_opens_the_breaker(self):
        now = [1_000_000.0]
        shared = FakeRedis(clock=lambda: now[0])
        breaker = RouteBreaker(redis_factory=lambda: shared, clock=lambda: now[0])
        key = route_key(BASE_URL, SESSION_MODEL)

        held = breaker.record_rate_limit(key)

        assert 0 < held <= DEFAULT_HOLD_SECONDS

    def test_an_unreachable_redis_admits_the_call(self):
        """The decision this module departs from ``core/quota.py`` on.

        There, a call the arbiter cannot admit is a call that must not happen: the
        subject is a paid account allowance. Here the subject is a route that
        enforces its own limit anyway, and the cost of being wrong is a blank
        answer on somebody's screen.
        """

        def broken() -> object:
            raise RuntimeError("redis is down")

        breaker = RouteBreaker(redis_factory=broken)
        key = route_key(BASE_URL, SESSION_MODEL)

        assert breaker.open_for(key) == 0.0
        assert breaker.record_rate_limit(key, retry_after=60.0) == 0.0
        assert breaker.open_for(key) == 0.0

    def test_no_redis_configured_admits_the_call(self):
        breaker = RouteBreaker(redis_factory=lambda: None)

        assert breaker.open_for(route_key(BASE_URL, SESSION_MODEL)) == 0.0

    def test_the_kill_switch_disables_it_entirely(self):
        shared = FakeRedis()
        breaker = RouteBreaker(redis_factory=lambda: shared, enabled=False)
        key = route_key(BASE_URL, SESSION_MODEL)

        breaker.record_rate_limit(key, retry_after=60.0)

        assert breaker.open_for(key) == 0.0
        assert shared.get(key) is None

    def test_the_key_carries_the_host_and_the_model_and_no_credential(self):
        key = route_key("https://llm.example/v1?key=sk-live-123", SESSION_MODEL)

        assert "llm.example" in key
        assert SESSION_MODEL in key
        assert "sk-live-123" not in key
        assert key != route_key(BASE_URL, BATCH_MODEL)

        # Userinfo too, which ``netloc`` keeps and ``hostname`` does not: a base
        # URL of this shape would otherwise write the credential into the key and
        # into the log line beside it.
        embedded = route_key("https://sk-live-456@llm.example/v1", SESSION_MODEL)
        assert "sk-live-456" not in embedded
        assert "llm.example" in embedded
        # A port still distinguishes two routes on one host.
        assert route_key("https://llm.example:8443/v1", SESSION_MODEL) != key


class TestBreakerInTheClient:
    pytestmark = pytest.mark.asyncio

    async def test_a_429_is_written_where_the_next_caller_reads_it(self):
        shared = FakeRedis(clock=lambda: 1_000_000.0)
        breaker = RouteBreaker(
            redis_factory=lambda: shared, clock=lambda: 1_000_000.0
        )
        transport = Script(
            RouteRateLimited("out of allowance (429)", retry_after=60.0)
        )

        with pytest.raises(RouteRateLimited):
            await client(transport, breaker=breaker).complete(request(), spend())

        assert breaker.open_for(route_key(BASE_URL, SESSION_MODEL)) > 0

    async def test_a_held_route_is_refused_before_the_paid_call(self):
        shared = FakeRedis(clock=lambda: 1_000_000.0)
        breaker = RouteBreaker(
            redis_factory=lambda: shared, clock=lambda: 1_000_000.0
        )
        breaker.record_rate_limit(route_key(BASE_URL, SESSION_MODEL), retry_after=60.0)
        transport = Script(answer())

        with pytest.raises(RouteRateLimited) as raised:
            await client(transport, breaker=breaker).complete(request(), spend())

        assert transport.seen == []
        assert raised.value.retry_after is not None

    async def test_a_rate_limit_is_never_retried_even_with_the_breaker_off(self):
        """``errors.RouteRateLimited`` is unchanged by any of this.

        The route answered, precisely, and what it said was *not now*. The
        breaker shares that answer; it does not turn it into a retry.
        """
        transport = Script(
            RouteRateLimited("out of allowance (429)"), answer()
        )

        with pytest.raises(RouteRateLimited):
            await client(transport).complete(request(), spend())

        assert len(transport.seen) == 1


class TestRebuildingASharedTransport:
    pytestmark = pytest.mark.asyncio

    async def test_the_replaced_client_is_not_closed_under_the_turns_using_it(self):
        """The whole process shares one ``AsyncClient`` (``agent/service.py``).

        Closing it on rebuild aborts every *other* Turn's in-flight request,
        which reaches those Turns as a transport failure whose own recovery is
        another rebuild — so one 504 would cascade through every concurrent Turn.
        The replaced client is therefore dropped from use and closed later.
        """
        subject = OpenAICompatibleTransport(config())
        first = subject._http

        assert await subject.rebuild() is True
        assert subject._http is not first
        assert first.is_closed is False

        await subject.aclose()
        assert first.is_closed is True
        assert subject._http.is_closed is True

    async def test_a_second_rebuild_inside_the_cooldown_is_refused(self):
        """A pool built two seconds ago is already the fresh one."""
        subject = OpenAICompatibleTransport(config())
        try:
            assert await subject.rebuild() is True
            assert await subject.rebuild() is False
        finally:
            await subject.aclose()

    async def test_an_injected_client_is_never_rebuilt(self):
        """Its lifecycle belongs to whoever supplied it."""
        supplied = httpx.AsyncClient()
        subject = OpenAICompatibleTransport(config(), http_client=supplied)

        assert await subject.rebuild() is False
        assert supplied.is_closed is False

        await subject.aclose()
        assert supplied.is_closed is False
        await supplied.aclose()


# --- deadlines ------------------------------------------------------------


def test_a_deadline_nobody_can_express_is_clamped_where_it_is_configured():
    """cpython #83220: an overflowing ``time_t`` raises inside ``Lock.acquire``.

    Clamped at the configuration boundary rather than at each waiter, because a
    waiter that clamps is a waiter somebody has to remember to write.
    """
    assert clamp_timeout(10 ** 12) == MAX_TIMEOUT_SECONDS
    assert clamp_timeout(0) == MIN_TIMEOUT_SECONDS
    assert clamp_timeout(-5) == MIN_TIMEOUT_SECONDS
    assert clamp_timeout(float("nan")) == MIN_TIMEOUT_SECONDS
    assert clamp_timeout("not a number") == MIN_TIMEOUT_SECONDS  # type: ignore[arg-type]
    assert clamp_timeout(120.0) == 120.0


# --- the cache breakpoint -------------------------------------------------


def test_segments_must_describe_the_content_they_accompany():
    """One prompt, whether it is read as blocks or measured as a string.

    The ledger estimates from ``content`` and the route reads the blocks. Two
    sources of truth here would mean paying for one prompt and sending another.
    """
    stable = "stable prefix"
    tail = " and the five values"

    message = Message(
        role=Role.SYSTEM,
        content=stable + tail,
        segments=(ContentSegment(stable, cache_breakpoint=True), ContentSegment(tail)),
    )

    assert message.as_wire()["content"] == stable + tail
    blocks = message.as_wire(cache_control=True)["content"]
    assert [block["text"] for block in blocks] == [stable, tail]
    assert blocks[0]["cache_control"] == {"type": "ephemeral"}
    assert "cache_control" not in blocks[1]

    with pytest.raises(ValueError, match="concatenate"):
        Message(
            role=Role.SYSTEM,
            content="one prompt",
            segments=(ContentSegment("another prompt"),),
        )


def test_a_message_without_segments_keeps_the_shape_it_always_had():
    """Off by default, and off is byte-identical to before.

    ``cache_control`` is Anthropic's spelling; an OpenAI-compatible route is free
    to refuse the request carrying it, so nothing changes until an operator turns
    it on and the Capability Probe agrees.
    """
    message = Message(role=Role.USER, content="FPT?")

    assert message.as_wire() == message.as_wire(cache_control=True)
