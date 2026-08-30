"""The calculation axis of the analysis compiler: pandas over frames, in a box.

Three modules and one script. :mod:`validator` decides whether code may run;
:mod:`runner` runs it in a process of its own; :mod:`frames_io` turns what came
back into a :class:`~src.studies.contracts.Frame` with honest provenance. The
script is ``worker.py``, which is spawned rather than imported and imports
nothing from this project — see its own docstring for why that is the boundary.
"""

from __future__ import annotations

from .frames_io import derived_provenance, frame_from_result, input_payload
from .runner import (
    CPU_SECONDS,
    MAX_RESULT_COLUMNS,
    MAX_RESULT_ROWS,
    MEMORY_BYTES,
    WALL_SECONDS,
    run,
)
from .validator import MAX_CODE_CHARS, Violation, first_code, validate

__all__ = [
    "CPU_SECONDS",
    "MAX_CODE_CHARS",
    "MAX_RESULT_COLUMNS",
    "MAX_RESULT_ROWS",
    "MEMORY_BYTES",
    "WALL_SECONDS",
    "Violation",
    "derived_provenance",
    "first_code",
    "frame_from_result",
    "input_payload",
    "run",
    "validate",
]
