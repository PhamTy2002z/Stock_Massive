"""A Turn that carries what the reader attached, and a Thread that redraws it.

Two halves, tested two ways, because they fail in different places.

The message layer is pure, so its tests are pure: given a snapshot, which
content parts come out. The rule under test there — an image travels only with
the newest Turn — is a property of the tuple and not of any clock, which is
exactly why it can be asserted without a database.

Everything else is a row and a ``WHERE``: the idempotency key comparing two
different pictures, ownership answering 404, and the binding that stops the
orphan sweep from deleting bytes a committed Turn points at. A fake store would
let all three pass. So those tests go through the real endpoints, on the harness
``test_agent_transport`` already owns — reusing it rather than restating it,
because a second copy of a service wiring is a second thing to keep true.

Requires DATABASE_URL to point at a migrated database.
"""

from __future__ import annotations

import base64
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from src.agent.attachments import (
    IMAGE_TOKENS_PER_CALL,
    MAX_IMAGES_PER_TURN,
    AttachmentStore,
    image_tokens_for,
)
from src.agent.messages import (
    MAX_ATTACHMENT_TEXT_BYTES,
    TRUNCATION_NOTE,
    Transcript,
    TranscriptTurn,
    TurnAttachment,
    build_messages,
)
from src.agent.router import (
    attachment_store as attachment_store_dependency,
    desk as desk_dependency,
    history_of,
)
from src.agent.turns import MAX_USER_INPUT_BYTES
from src.alpha.models import (
    AgentAttachment,
    AgentMessage,
    AgentThread,
    AgentToolCall,
    AgentTurn,
    LlmCallUsage,
)
from src.auth.models import User
from src.core.database import Base, engine, get_sync_db, sync_engine
from src.main import app

from .test_agent_attachments import png
from .test_agent_transport import Desk, open_thread, start_turn

pytestmark = pytest.mark.asyncio

API = "/api/v1"

#: One byte in UTF-8, and absent from every Vietnamese word in the harness's
#: own notes — so counting it counts file content only.
FILLER = "Z"


# --- the pure half: what reaches the model --------------------------------


def image(name: str = "bang-gia.png", *, tokens: int = 930) -> TurnAttachment:
    return TurnAttachment(
        id=uuid.uuid4(),
        filename=name,
        media_type="image/png",
        byte_size=4_096,
        estimated_tokens=tokens,
        data=base64.b64encode(b"not-really-a-png").decode("ascii"),
    )


def text_file(body: str, name: str = "danh-muc.csv") -> TurnAttachment:
    return TurnAttachment(
        id=uuid.uuid4(),
        filename=name,
        media_type="text/csv",
        byte_size=len(body.encode("utf-8")),
        text=body,
    )


def forget_payload(attachment: TurnAttachment) -> TurnAttachment:
    """The same attachment as a Thread reopened would carry it."""
    return TurnAttachment.from_payload(attachment.as_metadata())


class TestOnlyTheNewestTurnSendsPixels:
    """The most important test of this phase, and the one the plan lacked."""

    async def test_a_two_turn_thread_does_not_resend_the_first_turns_image(self):
        first = image("phien-1.png")
        transcript = Transcript(
            system_prompt="SYS",
            vision=True,
            turns=(
                TranscriptTurn(
                    user_text="ảnh này là gì?",
                    attachments=(forget_payload(first),),
                    assistant_text="một bảng giá",
                ),
                TranscriptTurn(user_text="còn cột thứ hai?"),
            ),
        )

        messages = build_messages(transcript).messages

        assert sum(len(message.images) for message in messages) == 0
        # The placeholder stays, so the model knows there was a picture it can
        # no longer see and can say so instead of answering as though none was
        # ever sent.
        assert "[ảnh: phien-1.png]" in (messages[1].content or "")

    async def test_the_newest_turn_does_send_its_own_image(self):
        transcript = Transcript(
            system_prompt="SYS",
            vision=True,
            turns=(
                TranscriptTurn(user_text="chào", assistant_text="chào bạn"),
                TranscriptTurn(user_text="đọc ảnh này", attachments=(image(),)),
            ),
        )

        messages = build_messages(transcript).messages

        assert sum(len(message.images) for message in messages) == 1
        assert messages[-1].images[0].placeholder == "[ảnh: bang-gia.png]"

    async def test_ten_turns_each_with_an_image_send_exactly_one(self):
        """The failure this rule exists to prevent, at the scale it appears."""
        turns = tuple(
            TranscriptTurn(
                user_text=f"câu {index}",
                attachments=(forget_payload(image(f"anh-{index}.png")),),
                assistant_text="rồi",
            )
            for index in range(9)
        )
        transcript = Transcript(
            system_prompt="SYS",
            vision=True,
            turns=(*turns, TranscriptTurn(user_text="câu cuối", attachments=(image(),))),
        )

        messages = build_messages(transcript).messages

        assert sum(len(message.images) for message in messages) == 1


