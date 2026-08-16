"""The frozen seed itself: what it records, and what reading it proves.

A fixture is one file. It holds the four captured tables, the manifest that says
what the capture was for, and nothing that a person is expected to edit —
``docs/adr/0016`` puts hand-editing outside the procedure, so the format makes it
detectable rather than merely discouraged: ``fixture_version`` is a digest of the
content, recomputed on every read.

That single choice buys three of the ticket's requirements at once. Capture is
**idempotent** — the same store at the same ``trading_day`` yields the same bytes
and the same version. A **re-freeze** after a registry change necessarily yields
a *new* version, because the pinned versions are inside the digest. And an
**edited** seed is refused, because its recorded version no longer describes it.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from .roles import FixtureRole
from .tables import CAPTURED_TABLES
from .versions import PinnedVersions

#: Bumped when a reader would have to parse the *file* differently. Separate
#: from ``schema_version``, which is about the store the rows came from: a
#: reader that cannot open the envelope and a reader that cannot trust its
#: contents are two failures with two remedies.
SEED_FORMAT_VERSION = 2


class FixtureSeedInvalid(RuntimeError):
    """A seed file that cannot be trusted to be what it says it is."""


@dataclass(frozen=True)
class FixtureManifest:
    """Everything about a fixture that is not a captured row."""

    trading_day: date
    versions: PinnedVersions
    # The Universe the battery runs against, pinned as the declared half. Read
    # `tables.py` for why the cohort is not captured instead.
    universe_symbols: tuple[str, ...]
    roles: Mapping[FixtureRole, str]
    watchlist: tuple[str, ...]
    # How many trading sessions back the capture reached. Recorded because a
    # window the fixture does not hold is an `insufficient_history` refusal that
    # says nothing about the symbol, and a reader comparing two fixtures needs
    # to be able to tell that apart from a shorter listing.
    history_sessions: int
    # The planted news of `news.py`, bound to the injection seat. In the
    # manifest rather than read from code at run time, so that re-wording an
    # embedded instruction changes `fixture_version` and voids the previous
    # baseline — a different injection is a different exam.
    news: tuple[Mapping[str, Any], ...] = ()

    def as_wire(self) -> dict[str, Any]:
        return {
            "trading_day": self.trading_day.isoformat(),
            "versions": self.versions.as_wire(),
            "universe_symbols": list(self.universe_symbols),
            "roles": {role.value: symbol for role, symbol in sorted(
                self.roles.items(), key=lambda item: item[0].value
            )},
            "watchlist": list(self.watchlist),
            "history_sessions": self.history_sessions,
            "news": [dict(item) for item in self.news],
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> "FixtureManifest":
        return cls(
            trading_day=date.fromisoformat(payload["trading_day"]),
            versions=PinnedVersions.from_wire(payload["versions"]),
            universe_symbols=tuple(payload["universe_symbols"]),
            roles={
                FixtureRole(role): str(symbol)
                for role, symbol in payload["roles"].items()
            },
            watchlist=tuple(payload["watchlist"]),
            history_sessions=int(payload["history_sessions"]),
            news=tuple(dict(item) for item in payload.get("news", ())),
        )

    @property
    def symbols(self) -> tuple[str, ...]:
        """Every symbol the fixture seats, Universe members and the outsider."""
        seen = dict.fromkeys(self.universe_symbols)
        seen.update(dict.fromkeys(self.roles.values()))
        return tuple(seen)


@dataclass(frozen=True)
class FixtureSeed:
    """One frozen capture, with the version its own content decides."""

    manifest: FixtureManifest
    tables: Mapping[str, tuple[Mapping[str, Any], ...]]

    @property
    def fixture_version(self) -> str:
        """``<trading day>-<digest>``: legible at a glance, exact underneath.

        The date is in front because a person reading two fixture versions in a
        pull request needs to know which exam is the newer one without looking
        anything up. The digest is what actually identifies it.
        """
        return f"{self.manifest.trading_day.isoformat()}-{self._digest()}"

    def _digest(self) -> str:
        payload = {
            "format": SEED_FORMAT_VERSION,
            "manifest": self.manifest.as_wire(),
            "tables": {
                name: list(self.tables.get(name, ()))
                for name in sorted(table.name for table in CAPTURED_TABLES)
            },
        }
        encoded = json.dumps(
            payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()[:16]

    def rows(self, table_name: str) -> tuple[Mapping[str, Any], ...]:
        return tuple(self.tables.get(table_name, ()))

    def as_wire(self) -> dict[str, Any]:
        return {
            "format": SEED_FORMAT_VERSION,
            "fixture_version": self.fixture_version,
            "manifest": self.manifest.as_wire(),
            "tables": {
                name: list(self.tables.get(name, ()))
                for name in sorted(table.name for table in CAPTURED_TABLES)
            },
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> "FixtureSeed":
        declared_format = int(payload.get("format", 0))
        if declared_format != SEED_FORMAT_VERSION:
            raise FixtureSeedInvalid(
                f"this seed is written in format {declared_format}; this build "
                f"reads format {SEED_FORMAT_VERSION}"
            )
        seed = cls(
            manifest=FixtureManifest.from_wire(payload["manifest"]),
            tables={
                name: tuple(rows) for name, rows in payload.get("tables", {}).items()
            },
        )
        recorded = str(payload.get("fixture_version", ""))
        if recorded != seed.fixture_version:
            raise FixtureSeedInvalid(
                "this seed records fixture_version "
                f"{recorded!r} but its contents digest to {seed.fixture_version!r}; "
                "a fixture is captured, never edited"
            )
        return seed


def write_seed(path: Path, seed: FixtureSeed) -> Path:
    """Write the seed so that an identical capture produces an identical file.

    Sorted keys and a fixed indent, and a trailing newline. The point is a
    reviewable diff: a re-freeze that moved one symbol should show one symbol
    moving, not a reshuffled file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(seed.as_wire(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def read_seed(path: Path) -> FixtureSeed:
    """Read and validate one seed file, or say why it cannot be trusted."""
    if not path.exists():
        raise FixtureSeedInvalid(
            f"no Eval Fixture at {path}: capture one with `make eval-fixture`"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FixtureSeedInvalid(f"{path} is not readable JSON: {exc}") from exc
    return FixtureSeed.from_wire(payload)


def seed_path(directory: Path, fixture_version: str) -> Path:
    return directory / f"{fixture_version}.json"


def latest_seed_path(directory: Path) -> Path:
    """The newest fixture in a directory, by the trading day in its name.

    Newest rather than only: a re-freeze lands beside its predecessor so the
    previous exam stays readable, and ``docs/adr/0016`` needs the old one to
    remain nameable when it voids a baseline.
    """
    candidates = sorted(directory.glob("*.json")) if directory.exists() else []
    if not candidates:
        raise FixtureSeedInvalid(
            f"no Eval Fixture in {directory}: capture one with `make eval-fixture`"
        )
    return candidates[-1]


__all__ = [
    "SEED_FORMAT_VERSION",
    "FixtureManifest",
    "FixtureSeed",
    "FixtureSeedInvalid",
    "latest_seed_path",
    "read_seed",
    "seed_path",
    "write_seed",
]
