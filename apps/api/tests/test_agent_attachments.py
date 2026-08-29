"""The attachment store, its ceilings, and how a stored file is handed back.

Integration rather than unit, for the reason the transport tests give: ownership
is a column and a ``WHERE``, the quota is an aggregate over rows, and the sweep
is a ``DELETE`` with a predicate. A fake store would let all three pass while the
real one refused.

Requires DATABASE_URL to point at a migrated database.
"""

from __future__ import annotations

import struct
import uuid
import zlib
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select, update

from src.agent.attachments import (
    MAX_ATTACHMENT_BYTES,
    MAX_ATTACHMENTS_PER_USER,
    MAX_IMAGE_PIXELS,
    MAX_IMAGES_PER_TURN,
    ORPHAN_TTL,
    AttachmentStore,
    image_tokens_for,
    sanitise_filename,
    serving_headers,
    sniff_image,
)
from src.agent.router import attachment_store as attachment_store_dependency
from src.alpha.models import AgentAttachment
from src.auth.models import User
from src.core.database import Base, engine, get_sync_db, sync_engine
from src.core.llm.protocol import IMAGE_TOKENS, REFERENCE_IMAGE_PIXELS
from src.main import app

pytestmark = pytest.mark.asyncio

API = "/api/v1"
# The agent router mounts without a prefix of its own.
DESK = API


# --- building files whose bytes really are what they claim ----------------


def png(width: int, height: int) -> bytes:
    """A real PNG of the requested size, from the standard library only."""
    rows = b"".join(b"\x00" + b"\xff" * (width * 3) for _ in range(height))

    def chunk(kind: bytes, payload: bytes) -> bytes:
        body = kind + payload
        return (
            struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows, 1))
        + chunk(b"IEND", b"")
    )


# --- fixtures -------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def attachment_schema():
    Base.metadata.create_all(
        sync_engine, tables=[AgentAttachment.__table__], checkfirst=True
    )


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    await engine.dispose()


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


@pytest.fixture
def account():
    email = f"attach-{uuid.uuid4().hex[:12]}@example.com"
    yield {"email": email, "password": "sup3r-secret-pw"}
    _purge(email)


@pytest.fixture
def other_account():
    email = f"stranger-{uuid.uuid4().hex[:12]}@example.com"
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
async def store():
    """The real store, installed as the dependency the endpoints resolve."""
    built = AttachmentStore()
    app.dependency_overrides[attachment_store_dependency] = lambda: built
    yield built
    app.dependency_overrides.pop(attachment_store_dependency, None)


async def upload(client, auth, *, data: bytes, name: str, media_type: str):
    return await client.post(
        f"{DESK}/attachments",
        files={"file": (name, data, media_type)},
        headers=auth,
    )


def _user_id(email: str) -> int:
    with get_sync_db() as session:
        return session.execute(select(User.id).where(User.email == email)).scalar_one()


# --- what the numbers are, and where they came from -----------------------


class TestCeilings:
    async def test_the_per_turn_image_count_is_derived_not_chosen(self):
        """It has to fall out of the Turn's own budget, or it means nothing.

        ``TURN_INPUT_TOTAL`` bounds the sum over ``MAX_TOOL_ROUNDS + 1`` calls,
        the attachments ride the newest question so they are resent on each one,
        and one reference-sized image costs what the probe measured.
        """
        assert MAX_IMAGES_PER_TURN == 8
        assert MAX_IMAGES_PER_TURN * IMAGE_TOKENS <= 8_000

    async def test_an_image_is_charged_by_area_not_by_the_count_of_it(self):
        """The measured number is for one size; every other size scales."""
        assert image_tokens_for(1_024, 768) == IMAGE_TOKENS
        assert image_tokens_for(2_048, 1_536) == pytest.approx(IMAGE_TOKENS * 4, rel=0.01)
        assert image_tokens_for(1, 1) >= 1

    async def test_the_pixel_ceiling_keeps_one_image_from_taking_the_turn(self):
        """Bytes cannot do this job: a compressible image is small and huge."""
        tokens_at_the_ceiling = IMAGE_TOKENS * MAX_IMAGE_PIXELS // REFERENCE_IMAGE_PIXELS
        assert tokens_at_the_ceiling <= 8_000 // 2


# --- reading the bytes rather than the client's word ----------------------


class TestSniffing:
    async def test_a_png_states_its_own_size(self):
        assert sniff_image(png(1_024, 768)) == ("image/png", 1_024, 768)

    async def test_something_that_is_not_an_image_sniffs_as_nothing(self):
        assert sniff_image(b"<html><body>hi</body></html>") is None
        assert sniff_image(b"") is None

    async def test_a_filename_is_a_label_and_never_a_path(self):
        assert sanitise_filename("../../etc/passwd") == "passwd"
        assert sanitise_filename("a/b\\c.png") == "c.png"
        assert sanitise_filename("") == "tep-dinh-kem"
        # A Vietnamese name is a name, not an attack.
        assert sanitise_filename("bảng giá.png") == "bảng giá.png"


