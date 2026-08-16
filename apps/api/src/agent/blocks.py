"""Splitting an answer into the units a Turn is allowed to release.

``docs/adr/0013`` emits ``content.block`` and never ``content.delta``, for two
reasons that both land here.  A half-streamed Markdown table or an unclosed code
fence is unreadable, so character-level delivery buys the appearance of speed at
the cost of legibility.  And a block is the smallest unit whose grounding can be
proven (``docs/adr/0015``), so it is also the smallest unit that can honestly be
shown.

The split is therefore by *presentation unit*, not by sentence or by token: a
paragraph, a related bullet group, a complete table, a closed code fence.  Blank
lines already separate all four in Markdown — with one exception, which is why
this is a function rather than ``text.split``: a fenced block may contain blank
lines of its own, and splitting inside one produces exactly the unclosed fence
the decision exists to prevent.
"""

from __future__ import annotations

FENCE_MARKERS = ("```", "~~~")


def _opens_fence(line: str) -> str | None:
    stripped = line.lstrip()
    for marker in FENCE_MARKERS:
        if stripped.startswith(marker):
            return marker
    return None


def split_blocks(text: str) -> tuple[str, ...]:
    """One answer, as the ordered presentation units it may be released in.

    Empty units are dropped rather than emitted: a blank ``content.block`` is a
    sequence number spent on nothing, and a reconnecting subscriber would have
    to render it.
    """
    if not text:
        return ()

    blocks: list[str] = []
    current: list[str] = []
    fence: str | None = None

    def flush() -> None:
        joined = "\n".join(current).strip()
        current.clear()
        if joined:
            blocks.append(joined)

    for line in text.splitlines():
        if fence is None:
            marker = _opens_fence(line)
            if marker is not None:
                # A fence starts its own block: whatever preceded it was a
                # complete unit, and mixing the two would make the fence
                # unclosable if the answer stops here.
                flush()
                fence = marker
                current.append(line)
                continue
            if not line.strip():
                flush()
                continue
            current.append(line)
            continue

        current.append(line)
        if line.strip().startswith(fence):
            fence = None
            flush()

    flush()
    return tuple(blocks)


__all__ = ["split_blocks"]
