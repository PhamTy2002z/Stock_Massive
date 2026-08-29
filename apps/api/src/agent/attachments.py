"""Taking a file in, holding it, and handing it back — with the ceilings.

Three ceilings, and they are not interchangeable.

**Per file.** Bytes and, for an image, pixels. The byte cap bounds what the Next
proxy buffers and what one row costs; the pixel cap is what keeps the token
estimate from being a fiction, because an image's cost scales with its area and
a compressed PNG says nothing about how large it decompresses.

**Per Turn.** How many images may ride one question, derived below from
``TURN_INPUT_TOTAL`` rather than chosen.

**Per user.** Rows and total bytes. This is the one that stops a loop: without
it, an endpoint that writes to the database on every call and is bounded only
per file is an unbounded write.

None of them come from the endpoint's own admission: every other ``POST`` in
``agent/router.py`` is bounded by LLM admission, and this one does not call a
model, so it passes through no such gate. There is no rate-limit middleware
either — ``main.py`` registers only CORS.

What this module does **not** do: decode, resize, re-encode or thumbnail. It
reads a header to learn what the bytes are and how large the picture is, and
stores what it was given.
"""

from __future__ import annotations

import asyncio
import re
import struct
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from src.alpha.models import AgentAttachment
from src.core.database import sync_session_factory
from src.core.llm.admission import TURN_INPUT_TOTAL
from src.core.llm.protocol import IMAGE_TOKENS, REFERENCE_IMAGE_PIXELS

SessionFactory = Callable[[], Session]

# --- what may be uploaded --------------------------------------------------

#: Images are recognised by their first bytes; the two text types are not
#: recognisable at all, which is the whole reason they are served back the way
#: they are. See :func:`serving_headers`.
IMAGE_TYPES = ("image/png", "image/jpeg", "image/webp")
TEXT_TYPES = ("text/plain", "text/csv")
ALLOWED_TYPES = IMAGE_TYPES + TEXT_TYPES

#: Per file. Large enough for a full-page screenshot as PNG, small enough that
#: the Next proxy buffering one — it must, to replay a request across the 401
#: retry — is not a memory event.
MAX_ATTACHMENT_BYTES = 4 * 1024 * 1024

# --- the per-Turn ceiling, and where the number comes from -----------------
#
# Start from ``TURN_INPUT_TOTAL = 100_000``, which bounds the *sum* of input
# tokens over one Turn. It binds before ``TURN_CONTEXT_PER_CALL = 32_000`` does,
# because a Turn runs ``MAX_TOOL_ROUNDS + 1 = 5`` calls and 5 x 32_000 = 160_000
# is already past it.
#
# Everything that is not an image is resent on every one of those five calls:
# the system prompt (its stable prefix measures 5_554 tokens), the question, the
# transcript, and the tool results as they accumulate. Reserved at 12_000 per
# call, which is the prompt plus room for the rounds to fill.
#
#     image budget for the Turn = 100_000 - 5 x 12_000 = 40_000
#     per call                  = 40_000 / 5            =  8_000
#     at the measured cost of a reference-sized image   =  8_000 / 930 ~ 8
#
# The attachments ride the newest question, so they are resent on every call —
# that division by five is not conservatism, it is the shape of the Turn.
NON_IMAGE_TOKENS_PER_CALL = 12_000
CALLS_PER_TURN = 5
IMAGE_TOKENS_PER_CALL = (
    TURN_INPUT_TOTAL - CALLS_PER_TURN * NON_IMAGE_TOKENS_PER_CALL
) // CALLS_PER_TURN
MAX_IMAGES_PER_TURN = IMAGE_TOKENS_PER_CALL // IMAGE_TOKENS