class TestPurityIsUntouched:
    async def test_the_same_transcript_twice_gives_the_same_list(self):
        transcript = Transcript(
            system_prompt="SYS",
            vision=True,
            turns=(
                TranscriptTurn(user_text="một", attachments=(image(),)),
                TranscriptTurn(
                    user_text="hai", attachments=(image("b.png"), text_file("a,b\n1,2"))
                ),
            ),
        )

        assert build_messages(transcript).messages == build_messages(transcript).messages

    async def test_newest_is_read_off_the_tuple_and_not_off_a_counter(self):
        """Reorder the snapshot and the images move with it, nothing else."""
        one, two = image("một.png"), image("hai.png")
        forward = Transcript(
            system_prompt="SYS",
            vision=True,
            turns=(
                TranscriptTurn(user_text="a", attachments=(one,), assistant_text="x"),
                TranscriptTurn(user_text="b", attachments=(two,)),
            ),
        )
        backward = Transcript(
            system_prompt="SYS",
            vision=True,
            turns=(
                TranscriptTurn(user_text="b", attachments=(two,), assistant_text="x"),
                TranscriptTurn(user_text="a", attachments=(one,)),
            ),
        )

        assert build_messages(forward).messages[-1].images[0].placeholder == (
            "[ảnh: hai.png]"
        )
        assert build_messages(backward).messages[-1].images[0].placeholder == (
            "[ảnh: một.png]"
        )


class TestARouteThatCannotSeeImages:
    async def test_no_content_part_reaches_a_route_without_vision(self):
        transcript = Transcript(
            system_prompt="SYS",
            vision=False,
            turns=(TranscriptTurn(user_text="đọc ảnh", attachments=(image(),)),),
        )

        messages = build_messages(transcript).messages

        assert sum(len(message.images) for message in messages) == 0

    async def test_the_attachment_is_still_in_the_transcript(self):
        """Not sent is not forgotten: the reader is told, not lied to."""
        transcript = Transcript(
            system_prompt="SYS",
            vision=False,
            turns=(TranscriptTurn(user_text="đọc ảnh", attachments=(image(),)),),
        )

        assert "[ảnh: bang-gia.png]" in (build_messages(transcript).messages[-1].content or "")

    async def test_a_text_file_still_travels_without_vision(self):
        """Vision is about pixels. A CSV was never an image."""
        transcript = Transcript(
            system_prompt="SYS",
            vision=False,
            turns=(
                TranscriptTurn(user_text="tóm tắt", attachments=(text_file("ma,gia\nVCB,95000"),)),
            ),
        )

        assert "VCB,95000" in (build_messages(transcript).messages[-1].content or "")


