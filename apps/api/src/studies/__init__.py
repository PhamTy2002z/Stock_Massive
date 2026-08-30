"""Studies: named, versioned analysis recipes the chat lane can draw.

Imported by ``src/agent/`` and importing nothing from it — the dependency runs
one way, so a Study stays testable without a model and the agent stays free to
change how it presents one.

Registering a Study means importing the module that declares it. The imports at
the bottom of this file are that act; a Study whose module nobody imports is
absent from the catalog no matter how correctly it is written.
"""

from .contracts import (
    BoardSpec,
    ComputeStep,
    QueryStep,
    ReadStep,
    SignalDeskBlock,
    SignalDeskSpec,
    Frame,
    Provenance,
    StoredArtifact,
    StudyContext,
    StudyDefinition,
    StudyRefused,
)
from .registry import REGISTRY, catalog, register, study
from .runner import StudyParamsInvalid, run

# Registration is an import. Keep this last: the modules below reach back into
# the registry above, and a Study nobody imports is absent from the catalog
# however correctly it is written.
from . import templates  # noqa: F401  (imported for its side effect)

__all__ = [
    "BoardSpec",
    "ComputeStep",
    "QueryStep",
    "ReadStep",
    "SignalDeskBlock",
    "SignalDeskSpec",
    "Frame",
    "Provenance",
    "REGISTRY",
    "StoredArtifact",
    "StudyContext",
    "StudyDefinition",
    "StudyParamsInvalid",
    "StudyRefused",
    "catalog",
    "register",
    "run",
    "study",
]
