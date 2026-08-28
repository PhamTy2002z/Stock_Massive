"""Naming three numbers across three statement templates, or saying unknown.

A screener needs "net profit this quarter", and the store holds whatever the
provider called it. This module is the only place that decides which stored line
answers a named concept, so a mapping that turns out wrong is a patch here and
never a market-wide re-fetch.

**Two of the three concepts need no per-template mapping.** Measured 2026-08-27
on the three templates this market reports under:
``net_profit_loss_after_tax`` and ``owners_equity`` are present for STB (bank),
SSI (securities) and HPG (non-financial) alike. STB's ``owners_equity`` for
2026-Q2 is 62,807,249,000,000, which is exactly the ``parent_equity_vnd``
already stored under the ``fundamental`` Capability in ``provider_snapshots``
for the same quarter — two independent paths to the same number.

**Pretax profit is where the templates actually differ.** STB and HPG both
report ``net_accounting_profit_loss_before_tax``. SSI reports no correctly
labelled pretax line at all: its pretax figure arrives under
``business_income_tax_expenses`` (+1,528,966,041,130 for 2026-Q2 — positive,
which no tax expense is). That is not read from the label but from an identity
that holds for every quarter in the response:

    net_profit_loss_after_tax
        == candidate + business_income_tax_current + business_income_tax_deferred

For SSI 2026-Q2: 1,528,966,041,130 − 301,667,112,228 + 4,585,945,424 =
1,231,884,874,326, the reported net profit to the dong. The same gate refuses
STB's ``business_income_tax_expenses``, whose value there really is the tax
(−683,200,000,000, and −683,200,000,000 + −683,200,000,000 is nowhere near its
net profit), so the fallback cannot turn a tax expense into a pretax profit.

**Unknown is an answer.** A concept whose line is missing — and a pretax
candidate that fails the identity — resolves to ``unknown`` and never to a
substitute number. The screener excludes unknown symbols and says how many it
excluded; a plausible wrong number does neither.

``core_operating_result`` is a non-goal here. The templates genuinely disagree
about it (a bank's is ``net_operating_profit_before_allowance_for_credit_loss``,
a securities house's ``operating_profit_loss``), and nothing in the roadmap
consumes it, so three mappings would be three things to keep true for no reader.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Mapping

from . import STATEMENT_BALANCE, STATEMENT_INCOME

#: One symbol's lines for one quarter at ``item_seq = 0``, keyed by
#: ``(statement, item_id)``. The first occurrence is the one a concept resolves
#: against: where the provider repeats an ``item_id``, the later occurrences have
#: been measured to be a different line arriving under the wrong id.
Lines = Mapping[tuple[str, str], Decimal]


class Concept(str, Enum):
    """A number a reader can ask for without knowing the template."""

    NET_PROFIT = "net_profit"
    PRETAX_PROFIT = "pretax_profit"
    EQUITY = "equity"


CONCEPTS = tuple(Concept)

#: How a resolved value was arrived at. Stored on the answer rather than
#: implied, because "the provider labelled it this" and "the arithmetic says it
#: is this" are different strengths of evidence.
BASIS_LABELLED = "labelled"
BASIS_TAX_IDENTITY = "tax_identity"
BASIS_UNKNOWN = "unknown"

NET_PROFIT_ITEM = (STATEMENT_INCOME, "net_profit_loss_after_tax")
PRETAX_ITEM = (STATEMENT_INCOME, "net_accounting_profit_loss_before_tax")
EQUITY_ITEM = (STATEMENT_BALANCE, "owners_equity")

#: The mislabelled line SSI's pretax profit arrives under, accepted only when
#: the tax identity holds for it.
PRETAX_UNLABELLED_CANDIDATES = (
    (STATEMENT_INCOME, "business_income_tax_expenses"),
)

TAX_CURRENT_ITEM = (STATEMENT_INCOME, "business_income_tax_current")
TAX_DEFERRED_ITEM = (STATEMENT_INCOME, "business_income_tax_deferred")

#: How far the tax identity may miss before the candidate is refused. Relative,
#: because the numbers span a bank's trillions and a small cap's hundreds of
#: millions; the floor is there because a statement rounded to the thousand dong
#: would otherwise fail on a small quarter. Measured responses satisfy the
#: identity exactly, so this is slack for rounding and not for interpretation.
TAX_IDENTITY_TOLERANCE = Decimal("0.0005")
TAX_IDENTITY_FLOOR = Decimal("1000")


#: Every line the resolver can read, so a market-wide read can ask for those and
#: nothing else. A statement is 25 to 208 lines per symbol and a quarter of the
#: market is over a hundred thousand rows; the screener needs eight of them.
REQUIRED_ITEMS = (
    NET_PROFIT_ITEM,
    PRETAX_ITEM,
    EQUITY_ITEM,
    TAX_CURRENT_ITEM,
    TAX_DEFERRED_ITEM,
    *PRETAX_UNLABELLED_CANDIDATES,
)


@dataclass(frozen=True)
class ConceptValue:
    """What one concept resolved to for one symbol and quarter."""

    concept: Concept
    value: Decimal | None
    item_id: str | None
    basis: str

    @property
    def is_unknown(self) -> bool:
        return self.value is None


def unknown(concept: Concept) -> ConceptValue:
    """The answer when no stored line resolves the concept."""
    return ConceptValue(
        concept=concept, value=None, item_id=None, basis=BASIS_UNKNOWN
    )


def resolve(concept: Concept, lines: Lines) -> ConceptValue:
    """The concept's value from one quarter's lines, or unknown."""
    if concept is Concept.NET_PROFIT:
        return _labelled(concept, NET_PROFIT_ITEM, lines)
    if concept is Concept.EQUITY:
        return _labelled(concept, EQUITY_ITEM, lines)
    if concept is Concept.PRETAX_PROFIT:
        return _pretax(lines)
    raise ValueError(f"{concept!r} is not a concept; expected one of {CONCEPTS}")


def resolve_all(lines: Lines) -> dict[Concept, ConceptValue]:
    """Every concept for one quarter's lines, unknowns included."""
    return {concept: resolve(concept, lines) for concept in CONCEPTS}