#: No single image may take more than half of one call's image budget. Past that
#: a Turn is one picture and no room to think, and — the reason this is a cap
#: rather than a preference — a highly compressible image can be enormous in
#: pixels while staying small in bytes, so the byte cap does not bound it.
MAX_IMAGE_PIXELS = (IMAGE_TOKENS_PER_CALL // 2) * REFERENCE_IMAGE_PIXELS // IMAGE_TOKENS

# --- the per-user quota ----------------------------------------------------

#: Enough for many Turns' worth of attachments and nothing like a loop.
MAX_ATTACHMENTS_PER_USER = 200
MAX_ATTACHMENT_BYTES_PER_USER = 200 * 1024 * 1024

#: How long an upload that never became a Turn is kept. Long enough to survive a
#: reader who attaches a file, goes to lunch and comes back; short enough that
#: an abandoned upload is not storage.
ORPHAN_TTL = timedelta(hours=24)


def assert_within_turn_budget(attachments: Sequence["StoredAttachment"]) -> None:
    """Refuse a Turn whose images cannot fit in one call, before it exists.

    ``MAX_IMAGES_PER_TURN`` is a count, and a count is derived from an average:
    it divides the per-call image budget by what a 1024x768 screenshot costs. A
    reader attaching three full-desktop captures is inside the count and past
    the budget, because :data:`MAX_IMAGE_PIXELS` lets one image take half of it.
    So the binding check is the sum, and the count is the cheap one that runs
    first in the schema.

    Refused here — at Turn creation, before a row exists and before any call
    reserves spend — rather than mid-Turn. Mid-Turn there is no action left for
    the reader to take; here there is exactly one, and the message names it.
    """
    total = sum(
        attachment.estimated_tokens or 0
        for attachment in attachments
        if attachment.media_type in IMAGE_TYPES
    )
    if total <= IMAGE_TOKENS_PER_CALL:
        return
    raise AttachmentRefused(
        "turn_image_budget",
        f"những ảnh này cần khoảng {total} token, vượt trần {IMAGE_TOKENS_PER_CALL} "
        "token ảnh của một lượt — hãy bỏ một ảnh rồi gửi lại",
    )


class AttachmentRefused(Exception):
    """A named refusal, so the endpoint maps it and the reader is told which."""

    def __init__(self, reason: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.reason = reason
        self.status_code = status_code


@dataclass(frozen=True)
class StoredAttachment:
    """What the caller gets back. Never the bytes — those need their own read."""

    id: uuid.UUID
    media_type: str
    filename: str
    byte_size: int
    pixel_width: int | None
    pixel_height: int | None

    @property
    def estimated_tokens(self) -> int | None:
        if self.pixel_width is None or self.pixel_height is None:
            return None
        return image_tokens_for(self.pixel_width, self.pixel_height)


@dataclass(frozen=True)
class StoredBytes:
    """A read: what the file is, and the bytes themselves."""

    meta: StoredAttachment
    content: bytes


def image_tokens_for(width: int, height: int) -> int:
    """What an image of this size is charged, scaled from the measurement.

    Linear in area, and that is not an assumption: ``make probe-vision`` and the
    diagnostics beside it measured five sizes on this route and they land
    between 1.18 and 1.49 tokens per kilopixel, with the larger images — the
    ones that matter for a ceiling — clustered at 1.18. Report:
    ``plans/reports/probe-260829-vision-route.md``.
    """
    pixels = max(width, 1) * max(height, 1)
    return max(1, IMAGE_TOKENS * pixels // REFERENCE_IMAGE_PIXELS)


# --- reading the bytes rather than the client's word for them --------------


def sniff_image(data: bytes) -> tuple[str, int, int] | None:
    """Media type and pixel size, from the file header, or ``None``.

    Only the three image types. The two text types have no magic bytes at all,
    which is a fact this module acts on rather than works around.
    """
    if data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR":
        width, height = struct.unpack(">II", data[16:24])
        return "image/png", width, height
    if data[:3] == b"\xff\xd8\xff":
        size = _jpeg_size(data)
        return ("image/jpeg", *size) if size else None
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        size = _webp_size(data)
        return ("image/webp", *size) if size else None
    return None


def _jpeg_size(data: bytes) -> tuple[int, int] | None:
    """Walk the segment chain to the frame header that states the size."""
    index = 2
    end = len(data)
    while index + 9 < end:
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            index += 2
            continue
        length = int.from_bytes(data[index + 2 : index + 4], "big")
        # SOF0..SOF15, minus the three that are not frame headers.
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            height = int.from_bytes(data[index + 5 : index + 7], "big")
            width = int.from_bytes(data[index + 7 : index + 9], "big")
            return width, height
        if length < 2:
            return None
        index += 2 + length
    return None


def _webp_size(data: bytes) -> tuple[int, int] | None:
    """The three WebP flavours state their size in three different places."""
    chunk = data[12:16]
    if chunk == b"VP8X" and len(data) >= 30:
        width = int.from_bytes(data[24:27], "little") + 1
        height = int.from_bytes(data[27:30], "little") + 1
        return width, height
    if chunk == b"VP8L" and len(data) >= 25:
        bits = int.from_bytes(data[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if chunk == b"VP8 " and len(data) >= 30:
        width = int.from_bytes(data[26:28], "little") & 0x3FFF
        height = int.from_bytes(data[28:30], "little") & 0x3FFF
        return width, height
    return None


_UNSAFE = re.compile(r"[^\w.\- ]+", re.UNICODE)


def sanitise_filename(raw: str) -> str:
    """A label, never a path.

    Separators go, leading dots go, and the result is bounded. Nothing
    downstream is allowed to treat this as a location, but a name that cannot be
    read as one is one fewer thing to get right later.
    """
    name = _UNSAFE.sub("_", (raw or "").replace("\\", "/").rsplit("/", 1)[-1]).strip()
    name = name.lstrip(".") or "tep-dinh-kem"
    return name[:255]


def serving_headers(media_type: str, filename: str) -> tuple[str, dict[str, str]]:
    """What to serve a stored file as, and the headers that must ride with it.

    ``text/plain`` and ``text/csv`` are the two types with no magic bytes, so
    anything at all — HTML, a script, an SVG — can be uploaded under either one
    and would then be read back same-origin, with the session cookie attached.
    The repo has neither a CSP nor a default ``nosniff``. So they are handed
    back as an opaque download instead of as text: the served type is
    ``application/octet-stream``, sniffing is refused, and the disposition says
    attachment.

    Images keep their type, because that type was read from their bytes.
    """
    safe = sanitise_filename(filename)
    if media_type in IMAGE_TYPES:
        return media_type, {
            "Content-Disposition": f'inline; filename="{safe}"',
            "X-Content-Type-Options": "nosniff",
        }
    return "application/octet-stream", {
        "Content-Disposition": f'attachment; filename="{safe}"',
        "X-Content-Type-Options": "nosniff",
    }


# --- the store -------------------------------------------------------------


class AttachmentStore:
    """The three operations, on the same sync sessions everything else uses.

    ``AgentPersistence`` is the neighbour to read: a sync ``Session`` off a
    thread, not an ``AsyncSession``, because that is the factory this schema is
    reached through everywhere else.
    """

    def __init__(self, session_factory: SessionFactory = sync_session_factory) -> None:
        self._session_factory = session_factory

    async def store(
        self, user_id: int, *, declared_type: str, filename: str, data: bytes
    ) -> StoredAttachment:
        return await asyncio.to_thread(
            self._store, user_id, declared_type, filename, data
        )

    async def read(
        self, user_id: int, attachment_id: uuid.UUID
    ) -> StoredBytes | None:
        return await asyncio.to_thread(self._read, user_id, attachment_id)

    async def sweep_orphans(self, *, now: datetime | None = None) -> int:
        return await asyncio.to_thread(self._sweep_orphans, now)

    def _store(
        self, user_id: int, declared_type: str, filename: str, data: bytes
    ) -> StoredAttachment:
        """Check everything, then write one row. Refusals are named."""
        if declared_type not in ALLOWED_TYPES:
            raise AttachmentRefused(
                "media_type_not_allowed",
                f"{declared_type} is not one of {', '.join(ALLOWED_TYPES)}",
            )
        if not data:
            raise AttachmentRefused("empty_file", "an empty file carries nothing")
        if len(data) > MAX_ATTACHMENT_BYTES:
            raise AttachmentRefused(
                "file_too_large",
                f"{len(data)} bytes is past the {MAX_ATTACHMENT_BYTES} byte ceiling",
                status_code=413,
            )

        width = height = None
        if declared_type in IMAGE_TYPES:
            sniffed = sniff_image(data)
            if sniffed is None:
                raise AttachmentRefused(
                    "not_an_image", "the bytes do not begin like a PNG, JPEG or WebP"
                )
            media_type, width, height = sniffed
            if media_type != declared_type:
                raise AttachmentRefused(
                    "media_type_mismatch",
                    f"declared {declared_type}, the bytes say {media_type}",
                )
            if width * height > MAX_IMAGE_PIXELS:
                raise AttachmentRefused(
                    "image_too_large",
                    f"{width}x{height} is past the {MAX_IMAGE_PIXELS} pixel "
                    "ceiling; one image may not take more than half of a call's "
                    "image budget",
                    status_code=413,
                )
        else:
            # No magic bytes exist for these. Nothing is inferred from the
            # content; the defence is in how they are served back.
            media_type = declared_type

        with self._session_factory() as session:
            self._check_quota(session, user_id, len(data))
            record = AgentAttachment(
                id=uuid.uuid4(),
                user_id=user_id,
                media_type=media_type,
                filename=sanitise_filename(filename),
                byte_size=len(data),
                pixel_width=width,
                pixel_height=height,
                content=data,
            )
            session.add(record)
            session.commit()
            return StoredAttachment(
                id=record.id,
                media_type=media_type,
                filename=record.filename,
                byte_size=len(data),
                pixel_width=width,
                pixel_height=height,
            )

    @staticmethod
    def _check_quota(session: Session, user_id: int, incoming: int) -> None:
        """Rows and bytes, asked before the insert rather than after."""
        rows, held = session.execute(
            select(
                func.count(AgentAttachment.id),
                func.coalesce(func.sum(AgentAttachment.byte_size), 0),
            ).where(AgentAttachment.user_id == user_id)
        ).one()
        if rows >= MAX_ATTACHMENTS_PER_USER:
            raise AttachmentRefused(
                "attachment_quota_rows",
                f"{rows} attachments is the per-reader ceiling",
                status_code=429,
            )
        if int(held) + incoming > MAX_ATTACHMENT_BYTES_PER_USER:
            raise AttachmentRefused(
                "attachment_quota_bytes",
                f"{int(held) + incoming} bytes is past the per-reader ceiling",
                status_code=429,
            )

    def _read(self, user_id: int, attachment_id: uuid.UUID) -> StoredBytes | None:
        """One row, for its owner. Somebody else's is ``None``, not a refusal."""
        with self._session_factory() as session:
            row = session.execute(
                select(AgentAttachment).where(
                    AgentAttachment.id == attachment_id,
                    AgentAttachment.user_id == user_id,
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            return StoredBytes(
                meta=StoredAttachment(
                    id=row.id,
                    media_type=row.media_type,
                    filename=row.filename,
                    byte_size=row.byte_size,
                    pixel_width=row.pixel_width,
                    pixel_height=row.pixel_height,
                ),
                content=bytes(row.content),
            )

    def _sweep_orphans(self, now: datetime | None) -> int:
        """Delete uploads that never became a Turn, and only those.

        An attachment with a Turn is part of a transcript that can be re-opened,
        and re-opening a Thread is supposed to draw what was sent. So the sweep
        is keyed on ``attached_turn_id IS NULL``: an upload nobody sent, past
        the grace period, is the only thing here nothing will ever read again.
        """
        cutoff = (now or datetime.now(timezone.utc)) - ORPHAN_TTL
        with self._session_factory() as session:
            removed = session.execute(
                delete(AgentAttachment).where(
                    AgentAttachment.attached_turn_id.is_(None),
                    AgentAttachment.created_at < cutoff,
                )
            ).rowcount
            session.commit()
            return int(removed or 0)


__all__ = [
    "ALLOWED_TYPES",
    "IMAGE_TYPES",
    "MAX_ATTACHMENTS_PER_USER",
    "MAX_ATTACHMENT_BYTES",
    "MAX_ATTACHMENT_BYTES_PER_USER",
    "MAX_IMAGES_PER_TURN",
    "MAX_IMAGE_PIXELS",
    "ORPHAN_TTL",
    "TEXT_TYPES",
    "AttachmentRefused",
    "assert_within_turn_budget",
    "AttachmentStore",
    "StoredAttachment",
    "StoredBytes",
    "image_tokens_for",
    "sanitise_filename",
    "serving_headers",
    "sniff_image",
]
