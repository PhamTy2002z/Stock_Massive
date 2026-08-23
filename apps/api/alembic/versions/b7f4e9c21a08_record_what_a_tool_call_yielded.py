"""record what a tool call yielded, not only whether it ran

``agent_tool_call.status`` answers which kind of outcome a call had and
``error`` names the failure it was, and between them they cannot express the
thing a third of this table's ``get_field`` rows actually are: a call that
worked, asked a well-formed question, and came back with no number.

Measured before writing this, over the rows already in the table: of 151
``get_field`` calls, 94 carried a figure, 42 carried a refusal and 15 said the
symbol was outside the Universe. All 151 are stored as ``ok``, because all 151
*were* ``ok`` — the tool returns a refusal as a result the model reads rather
than as an exception, which is right, and leaves the trace unable to tell the
two apart. Whether an evidence path answers is the one thing this table exists
to be asked, and it was the one thing it could not be.

Not a new status value. ``status`` is a closed four-value vocabulary about the
kind of outcome (``src/alpha/models.py``), and a fifth value meaning "fine, but
empty" would make every existing reader of ``status = 'ok'`` quietly wrong about
rows it had been counting correctly. A separate column leaves those readers
alone.

The refusal's own reason is kept, not flattened. ``no_value:market_cap_absent``
and ``no_value:insufficient_cross_section`` have different causes and different
fixes — one is a Main Source that did not write a capitalisation, the other a
sample too thin to rank — and one word for both would rebuild the blind spot one
level up from where it was.

Additive and nullable: one ADD COLUMN, no backfill, no existing column touched.
The 498 rows already here cannot be told what they yielded — their payloads are
stored, but reading a figure out of them now would be this migration inventing
history — so they keep ``NULL``, which reads as "not classified" and not as
"answered nothing".
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7f4e9c21a08"
down_revision: Union[str, None] = "a3c7e21b8f65"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agent_tool_call",
        sa.Column("outcome", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_tool_call", "outcome")