def _labelled(
    concept: Concept, item: tuple[str, str], lines: Lines
) -> ConceptValue:
    value = lines.get(item)
    if value is None:
        return unknown(concept)
    return ConceptValue(
        concept=concept, value=value, item_id=item[1], basis=BASIS_LABELLED
    )


def _pretax(lines: Lines) -> ConceptValue:
    """The pretax line, by label where there is one and by identity where not."""
    labelled = _labelled(Concept.PRETAX_PROFIT, PRETAX_ITEM, lines)
    if not labelled.is_unknown:
        return labelled

    for item in PRETAX_UNLABELLED_CANDIDATES:
        candidate = lines.get(item)
        if candidate is None:
            continue
        if _satisfies_tax_identity(candidate, lines):
            return ConceptValue(
                concept=Concept.PRETAX_PROFIT,
                value=candidate,
                item_id=item[1],
                basis=BASIS_TAX_IDENTITY,
            )
    return unknown(Concept.PRETAX_PROFIT)


def _satisfies_tax_identity(candidate: Decimal, lines: Lines) -> bool:
    """Whether ``net == candidate + tax_current + tax_deferred`` for this quarter.

    Both tax lines have to be present. Treating a missing one as zero would let
    the identity pass on a template that simply does not report it, which is the
    guess this whole module refuses to make.
    """
    net = lines.get(NET_PROFIT_ITEM)
    current = lines.get(TAX_CURRENT_ITEM)
    deferred = lines.get(TAX_DEFERRED_ITEM)
    if net is None or current is None or deferred is None:
        return False
    gap = abs(net - (candidate + current + deferred))
    allowed = max(abs(net) * TAX_IDENTITY_TOLERANCE, TAX_IDENTITY_FLOOR)
    return gap <= allowed


__all__ = [
    "BASIS_LABELLED",
    "BASIS_TAX_IDENTITY",
    "BASIS_UNKNOWN",
    "CONCEPTS",
    "EQUITY_ITEM",
    "NET_PROFIT_ITEM",
    "PRETAX_ITEM",
    "REQUIRED_ITEMS",
    "TAX_IDENTITY_FLOOR",
    "TAX_IDENTITY_TOLERANCE",
    "Concept",
    "ConceptValue",
    "Lines",
    "resolve",
    "resolve_all",
    "unknown",
]
