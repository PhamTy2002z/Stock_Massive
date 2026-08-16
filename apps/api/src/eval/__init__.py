"""The Eval Fixture and the Eval Battery harness (``docs/adr/0016``).

Nothing in here is imported by the serving application. That separation is the
point of a package rather than a module beside the agent: the battery reads a
**dedicated eval database** and must never be able to reach the one the API
serves from, and an import edge from ``src.main`` into this package would be the
first step towards a code path that could.

**Importing the package seats the battery.** A case registers itself as its
module is imported, so those modules are imported here rather than by whichever
caller happened to reach one first. A battery whose contents depended on an
import edge somewhere upstream is a battery that quietly runs a subset of
itself — and a subset publishes a per-category total over cases nobody ran.
"""

# Imported for the registration side effect, which is the point. `battery()`
# reads one registry, and a case module nobody imported is a case that silently
# left the exam.
from . import analysis_cases as _analysis_cases  # noqa: F401
