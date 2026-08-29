"""Which domain this deployment answers questions about.

One pack exists, so the choice is a module-level constant. Writing down why,
because the next person to need this will need something else:

**The lifetime of this choice is the process; the lifetime that will matter is
the Turn.** ``ToolContext`` is built per Turn (``loop.py``) and ``AgentLoop``
per Turn (``service.py``), so a deployment that must serve two tenants two
different packs has the seam it needs already — the pack moves onto the request,
not into a wider module-level variable. That work is not done here because it is
not needed here: exactly one pack exists, and a selection mechanism for a set of
one is a mechanism with no way to be wrong and no way to be tested. What this
comment buys is that the constraint does not have to be rediscovered.

**A pack carries no mutable state**, which is what makes the constant safe in
the meantime: :class:`~.pack.DomainPack` is frozen, so two Turns reading it
concurrently cannot observe each other. Adding a mutable field to a pack is the
change this comment exists to have review stop.
"""

from __future__ import annotations

from .pack import DomainPack, DomainPackInvalid
from .vn_equity import PACK as VN_EQUITY

#: Every pack this build knows how to be. Keyed by the name the pack declares,
#: so the key and the pack cannot disagree.
PACKS: dict[str, DomainPack] = {VN_EQUITY.name: VN_EQUITY}

#: The one this deployment is. See the module docstring for why this is a
#: constant and what would have to move if it stopped being one.
ACTIVE_PACK = "vn-equity"


def active_pack() -> DomainPack:
    """The pack every Turn of this process answers under."""
    try:
        return PACKS[ACTIVE_PACK]
    except KeyError:  # pragma: no cover - a build that cannot serve at all
        raise DomainPackInvalid(
            f"ACTIVE_PACK names {ACTIVE_PACK!r}, which no pack declares; known "
            f"packs are {', '.join(sorted(PACKS))}"
        ) from None


__all__ = [
    "ACTIVE_PACK",
    "PACKS",
    "DomainPack",
    "DomainPackInvalid",
    "active_pack",
]