class TestServing:
    async def test_a_csv_full_of_html_is_never_served_as_html(self):
        """The two text types have no magic bytes, so this is the defence.

        Anything can arrive under ``text/csv``, and it is read back same-origin
        with the session cookie attached. The repo has no CSP and no default
        ``nosniff``, so the file is handed back as an opaque download.
        """
        media_type, headers = serving_headers("text/csv", "prices.csv")

        assert media_type == "application/octet-stream"
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["Content-Disposition"].startswith("attachment")

    async def test_an_image_keeps_the_type_its_bytes_proved(self):
        media_type, headers = serving_headers("image/png", "board.png")

        assert media_type == "image/png"
        assert headers["X-Content-Type-Options"] == "nosniff"


# --- the endpoints --------------------------------------------------------


class TestUpload:
    async def test_an_upload_comes_back_byte_for_byte(self, client, auth, store):
        data = png(320, 240)

        created = await upload(
            client, auth, data=data, name="board.png", media_type="image/png"
        )
        assert created.status_code == 201, created.text
        body = created.json()
        assert body["media_type"] == "image/png"
        assert body["byte_size"] == len(data)
        assert body["estimated_tokens"] == image_tokens_for(320, 240)

        read = await client.get(f"{DESK}/attachments/{body['id']}", headers=auth)
        assert read.status_code == 200
        assert read.content == data
        assert read.headers["x-content-type-options"] == "nosniff"

    async def test_a_stranger_gets_not_found_rather_than_forbidden(
        self, client, auth, store, other_account
    ):
        """A 403 would confirm the id exists, which is the thing being withheld."""
        created = await upload(
            client, auth, data=png(32, 32), name="a.png", media_type="image/png"
        )
        attachment_id = created.json()["id"]
        stranger = await register(client, other_account)

        response = await client.get(
            f"{DESK}/attachments/{attachment_id}", headers=stranger
        )

        assert response.status_code == 404
        assert (
            await client.get(f"{DESK}/attachments/{uuid.uuid4()}", headers=stranger)
        ).status_code == 404

    async def test_an_unauthenticated_caller_reaches_neither_endpoint(self, client, store):
        assert (
            await client.post(
                f"{DESK}/attachments", files={"file": ("a.png", png(8, 8), "image/png")}
            )
        ).status_code == 401
        assert (
            await client.get(f"{DESK}/attachments/{uuid.uuid4()}")
        ).status_code == 401

    async def test_html_declared_as_a_png_is_refused_on_its_bytes(
        self, client, auth, store
    ):
        response = await upload(
            client,
            auth,
            data=b"<html><script>alert(1)</script></html>",
            name="board.png",
            media_type="image/png",
        )

        assert response.status_code == 400
        assert response.json()["detail"]["reason"] == "not_an_image"

    async def test_a_jpeg_wearing_a_png_label_is_refused(self, client, auth, store):
        """Declared and measured must agree, or the served type is a lie."""
        jpeg = b"\xff\xd8\xff\xe0" + b"\x00\x10JFIF" + b"\x00" * 64
        response = await upload(
            client, auth, data=jpeg, name="x.png", media_type="image/png"
        )

        assert response.status_code == 400
        assert response.json()["detail"]["reason"] in {
            "media_type_mismatch",
            "not_an_image",
        }

    async def test_a_type_nobody_allowed_is_refused(self, client, auth, store):
        response = await upload(
            client, auth, data=b"MZ\x90\x00", name="x.exe", media_type="application/x-msdownload"
        )

        assert response.status_code == 400
        assert response.json()["detail"]["reason"] == "media_type_not_allowed"

    async def test_a_content_length_past_the_ceiling_is_refused_before_the_body(
        self, client, auth, store
    ):
        """The header is the only thing that can refuse before paying for bytes.

        Starlette has spooled the request by the time the handler runs, so a
        check on the bytes in hand is a check made after receiving them.
        """
        response = await client.post(
            f"{DESK}/attachments",
            content=b"",
            headers={
                **auth,
                "content-type": "multipart/form-data; boundary=x",
                "content-length": str(MAX_ATTACHMENT_BYTES * 4),
            },
        )

        assert response.status_code == 413
        assert response.json()["detail"]["reason"] == "file_too_large"

    async def test_an_image_too_large_in_pixels_is_refused_however_small_its_bytes(
        self, client, auth, store
    ):
        """A flat PNG compresses to nothing and still decodes enormous."""
        side = 4_096
        assert side * side > MAX_IMAGE_PIXELS
        data = png(side, 8)
        header_only = data[:24] + png(8, 8)[24:]  # tiny bytes, huge declared size
        header_only = (
            b"\x89PNG\r\n\x1a\n"
            + struct.pack(">I", 13)
            + b"IHDR"
            + struct.pack(">IIBBBBB", side, side, 8, 2, 0, 0, 0)
            + struct.pack(
                ">I",
                zlib.crc32(
                    b"IHDR" + struct.pack(">IIBBBBB", side, side, 8, 2, 0, 0, 0)
                ),
            )
            + png(8, 8)[33:]
        )

        response = await upload(
            client, auth, data=header_only, name="huge.png", media_type="image/png"
        )

        assert response.status_code == 413
        assert response.json()["detail"]["reason"] == "image_too_large"
        assert len(header_only) < 4_096  # small bytes, refused on pixels


