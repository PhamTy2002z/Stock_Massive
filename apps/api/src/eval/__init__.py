"""The Evaluation lane: a measurement system wrapped around the runtime.

This package exists to answer one question — did a model change make the
answers better or worse — reproducibly, over frozen evidence, without spending
a single live data-provider call.

Two boundary rules are absolute, and both were paid for by the harness that
was deleted at ``1974c24``:

**Production never imports this package.** No module under ``src.agent`` or
``src.alpha``, no app startup path, no API route names ``src.eval``. Eval
depends inward on public runtime seams (prompt contract, tool registry,
LLM config); the runtime does not know eval exists. The direction of every
import below points one way.

**No import has side effects.** Importing this package reads no database,
touches no provider, starts nothing. A measurement system that perturbs the
thing it measures is not measuring it.
"""

from __future__ import annotations

__all__: list[str] = []
