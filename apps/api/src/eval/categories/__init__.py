"""The seeded battery: importing this package is what puts cases on the table.

``cases.py`` holds the shape and an empty registry; the cases themselves live
here, one module per group of categories. Registration happens at import, and
the import is explicit in ``src/eval/cli.py`` rather than tucked into
``src/eval/__init__.py``: a battery that assembled itself as a side effect of
touching the package would be a battery whose contents depend on which module
somebody imported first.

**Cases are seeded once.** After that the battery grows only through the flag
loop of ``docs/adr/0016`` — a flagged message confirmed as a genuine failure
becomes a new case, frozen with its fixture. Nobody adds cases to improve a
score, and there is no documented workflow that would let them.
"""

from __future__ import annotations

from . import safety  # noqa: F401  - imported for its registration side effect

__all__ = ["safety"]
