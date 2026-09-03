"""The three Phase 6 evidence lifetimes and their ownership boundary."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from src.agent.evidence.source_policy import POLICY_VERSION
from src.agent.persistence import TURN_COMPLETE, AgentPersistence
from src.alpha.models import (
    AgentClaimLedger,
    AgentEvidenceCache,
    AgentEvidenceTrajectory,
    AgentThread,
)
from src.auth.models import User
from src.core.database import Base, get_sync_db, sync_engine, sync_session_factory


@pytest.fixture(scope="module", autouse=True)
def schema():
    Base.metadata.create_all(sync_engine, checkfirst=True)


@pytest.fixture
def owners():
    with get_sync_db() as session:
        first = User(email=f"evidence-{uuid.uuid4().hex}@example.com", hashed_password="x")
        second = User(email=f"evidence-{uuid.uuid4().hex}@example.com", hashed_password="x")
        session.add_all((first, second))
        session.flush()
        ids = (first.id, second.id)
    yield ids
    with get_sync_db() as session:
        session.execute(delete(AgentThread).where(AgentThread.user_id.in_(ids)))
        session.execute(delete(User).where(User.id.in_(ids)))


def store() -> AgentPersistence:
    return AgentPersistence(session_factory=sync_session_factory)


def public_payload(*, now: datetime, url: str | None = None, **overrides):
    content = "Công bố chính thức: lợi nhuận đạt 1.245 tỷ đồng."
    payload = {
        "canonical_url": url or f"https://ssc.gov.vn/{uuid.uuid4().hex}",
        "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
        "as_of_bucket": "2026-08-20",
        "policy_version": POLICY_VERSION,
        "cache_kind": "primary_filing",
        "source_class": "regulator",
        "title": "Công bố chính thức",
        "publisher": "SSC",
        "content": content,
        "publication": {
            "publishedAt": "2026-08-20T09:00:00+07:00",
            "publicationMethod": "html_meta",
            "publicationConfidence": "high",
            "publicationPrecision": "instant",
        },
        "retrieved_at": now,
        "expires_at": now + timedelta(days=730),
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_public_cache_is_content_addressed_and_shared_without_an_owner(owners):
    now = datetime(2026, 8, 20, 3, tzinfo=timezone.utc)
    payload = public_payload(now=now)
    persistence = store()

    first = await persistence.cache_public_evidence(payload)
    repeated = await persistence.cache_public_evidence(payload)
    found = await persistence.read_cached_evidence(
        payload["canonical_url"], "2026-08-20", now=now
    )

    assert repeated.id == first.id
    assert found is not None and found.content == payload["content"]
    assert "user_id" not in AgentEvidenceCache.__table__.columns
    assert "turn_id" not in AgentEvidenceCache.__table__.columns


@pytest.mark.asyncio
async def test_public_cache_refuses_snippets_and_a_false_content_identity():
    now = datetime(2026, 8, 20, 3, tzinfo=timezone.utc)
    persistence = store()

    with pytest.raises(ValueError, match="discovery-only"):
        await persistence.cache_public_evidence(
            public_payload(now=now, cache_kind="search_snippet")
        )
    with pytest.raises(ValueError, match="exact public content"):
        await persistence.cache_public_evidence(
            public_payload(now=now, content_sha256="0" * 64)
        )


@pytest.mark.asyncio
async def test_expired_public_cache_is_not_readable():
    retrieved = datetime(2026, 8, 20, 3, tzinfo=timezone.utc)
    payload = public_payload(now=retrieved, expires_at=retrieved + timedelta(hours=1))
    persistence = store()
    await persistence.cache_public_evidence(payload)

    assert await persistence.read_cached_evidence(
        payload["canonical_url"], "2026-08-20", now=retrieved + timedelta(hours=2)
    ) is None


@pytest.mark.asyncio
async def test_trajectory_is_private_bounded_and_expires_in_thirty_days(owners):
    owner, stranger = owners
    persistence = store()
    thread = await persistence.create_thread(owner)
    turn = await persistence.create_turn(
        user_id=owner,
        thread_id=thread.id,
        turn_id=uuid.uuid4(),
        user_text="Nghiên cứu VCB",
    )
    now = datetime(2026, 8, 20, 3, tzinfo=timezone.utc)

    written = await persistence.write_evidence_trajectory(
        owner, turn.turn.id, stage="research", payload={"draft": ["claim"]}, now=now
    )

    assert written is not None
    assert written.expires_at == now + timedelta(days=30)
    assert [row.stage for row in await persistence.evidence_trajectories(owner, turn.turn.id)] == [
        "research"
    ]
    assert await persistence.evidence_trajectories(stranger, turn.turn.id) == ()
    assert await persistence.write_evidence_trajectory(
        stranger, turn.turn.id, stage="research", payload={}, now=now
    ) is None


@pytest.mark.asyncio
async def test_claim_ledger_commits_with_the_assistant_message_and_is_owner_scoped(owners):
    owner, stranger = owners
    persistence = store()
    thread = await persistence.create_thread(owner)
    turn = await persistence.create_turn(
        user_id=owner,
        thread_id=thread.id,
        turn_id=uuid.uuid4(),
        user_text="Nghiên cứu HPG",
    )
    ledger = {
        "version": "1",
        "policyVersion": POLICY_VERSION,
        "asOf": "2026-08-20T15:00:00+07:00",
        "evidence": [],
        "claims": [],
        "gaps": ["Chưa đủ nguồn"],
        "assumptions": [],
        "verifierOutcome": "insufficient_evidence",
    }

    finished = await persistence.finish_turn(
        turn.turn.id,
        status=TURN_COMPLETE,
        terminal_reason=None,
        message={"text": "Chưa đủ bằng chứng."},
        claim_ledger=ledger,
    )

    assert finished.response_message_id is not None
    stored = await persistence.claim_ledger_for_message(owner, finished.response_message_id)
    assert stored is not None and stored.payload == ledger
    assert stored.turn_id == turn.turn.id
    assert await persistence.claim_ledger_for_message(
        stranger, finished.response_message_id
    ) is None


@pytest.mark.asyncio
async def test_ledger_requires_a_terminal_message_before_any_write(owners):
    owner, _stranger = owners
    persistence = store()
    thread = await persistence.create_thread(owner)
    turn = await persistence.create_turn(
        user_id=owner,
        thread_id=thread.id,
        turn_id=uuid.uuid4(),
        user_text="Nghiên cứu",
    )

    with pytest.raises(ValueError, match="anchored"):
        await persistence.finish_turn(
            turn.turn.id,
            status=TURN_COMPLETE,
            terminal_reason=None,
            claim_ledger={"version": "1"},
        )
    with get_sync_db() as session:
        assert session.execute(
            select(AgentClaimLedger).where(AgentClaimLedger.turn_id == turn.turn.id)
        ).scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_cleanup_deletes_only_expired_cache_and_trajectory_not_ledgers(owners):
    owner, _stranger = owners
    persistence = store()
    thread = await persistence.create_thread(owner)
    turn = await persistence.create_turn(
        user_id=owner,
        thread_id=thread.id,
        turn_id=uuid.uuid4(),
        user_text="Nghiên cứu",
    )
    now = datetime(2026, 8, 20, 3, tzinfo=timezone.utc)
    trajectory = await persistence.write_evidence_trajectory(
        owner,
        turn.turn.id,
        stage="verification",
        payload={"candidate": {}},
        now=now - timedelta(days=31),
    )
    cache = await persistence.cache_public_evidence(
        public_payload(
            now=now - timedelta(days=2),
            expires_at=now - timedelta(days=1),
        )
    )
    finished = await persistence.finish_turn(
        turn.turn.id,
        status=TURN_COMPLETE,
        terminal_reason=None,
        message={"text": "Thiếu bằng chứng."},
        claim_ledger={"version": "1", "policyVersion": POLICY_VERSION},
    )

    deleted = await persistence.cleanup_expired_evidence(now=now)

    assert deleted["cache"] >= 1 and deleted["trajectory"] >= 1
    with get_sync_db() as session:
        assert session.get(AgentEvidenceCache, cache.id) is None
        assert session.get(AgentEvidenceTrajectory, trajectory.id) is None
    assert await persistence.claim_ledger_for_message(owner, finished.response_message_id) is not None


def test_every_pass_the_loop_can_record_is_a_stage_the_store_accepts():
    """The two vocabularies must not drift, and drifting is silent.

    A failed trajectory write is deliberately swallowed — a private trace is not
    the answer, so the Turn goes on — which means a stage the store rejects
    disappears from the trail with nothing but a log line. ``planning`` did
    exactly that: its four queries were missing from every deep Turn's audit
    trail until this test existed.
    """
    from src.agent.evidence.pipeline import PipelineStage
    from src.agent.persistence import EVIDENCE_TRAJECTORY_STAGES

    recordable = {
        stage.value for stage in PipelineStage if stage is not PipelineStage.COMPLETE
    }

    assert recordable <= EVIDENCE_TRAJECTORY_STAGES, (
        "the loop can record a stage the store refuses: "
        f"{sorted(recordable - EVIDENCE_TRAJECTORY_STAGES)}"
    )