class TestUploadedTextIsWrappedAndBounded:
    async def test_a_files_text_arrives_inside_the_attachment_wrapper(self):
        transcript = Transcript(
            system_prompt="SYS",
            turns=(TranscriptTurn(user_text="đọc", attachments=(text_file("ma,gia\nVCB,95000"),)),),
        )

        content = build_messages(transcript).messages[-1].content or ""

        assert '<user_attachment name="danh-muc.csv">' in content
        assert content.count("</user_attachment>") == 1

    async def test_the_inline_cap_is_the_same_number_as_the_typed_message_cap(self):
        """One policy, two names, pinned equal.

        ``messages`` cannot import the constant from ``turns`` — ``turns``
        imports ``loop`` which imports ``messages`` — so the value is written
        twice. This is the test that keeps two names from becoming two policies.
        """
        assert MAX_ATTACHMENT_TEXT_BYTES == MAX_USER_INPUT_BYTES

    async def test_a_file_past_the_cap_is_cut_and_says_so(self):
        # A filler no part of TRUNCATION_NOTE contains, so counting it counts
        # file content and nothing the harness added. The first version of this
        # test used "y", which the note's own word "đây" carries.
        body = FILLER * (MAX_ATTACHMENT_TEXT_BYTES + 500)
        transcript = Transcript(
            system_prompt="SYS",
            turns=(TranscriptTurn(user_text="đọc", attachments=(text_file(body),)),),
        )

        content = build_messages(transcript).messages[-1].content or ""

        # Cut, and the cut is stated: a file trimmed silently is a file the model
        # reads as whole, and a conclusion from half of it would sound complete.
        assert TRUNCATION_NOTE in content
        assert content.count(FILLER) == MAX_ATTACHMENT_TEXT_BYTES

    async def test_the_cap_is_spent_across_a_turn_and_not_per_file(self):
        """Two files over half the cap each: together they get exactly the cap.

        Per-file would let n files carry n times the allowance, which is how a
        ceiling stops being one.
        """
        half = FILLER * (MAX_ATTACHMENT_TEXT_BYTES // 2 + 100)
        transcript = Transcript(
            system_prompt="SYS",
            turns=(
                TranscriptTurn(
                    user_text="đọc cả hai",
                    attachments=(text_file(half, "a.csv"), text_file(half, "b.csv")),
                ),
            ),
        )

        content = build_messages(transcript).messages[-1].content or ""

        assert content.count(FILLER) == MAX_ATTACHMENT_TEXT_BYTES
        assert TRUNCATION_NOTE in content


class TestTheEstimateSeesTheImages:
    async def test_a_message_with_an_image_costs_more_than_its_placeholder(self):
        """The whole reason phase 03 exists, asserted from this phase's shape."""
        bare = Transcript(
            system_prompt="SYS", vision=True, turns=(TranscriptTurn(user_text="q"),)
        )
        withimage = Transcript(
            system_prompt="SYS",
            vision=True,
            turns=(TranscriptTurn(user_text="q", attachments=(image(),)),),
        )

        cost = build_messages(withimage).estimated_tokens - build_messages(bare).estimated_tokens

        assert cost >= 930


# --- the row half: ownership, idempotency, and the binding ----------------


@pytest.fixture(scope="module", autouse=True)
def schema():
    Base.metadata.create_all(
        sync_engine,
        tables=[
            AgentThread.__table__,
            AgentMessage.__table__,
            AgentToolCall.__table__,
            AgentTurn.__table__,
            AgentAttachment.__table__,
            LlmCallUsage.__table__,
        ],
        checkfirst=True,
    )


def _purge(email: str) -> None:
    with get_sync_db() as session:
        user = session.execute(
            select(User).where(User.email == email)
        ).scalar_one_or_none()
        if user is None:
            return
        session.execute(delete(AgentAttachment).where(AgentAttachment.user_id == user.id))
        session.execute(delete(User).where(User.id == user.id))
        session.commit()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    await engine.dispose()


@pytest.fixture
def account():
    email = f"turn-attach-{uuid.uuid4().hex[:12]}@example.com"
    yield {"email": email, "password": "sup3r-secret-pw"}
    _purge(email)


@pytest.fixture
def other_account():
    email = f"turn-stranger-{uuid.uuid4().hex[:12]}@example.com"
    yield {"email": email, "password": "sup3r-secret-pw"}
    _purge(email)


async def register(client: AsyncClient, account: dict) -> dict:
    response = await client.post(f"{API}/auth/register", json=account)
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest_asyncio.fixture
async def auth(client, account):
    return await register(client, account)


@pytest_asyncio.fixture
async def desk():
    built = Desk()
    store = AttachmentStore()
    app.dependency_overrides[desk_dependency] = lambda: built.service
    app.dependency_overrides[attachment_store_dependency] = lambda: store
    yield built
    app.dependency_overrides.pop(desk_dependency, None)
    app.dependency_overrides.pop(attachment_store_dependency, None)
    built.control.finish()
    await built.service.turns.shutdown(timeout=5)


async def upload(client, auth, *, name="bang-gia.png", data=None, media_type="image/png"):
    response = await client.post(
        f"{API}/attachments",
        files={"file": (name, data if data is not None else png(64, 48), media_type)},
        headers=auth,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _stored_payload(turn_id: str) -> dict:
    with get_sync_db() as session:
        turn = session.get(AgentTurn, uuid.UUID(turn_id))
        message = session.get(AgentMessage, turn.request_message_id)
        return dict(message.content or {})


class TestIdempotencyCoversTheAttachments:
    async def test_the_same_id_with_a_different_image_is_a_conflict(
        self, client, auth, desk
    ):
        thread = await open_thread(client, auth)
        first = await upload(client, auth, name="một.png")
        second = await upload(client, auth, name="hai.png")
        turn_id = str(uuid.uuid4())

        opened = await start_turn(
            client, auth, thread, turn_id=turn_id, attachments=[first]
        )
        assert opened.status_code == 201, opened.text
        again = await start_turn(
            client, auth, thread, turn_id=turn_id, attachments=[second]
        )

        assert again.status_code == 409
        assert again.json()["detail"]["reason"] == "turn_id_reused"
        desk.control.finish()

    async def test_the_same_id_with_the_same_image_returns_the_turn_that_exists(
        self, client, auth, desk
    ):
        thread = await open_thread(client, auth)
        attachment = await upload(client, auth)
        turn_id = str(uuid.uuid4())

        first = await start_turn(
            client, auth, thread, turn_id=turn_id, attachments=[attachment]
        )
        second = await start_turn(
            client, auth, thread, turn_id=turn_id, attachments=[attachment]
        )

        assert first.status_code == 201
        assert second.status_code == 200
        assert second.json()["created"] is False
        desk.control.finish()

    async def test_a_turn_with_no_attachment_stores_exactly_what_it_stored_before(
        self, client, auth, desk
    ):
        """The key must not change shape for every Turn asked before this existed."""
        thread = await open_thread(client, auth)
        opened = await start_turn(client, auth, thread, text="VCB thế nào?")
        assert opened.status_code == 201, opened.text

        assert _stored_payload(opened.json()["id"]) == {"text": "VCB thế nào?"}
        desk.control.finish()

    async def test_a_turn_with_an_attachment_stores_metadata_and_never_bytes(
        self, client, auth, desk
    ):
        thread = await open_thread(client, auth)
        attachment = await upload(client, auth)
        opened = await start_turn(client, auth, thread, attachments=[attachment])
        assert opened.status_code == 201, opened.text

        stored = _stored_payload(opened.json()["id"])["attachments"]

        assert [entry["id"] for entry in stored] == [attachment]
        assert stored[0]["filename"] == "bang-gia.png"
        assert stored[0]["media_type"] == "image/png"
        assert stored[0]["byte_size"] > 0
        assert "data" not in stored[0] and "content" not in stored[0]
        desk.control.finish()


class TestOwnership:
    async def test_another_users_attachment_is_404_and_not_403(
        self, client, auth, desk, other_account
    ):
        """One answer for absent and for somebody else's, deliberately.

        Two answers would make this endpoint a way to learn which ids exist.
        """
        stranger = await register(client, other_account)
        theirs = await upload(client, stranger, name="cua-nguoi-khac.png")
        thread = await open_thread(client, auth)

        response = await start_turn(client, auth, thread, attachments=[theirs])

        assert response.status_code == 404
        desk.control.finish()

    async def test_an_attachment_that_never_existed_is_404(self, client, auth, desk):
        thread = await open_thread(client, auth)

        response = await start_turn(
            client, auth, thread, attachments=[str(uuid.uuid4())]
        )

        assert response.status_code == 404
        desk.control.finish()

    async def test_a_refused_attachment_leaves_no_turn_behind(self, client, auth, desk):
        thread = await open_thread(client, auth)
        turn_id = str(uuid.uuid4())

        await start_turn(
            client, auth, thread, turn_id=turn_id, attachments=[str(uuid.uuid4())]
        )

        with get_sync_db() as session:
            assert session.get(AgentTurn, uuid.UUID(turn_id)) is None
        desk.control.finish()


class TestTheBindingThatSurvivesTheSweep:
    async def test_creating_the_turn_binds_the_rows_to_it(self, client, auth, desk):
        """Unbound rows are swept in 24 hours, and a Turn cannot lose its bytes."""
        thread = await open_thread(client, auth)
        attachment = await upload(client, auth)

        opened = await start_turn(client, auth, thread, attachments=[attachment])
        assert opened.status_code == 201, opened.text

        with get_sync_db() as session:
            row = session.get(AgentAttachment, uuid.UUID(attachment))
            assert row.attached_turn_id == uuid.UUID(opened.json()["id"])
        desk.control.finish()

    async def test_an_upload_that_never_became_a_turn_stays_unbound(
        self, client, auth, desk
    ):
        attachment = await upload(client, auth)

        with get_sync_db() as session:
            assert session.get(AgentAttachment, uuid.UUID(attachment)).attached_turn_id is None

    async def test_the_sweep_spares_a_bound_row(self, client, auth, desk):
        thread = await open_thread(client, auth)
        attachment = await upload(client, auth)
        opened = await start_turn(client, auth, thread, attachments=[attachment])
        assert opened.status_code == 201, opened.text

        await AttachmentStore().sweep_orphans()

        with get_sync_db() as session:
            assert session.get(AgentAttachment, uuid.UUID(attachment)) is not None
        desk.control.finish()


class TestTheImageBudgetRefusesBeforeTheTurnExists:
    async def test_three_full_desktop_captures_are_refused_with_a_readable_reason(
        self, client, auth, desk
    ):
        """The count cap is not the binding one, and this is why.

        ``MAX_IMAGES_PER_TURN`` divides the per-call image budget by what a
        1024x768 screenshot costs. Three 1800x1800 captures are inside that
        count and past that budget.
        """
        thread = await open_thread(client, auth)
        ids = [
            await upload(client, auth, name=f"to-{index}.png", data=png(1_800, 1_800))
            for index in range(3)
        ]
        assert len(ids) < MAX_IMAGES_PER_TURN
        assert 3 * image_tokens_for(1_800, 1_800) > IMAGE_TOKENS_PER_CALL

        response = await start_turn(client, auth, thread, attachments=ids)

        assert response.status_code == 400
        assert response.json()["detail"]["reason"] == "turn_image_budget"
        assert "bỏ một ảnh" in response.json()["detail"]["message"]
        desk.control.finish()

    async def test_more_ids_than_the_count_cap_is_a_422(self, client, auth, desk):
        thread = await open_thread(client, auth)

        response = await start_turn(
            client,
            auth,
            thread,
            attachments=[str(uuid.uuid4()) for _ in range(MAX_IMAGES_PER_TURN + 1)],
        )

        assert response.status_code == 422
        desk.control.finish()


class TestReopeningAThread:
    async def test_the_message_carries_the_metadata_the_surface_draws_from(
        self, client, auth, desk
    ):
        thread = await open_thread(client, auth)
        attachment = await upload(client, auth)
        opened = await start_turn(client, auth, thread, attachments=[attachment])
        assert opened.status_code == 201, opened.text
        desk.control.finish()

        response = await client.get(f"{API}/threads/{thread}", headers=auth)

        assert response.status_code == 200, response.text
        user_message = next(
            message for message in response.json()["messages"] if message["role"] == "user"
        )
        stored = user_message["content"]["attachments"]
        assert stored[0]["id"] == attachment
        assert stored[0]["filename"] == "bang-gia.png"
        # Bytes are a second request, so a thread open stays one small response.
        assert "data" not in stored[0]

    async def test_history_rebuilds_metadata_and_no_payload(self):
        """``history_of`` is where resending every image would have happened."""

        class Record:
            role = "user"
            content = {
                "text": "ảnh này là gì?",
                "attachments": [
                    {
                        "id": str(uuid.uuid4()),
                        "filename": "cũ.png",
                        "media_type": "image/png",
                        "byte_size": 1_024,
                        "estimated_tokens": 930,
                    }
                ],
            }

        turns = history_of([Record()])

        assert len(turns[0].attachments) == 1
        assert turns[0].attachments[0].filename == "cũ.png"
        assert turns[0].attachments[0].data is None
        assert turns[0].attachments[0].text is None

    async def test_history_leaves_an_ordinary_turn_exactly_as_it_was(self):
        class Record:
            role = "user"
            content = {"text": "VCB thế nào?"}

        assert history_of([Record()]) == (TranscriptTurn(user_text="VCB thế nào?"),)
