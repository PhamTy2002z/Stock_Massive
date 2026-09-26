"""Export the answers readers flagged, as JSON Lines, for review.

The "báo sai" button writes a reason onto the message (``agent_message``); this
reads that queue back with the question each answer was for and the claim
ledger the figure check wrote beside it. A reviewer reads one line per case and
decides whether the answer stated a wrong figure or the check accepted one.

    python -m scripts.export_flagged_answers --reason wrong_figure --since 2026-09-01 --out cases.jsonl

Read-only. Point ``DATABASE_URL`` at the store you mean before running it on
the host (a local Postgres can shadow the Docker one on localhost).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.agent.persistence import flagged_answers
from src.alpha.models import FLAG_REASONS
from src.core.database import get_sync_db


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reason", choices=sorted(FLAG_REASONS))
    parser.add_argument("--since", help="YYYY-MM-DD, flags written on or after this day")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--out", type=Path, help="file to write; stdout when omitted")
    args = parser.parse_args(argv)
    since = (
        datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc) if args.since else None
    )
    with get_sync_db() as session:
        cases = flagged_answers(session, reason=args.reason, since=since, limit=args.limit)
    lines = "".join(json.dumps(case, ensure_ascii=False) + "\n" for case in cases)
    if args.out:
        args.out.write_text(lines, encoding="utf-8")
        print(f"{len(cases)} case(s) written to {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(lines)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
