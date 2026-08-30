"""Run a template the way production runs one, and read its frames back.

Every Study is now a plan whose steps are persisted one artifact each, so a test
that wants "the frames this Study produced" can no longer call a ``compute``
function — there is not one. It runs the plan and reads the rows back, which is
also the honest thing to be asserting on: what a reader sees comes out of those
rows and out of nothing else.

The reader is injected here for the same reason the runner takes it as an
argument — ``src/studies`` imports nothing from ``src/agent`` — and a test is
free to reach across that line because a test is not in the dependency graph
either package ships.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.agent.tools.query import read_source
from src.alpha.models import AgentArtifact
from src.core.database import get_sync_db
from src.studies import runner
from src.studies.contracts import StoredArtifact


@dataclass(frozen=True)
class RunFrame:
    """One step's frame, in the attribute names the Study wrote it under.

    Read off the persisted payload rather than off a :class:`Frame` the test
    kept a reference to, so what is asserted is what a browser would be served.
    """

    kind: str
    columns: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]
    unit: str | None
    labels: Mapping[str, str]
    column_roles: Mapping[str, str]
    point_roles: tuple[str | None, ...]
    cell_roles: Mapping[tuple[int, str], str]

    @classmethod
    def of(cls, payload: Mapping[str, Any]) -> "RunFrame":
        return cls(
            kind=str(payload.get("kind") or "table"),
            columns=tuple(str(name) for name in payload.get("columns") or ()),
            rows=tuple(tuple(row) for row in payload.get("rows") or ()),
            unit=payload.get("unit"),
            labels=dict(payload.get("labels") or {}),
            column_roles=dict(payload.get("columnRoles") or {}),
            point_roles=tuple(payload.get("pointRoles") or ()),
            cell_roles={
                (int(entry["row"]), str(entry["column"])): str(entry["role"])
                for entry in payload.get("cellRoles") or ()
            },
        )

    def column(self, name: str) -> list[Any]:
        position = self.columns.index(name)
        return [row[position] for row in self.rows]


@dataclass(frozen=True)
class TemplateRun:
    """What one run produced: the model's headline, the frames, and the board."""

    artifact: StoredArtifact
    frames: Mapping[str, RunFrame]

    @property
    def headline(self) -> Mapping[str, Any]:
        return self.artifact.headline

    @property
    def board(self):
        return self.artifact.signal_desk_spec

    def kpi(self, label: str):
        for cell in self.board.kpis:
            if cell.label == label:
                return cell
        raise KeyError(f"no KPI labelled {label!r}; the strip holds " + ", ".join(
            cell.label for cell in self.board.kpis
        ))


class _AUniverseOf:
    def __init__(self, symbols: Sequence[str]) -> None:
        self.symbols = tuple(symbols)


def run_template(
    name: str,
    params: Mapping[str, Any],
    *,
    universe: Sequence[str],
    monkeypatch,
    turn_id: UUID | None = None,
    thread_id: UUID | None = None,
    as_of: datetime | None = None,
) -> TemplateRun:
    """Run a registered template and hand back its artifact and every step frame.

    ``UNIVERSE_SYMBOLS`` is empty in the suite's settings — a declared Universe is
    operator configuration, not a test fixture — so the membership a template
    checks is stated by the caller rather than inherited from whatever the
    developer has in their environment.

    ``as_of`` freezes the run, for a template whose answer depends on when it
    was asked — a ladder is healthy at 16:00, degraded at 13:50 and a refusal
    the next morning, and a test of those three needs to say which.

    The session is rolled back before returning: a test asserting on numbers has
    no reason to leave six artifact rows behind, and the payloads have already
    been read out of them.
    """
    monkeypatch.setattr(
        runner, "build_universe", lambda session: _AUniverseOf(universe)
    )
    with get_sync_db() as session:
        artifact = runner.run(
            name,
            params,
            session=session,
            read=read_source,
            turn_id=turn_id,
            thread_id=thread_id,
            as_of=as_of,
        )
        frames = _steps_of(session, artifact.steps)
        session.rollback()
    return TemplateRun(artifact=artifact, frames=frames)


def _steps_of(
    session: Session, references: Mapping[str, str]
) -> dict[str, RunFrame]:
    """Each step's frame, fetched by the id the run itself handed back.

    By id rather than by scanning for rows whose params name this Study: the
    suite shares one database, so a scan would be answered by whatever another
    test happened to leave behind, and the winner among duplicates would be
    whatever order the table came back in. The run already knows exactly which
    rows it wrote — that is what ``StoredArtifact.steps`` is — so there is
    nothing to search for.
    """
    frames: dict[str, RunFrame] = {}
    for step, reference in references.items():
        identifier = UUID(reference.split("#", 1)[0])
        row = session.execute(
            select(AgentArtifact).where(AgentArtifact.id == identifier)
        ).scalar_one()
        payload = (row.frames or {}).get(step)
        if payload is not None:
            frames[step] = RunFrame.of(payload)
    return frames


__all__ = ["RunFrame", "TemplateRun", "run_template"]