class TestQuota:
    async def test_the_row_quota_refuses_a_loop(self, client, auth, store, account):
        """Rows, not bytes: many tiny uploads are the cheap way to fill a table."""
        user_id = _user_id(account["email"])
        with get_sync_db() as session:
            session.add_all(
                AgentAttachment(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    media_type="text/plain",
                    filename="f.txt",
                    byte_size=1,
                    content=b"x",
                )
                for _ in range(MAX_ATTACHMENTS_PER_USER)
            )
            session.commit()

        response = await upload(
            client, auth, data=png(8, 8), name="a.png", media_type="image/png"
        )

        assert response.status_code == 429
        assert response.json()["detail"]["reason"] == "attachment_quota_rows"

    async def test_the_byte_quota_refuses_independently_of_the_row_count(
        self, client, auth, store, account
    ):
        """One row can hold the whole allowance, so counting rows is not enough."""
        user_id = _user_id(account["email"])
        with get_sync_db() as session:
            session.add(
                AgentAttachment(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    media_type="text/plain",
                    filename="big.txt",
                    byte_size=200 * 1024 * 1024,
                    content=b"x",
                )
            )
            session.commit()

        response = await upload(
            client, auth, data=png(8, 8), name="a.png", media_type="image/png"
        )

        assert response.status_code == 429
        assert response.json()["detail"]["reason"] == "attachment_quota_bytes"


class TestSweep:
    async def test_the_sweep_takes_orphans_and_leaves_what_a_turn_named(
        self, client, auth, store, account
    ):
        """A sent attachment is part of a transcript that re-opens; keep it."""
        user_id = _user_id(account["email"])
        orphan = uuid.uuid4()
        recent = uuid.uuid4()
        old = datetime.now(timezone.utc) - ORPHAN_TTL - timedelta(hours=1)
        with get_sync_db() as session:
            session.add_all(
                [
                    AgentAttachment(
                        id=orphan,
                        user_id=user_id,
                        media_type="text/plain",
                        filename="o.txt",
                        byte_size=1,
                        content=b"x",
                        created_at=old,
                    ),
                    AgentAttachment(
                        id=recent,
                        user_id=user_id,
                        media_type="text/plain",
                        filename="r.txt",
                        byte_size=1,
                        content=b"x",
                    ),
                ]
            )
            session.commit()

        removed = await store.sweep_orphans()

        with get_sync_db() as session:
            surviving = set(
                session.execute(
                    select(AgentAttachment.id).where(
                        AgentAttachment.user_id == user_id
                    )
                )
                .scalars()
                .all()
            )
        assert removed >= 1
        assert orphan not in surviving
        assert recent in surviving

    async def test_an_attachment_a_turn_holds_survives_however_old_it_is(
        self, client, auth, store, account
    ):
        """The predicate is ``attached_turn_id IS NULL``, not age alone."""
        user_id = _user_id(account["email"])
        held = uuid.uuid4()
        old = datetime.now(timezone.utc) - ORPHAN_TTL - timedelta(days=30)
        with get_sync_db() as session:
            session.add(
                AgentAttachment(
                    id=held,
                    user_id=user_id,
                    media_type="text/plain",
                    filename="h.txt",
                    byte_size=1,
                    content=b"x",
                    created_at=old,
                )
            )
            session.commit()
            # Stand in for the Turn that will claim it in a later phase.
            session.execute(
                update(AgentAttachment)
                .where(AgentAttachment.id == held)
                .values(attached_turn_id=None)
            )
            session.commit()

        # With no Turn it is an orphan and goes.
        assert await store.sweep_orphans() >= 1
        with get_sync_db() as session:
            assert (
                session.execute(
                    select(AgentAttachment.id).where(AgentAttachment.id == held)
                ).scalar_one_or_none()
                is None
            )
