"""Build and check the ``signal_desk`` corpus without a developer choosing it.

The questions come from people outside the repository, and the point of that is
lost the moment somebody here picks which fifty of them get measured. So the
choice is made by a seed: shuffle the labelled submissions deterministically,
fill each family's floor, then take the rest in shuffled order. Re-running with
the same seed on the same submissions gives the same corpus, and the corpus file
carries the seed and the digest of what it was drawn from, so the selection is
checkable by anyone who has both files.

Nothing here writes a question. Labelling — which family a question belongs to
and what the case expects — is a grading contract and stays with the repository;
the question itself never is.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import random
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

#: The six shapes of analytical question the desk claims to answer. A question
#: outside them is a question this corpus cannot label, not a seventh family
#: invented to fit it.
FAMILIES = (
    "single",
    "compare",
    "screen",
    "timeline",
    "decompose",
    "off_store",
)

#: Floors, not quotas. A run that is 40 comparisons measures the comparison
#: path and reports it as if it measured the desk.
MIN_PER_FAMILY = 6
FAMILY_FLOORS = {family: MIN_PER_FAMILY for family in FAMILIES}
FAMILY_FLOORS["compare"] = 12

TARGET_CASES = 50

#: The pool has to be bigger than the draw or the seed is decorative: fifty
#: submissions drawn fifty at a time is the whole pool under any seed, and the
#: corpus records a seed and a provenance for a choice nobody made. Twenty per
#: cent above the target is sixty at the default, which is the number the
#: collection asks for.
POOL_MARGIN = 1.2

CORPUS_ID = "signal-desk-v1"


def digest(value: Any) -> str:
    """SHA-256 of a canonical rendering, so formatting is not identity."""
    canonical = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _case_errors(case: Mapping[str, Any], index: int, *, label: str = "case") -> list[str]:
    where = f"{label}[{index}]"
    errors: list[str] = []
    if not str(case.get("id") or "").strip():
        errors.append(f"{where}: id is empty")
    if not str(case.get("question") or "").strip():
        errors.append(f"{where}: question is empty")
    family = str(case.get("family") or "")
    if family not in FAMILIES:
        errors.append(f"{where}: family {family!r} is not one of {', '.join(FAMILIES)}")
    expect = case.get("expect")
    if not isinstance(expect, Mapping):
        errors.append(f"{where}: expect is missing")
        return errors
    if not isinstance(expect.get("board"), bool):
        errors.append(f"{where}: expect.board must be true or false")
    minimum = expect.get("min_kpi")
    if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 0:
        errors.append(f"{where}: expect.min_kpi must be a non-negative integer")
    archetype = expect.get("archetype")
    if archetype is not None and not str(archetype).strip():
        errors.append(f"{where}: expect.archetype is present but empty")
    refusal = expect.get("refusal")
    if refusal is not None and not str(refusal).strip():
        errors.append(f"{where}: expect.refusal is present but empty")
    return errors


def _provenance_errors(corpus: Mapping[str, Any], case_count: int) -> list[str]:
    """A corpus with no draw behind it is a corpus somebody here wrote.

    This cannot prove the questions came from outside the repository — nothing
    in a file can. It can refuse to bless a corpus that never went through the
    draw, which is the step where a developer would otherwise choose the fifty.
    """
    selection = corpus.get("selection")
    if not isinstance(selection, Mapping):
        return ["selection is missing: this corpus was not drawn"]
    errors: list[str] = []
    seed = selection.get("seed")
    if not isinstance(seed, int) or isinstance(seed, bool):
        errors.append("selection.seed is not an integer")
    if len(str(selection.get("submissions_sha256") or "")) != 64:
        errors.append("selection.submissions_sha256 is missing")
    if selection.get("drawn") != case_count:
        errors.append(
            f"selection.drawn is {selection.get('drawn')!r}, corpus holds {case_count}"
        )
    drawn_from = selection.get("drawn_from")
    if not isinstance(drawn_from, int) or isinstance(drawn_from, bool):
        errors.append("selection.drawn_from is not an integer")
    elif drawn_from <= case_count:
        errors.append(
            f"selection.drawn_from is {drawn_from}, no larger than the {case_count} drawn"
        )
    return errors


def validate(corpus: Mapping[str, Any], *, target: int = TARGET_CASES) -> list[str]:
    """Every reason this corpus cannot be measured, rather than the first one."""
    cases = list(corpus.get("cases") or ())
    known = [
        case
        for case in cases
        if isinstance(case, Mapping) and str(case.get("family") or "") in FAMILIES
    ]
    if cases and not known:
        # Otherwise a corpus from another lane prints a hundred lines about its
        # every case, none of which name the one thing that is wrong with it.
        return ["not a signal_desk corpus: no case declares one of its six families"]

    errors: list[str] = []
    if len(cases) != target:
        errors.append(f"corpus holds {len(cases)} case(s), expected {target}")

    seen: set[str] = set()
    counts = dict.fromkeys(FAMILIES, 0)
    for index, case in enumerate(cases):
        if not isinstance(case, Mapping):
            errors.append(f"case[{index}]: not an object")
            continue
        errors.extend(_case_errors(case, index))
        identifier = str(case.get("id") or "")
        if identifier and identifier in seen:
            errors.append(f"case[{index}]: duplicate id {identifier!r}")
        if identifier:
            seen.add(identifier)
        family = str(case.get("family") or "")
        if family in counts:
            counts[family] += 1

    for family, floor in FAMILY_FLOORS.items():
        if counts[family] < floor:
            errors.append(
                f"family {family!r} has {counts[family]} case(s), floor is {floor}"
            )
    errors.extend(_provenance_errors(corpus, len(cases)))
    return errors


def _submission_errors(submissions: Sequence[Mapping[str, Any]]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(submissions):
        if not isinstance(item, Mapping):
            errors.append(f"submission[{index}]: not an object")
            continue
        errors.extend(_case_errors(item, index, label="submission"))
        identifier = str(item.get("id") or "")
        if identifier and identifier in seen:
            errors.append(f"submission[{index}]: duplicate id {identifier!r}")
        if identifier:
            seen.add(identifier)
    return errors


def select(
    submissions: Sequence[Mapping[str, Any]],
    *,
    seed: int,
    target: int = TARGET_CASES,
) -> dict[str, Any]:
    """Draw ``target`` labelled submissions with the family floors honoured.

    Floors first, then the remainder in shuffled order. Filling the floors from
    the same shuffled list is what keeps the draw a draw: within a family the
    order is still the seed's, so no submission is preferred for being early in
    the file or for reading well.
    """
    problems = _submission_errors(submissions)
    if problems:
        raise ValueError("; ".join(problems))
    required = max(target, math.ceil(target * POOL_MARGIN))
    if len(submissions) < required:
        raise ValueError(
            f"{len(submissions)} submission(s) is fewer than the {required} a draw of "
            f"{target} needs; collect more before drawing"
        )

    ordered = sorted(submissions, key=lambda item: str(item.get("id")))
    shuffled = list(ordered)
    random.Random(seed).shuffle(shuffled)

    by_family = {
        family: [item for item in shuffled if str(item.get("family")) == family]
        for family in FAMILY_FLOORS
    }
    # Every family short of its floor, not the first one. Collection is a slow
    # human loop — a form sent to people outside the repository — and each
    # shortfall hidden behind the first one costs another round of it.
    short = [
        f"family {family!r} has {len(items)} submission(s), floor is {FAMILY_FLOORS[family]}"
        for family, items in by_family.items()
        if len(items) < FAMILY_FLOORS[family]
    ]
    if short:
        raise ValueError("; ".join(short))

    picked: list[Mapping[str, Any]] = []
    taken: set[str] = set()
    for family, floor in FAMILY_FLOORS.items():
        for item in by_family[family][:floor]:
            picked.append(item)
            taken.add(str(item.get("id")))
    if len(picked) > target:
        raise ValueError(
            f"the family floors need {len(picked)} case(s), more than the {target} to draw"
        )
    for item in shuffled:
        if len(picked) >= target:
            break
        if str(item.get("id")) not in taken:
            picked.append(item)
            taken.add(str(item.get("id")))

    cases = sorted(picked, key=lambda item: str(item.get("id")))
    return {
        "corpus_id": CORPUS_ID,
        "description": (
            "Fifty analytical questions about the Vietnamese market, written by "
            "people outside the repository and drawn by seed rather than chosen."
        ),
        "families": {family: FAMILY_FLOORS[family] for family in FAMILIES},
        "selection": {
            "seed": seed,
            "drawn_from": len(submissions),
            "drawn": len(cases),
            "submissions_sha256": digest(list(ordered)),
        },
        # Deep, not shallow: a caller normalising the returned corpus would
        # otherwise reach back into the submissions the digest above was taken
        # over, and the recorded hash would describe objects that no longer exist.
        "cases": copy.deepcopy([dict(case) for case in cases]),
    }


def _load(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    draw = sub.add_parser("select", help="draw the corpus from labelled submissions")
    draw.add_argument("--submissions", required=True)
    draw.add_argument("--seed", type=int, required=True)
    draw.add_argument("--out", default="golden/signal_desk.json")
    draw.add_argument("--target", type=int, default=TARGET_CASES)
    draw.add_argument(
        "--force",
        action="store_true",
        help="redraw over an existing corpus file, orphaning every artifact digest",
    )

    check = sub.add_parser("validate", help="check a corpus file against the contract")
    check.add_argument("corpus")
    check.add_argument("--target", type=int, default=TARGET_CASES)

    args = parser.parse_args(argv)
    path = args.submissions if args.command == "select" else args.corpus
    try:
        payload = _load(path)
    except (OSError, json.JSONDecodeError) as error:
        print(f"{path}: {error}")
        return 1

    if args.command == "validate":
        errors = validate(payload, target=args.target)
        for error in errors:
            print(error)
        if not errors:
            print(f"{path}: valid, sha256 {digest(payload)}")
        return 1 if errors else 0

    # A redraw replaces the questions every artifact already written was scored
    # against, and nothing in the tree would reproduce those digests afterwards.
    out = Path(args.out)
    if out.exists() and not args.force:
        print(f"{out}: already exists; pass --force to redraw over it")
        return 1
    if not isinstance(payload, Mapping) or not isinstance(payload.get("submissions"), list):
        print(f"{path}: expected an object with a 'submissions' list")
        return 1
    try:
        corpus = select(payload["submissions"], seed=args.seed, target=args.target)
    except ValueError as error:
        print(str(error))
        return 1
    errors = validate(corpus, target=args.target)
    if errors:
        for error in errors:
            print(error)
        return 1
    out.write_text(
        json.dumps(corpus, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"{out}: {len(corpus['cases'])} case(s), sha256 {digest(corpus)}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI
    raise SystemExit(main())
