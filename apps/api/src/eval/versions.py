"""The three versions a fixture is frozen against, and the loud failure.

``docs/adr/0016``: *a mismatch makes the harness fail loud and refuse to run.*
The failure mode being designed out is not a crash — it is a green run. An old
fixture passed through a new Signal Registry produces flattering scores at
precisely the moment the registry changed, and nothing about that run looks
wrong from the outside. So the comparison happens before the first case, it
names which version moved, and it raises.

Each of the three is derived rather than declared, for the same reason
``registry_version`` is: a number somebody has to remember to bump is a number
that eventually names the wrong thing, and here being wrong is silent.

There is no pin for the tool catalog. The battery scores the nightly Analysis
lane, which calls no tool, and the harness that did has no frozen catalog to
name any more (``docs/adr/0026``): its tools are registered per process, so a pin
over them would move without the fixture moving.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from src.alpha.field_profile import FIELD_PROFILE_VERSION
from src.stocks.signals import registry_version

from .tables import store_schema_version


@dataclass(frozen=True)
class VersionMismatch:
    """One pinned version that no longer matches the running code."""

    name: str
    frozen: str
    running: str

    def __str__(self) -> str:
        return f"{self.name}: fixture pinned {self.frozen!r}, code is {self.running!r}"


class FixtureVersionMismatch(RuntimeError):
    """The fixture and the code disagree, so no battery may run.

    Carries the mismatches rather than only a sentence: the operator's next move
    is different for each — a moved ``registry_version`` means re-freeze, a
    moved ``schema_version`` means the seed cannot even be loaded — and a caller
    reading this has to be able to branch without parsing prose.
    """

    def __init__(self, mismatches: Sequence[VersionMismatch]) -> None:
        self.mismatches = tuple(mismatches)
        super().__init__(
            "the Eval Fixture was frozen against different code and must be "
            "re-captured before it can be run — "
            + "; ".join(str(item) for item in self.mismatches)
        )


@dataclass(frozen=True)
class PinnedVersions:
    """What the fixture recorded, or what the running build answers."""

    registry_version: str
    profile_version: str
    schema_version: str

    def as_wire(self) -> dict[str, str]:
        return {
            "registry_version": self.registry_version,
            "profile_version": self.profile_version,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> "PinnedVersions":
        missing = sorted(set(cls.__annotations__) - set(payload))
        if missing:
            raise ValueError(
                "the fixture manifest does not record " + ", ".join(missing)
            )
        return cls(**{name: str(payload[name]) for name in cls.__annotations__})

    def mismatches_against(self, running: "PinnedVersions") -> tuple[VersionMismatch, ...]:
        return tuple(
            VersionMismatch(
                name=name,
                frozen=getattr(self, name),
                running=getattr(running, name),
            )
            for name in self.__annotations__
            if getattr(self, name) != getattr(running, name)
        )

    def assert_matches(self, running: "PinnedVersions | None" = None) -> None:
        """Refuse to proceed unless every pin still names what the code is."""
        mismatches = self.mismatches_against(running or running_versions())
        if mismatches:
            raise FixtureVersionMismatch(mismatches)


def running_versions() -> PinnedVersions:
    """The three versions this build actually serves."""
    return PinnedVersions(
        registry_version=registry_version(),
        profile_version=FIELD_PROFILE_VERSION,
        schema_version=store_schema_version(),
    )


__all__ = [
    "FixtureVersionMismatch",
    "PinnedVersions",
    "VersionMismatch",
    "running_versions",
]
