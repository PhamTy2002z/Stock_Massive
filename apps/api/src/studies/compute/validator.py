"""What a model may write inside ``compute``, checked before anything runs.

The analysis compiler's whole bet is that the *calculation* axis should be
general — a model writes pandas over frames it already gathered rather than
picking from a closed list of operations somebody guessed at in advance. That
bet only pays if the invariant survives it: **the model never types a market
number.** A closed enum of operations enforced that by construction. Arbitrary
code has to enforce it by inspection, and this is the inspection.

So the rule is not "no arithmetic". It is that every number entering a
calculation comes from a frame, and the only literals the code may spell are the
ones that describe *structure* rather than measurement — a column position, four
quarters, a percentage's hundred, a year's trading sessions. Anything else is a
figure, and a figure has to be declared as a constant with a reason attached, so
a reader of the artifact can see it was asserted rather than computed.

Four other refusals ride along, and they are about the sandbox rather than about
numbers. Imports are held to five modules; the names that reach outside the
process are refused by name; dunder attributes are refused as a family, because
every published escape from a Python namespace goes through one; and code that
never assigns ``result`` is refused before a subprocess is spawned for it.

**Every refusal is returned, never raised.** A rejected calculation is a model
mistake the model can fix on the next round, which is a different thing from a
tool that broke — and the loop counts those two differently.

**What this is not: a proof.** ``7 / 100`` is two structural numbers and it is
also 0.07, and no reading of the code can tell that apart from a legitimate
percentage without knowing what the question was. Arithmetic over the structural
set reaches everything, so a model that has decided to smuggle a figure can. What
this closes is every *obvious* route — the literal, the literal in a filter, the
literal with quotes around it — each named, so a model following its
instructions never types a figure by accident and one that does is told exactly
what it did. The proof that a number is real lives one layer up, where the
number came out of a frame that came out of the store.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

#: The numbers that describe shape rather than measurement, and may therefore be
#: written directly.
#:
#: ``0``–``12``: positions, small counts, and the twelve months of a year. A
#: window of eight quarters and a lag of one session are structure; there is no
#: market claim inside either.
#: ``100``: what a ratio is multiplied by to become a percentage.
#: ``252``: trading sessions in a year, the annualising divisor.
#: ``365``: days in a year, for anything expressed per calendar day.
#: ``1_000``, ``1_000_000``, ``1_000_000_000``: the unit scales a Vietnamese
#: figure is rebased by — nghìn, triệu, tỷ.
#:
#: Nothing else. A rolling window of twenty sessions, a quantile of 0.75, a
#: threshold of 5%: all three are judgements about the market, and all three go
#: through ``constants`` where the reason is recorded beside the number.
STRUCTURAL_NUMBERS: frozenset[float] = frozenset(
    {*range(0, 13), 100, 252, 365, 1_000, 1_000_000, 1_000_000_000}
)

#: The five modules a calculation may import. Everything a table of numbers
#: needs, and nothing that opens a socket or a file.
ALLOWED_MODULES: frozenset[str] = frozenset(
    {"pandas", "numpy", "math", "statistics", "datetime"}
)

#: Names that reach outside the namespace they are written in. Refused by name
#: rather than by removing them from the sandbox's builtins, because a refusal
#: the model reads before anything runs is a refusal it can act on.
FORBIDDEN_NAMES: frozenset[str] = frozenset(
    {
        "open",
        "eval",
        "exec",
        "compile",
        "__import__",
        "getattr",
        "setattr",
        "delattr",
        "vars",
        "globals",
        "locals",
        "input",
        "breakpoint",
        "memoryview",
        "print",
    }
)

#: Attribute names on pandas objects that read or write the world. Matched by
#: shape (``read_*``, ``to_*``) rather than by a list, so a pandas release that
#: adds a reader does not silently add a hole; the pure conversions that share
#: the prefix are named below because they are the exceptions, and there are few.
_IO_PREFIXES: tuple[str, ...] = ("read_", "to_")

PURE_CONVERSIONS: frozenset[str] = frozenset(
    {
        "to_numpy",
        "to_list",
        "to_dict",
        "to_frame",
        "to_series",
        "to_datetime",
        "to_numeric",
        "to_timedelta",
        "to_period",
        "to_timestamp",
        "to_records",
    }
)

#: Methods whose numeric arguments count rows or digits rather than assert a
#: figure. ``head(20)`` says how much of a table to show and ``round(2)`` says
#: how precisely to print it; neither is a claim about a company.
COUNT_METHODS: frozenset[str] = frozenset(
    {"head", "tail", "nlargest", "nsmallest", "round"}
)

#: Calls that turn whatever they are given into a number. A string handed to one
#: of these is a numeric literal with quotes around it — ``float("0.07")`` reads
#: exactly like typing ``0.07`` and is the nearest thing to an obvious way past
#: the rule above, so the string is read as the number it is about to become.
#:
#: Only in this position, deliberately. A numeric-looking string is otherwise a
#: label — a column, a period, a symbol — and refusing every one of those would
#: refuse ``f0['2025']`` on a pivoted table.
COERCIONS: frozenset[str] = frozenset(
    {"float", "int", "Decimal", "to_numeric", "astype", "float64", "int64"}
)

#: The variable the sandbox reads the answer out of.
RESULT_NAME = "result"

#: How long a calculation may be. A ceiling on the *request*, so a model that
#: pasted a script rather than writing an expression is told so before a
#: subprocess is spawned for it.
MAX_CODE_CHARS = 4_000

LITERAL_NUMBER = "compute_literal_number"
FORBIDDEN_IMPORT = "compute_forbidden_import"
FORBIDDEN_NAME = "compute_forbidden_name"
NO_RESULT = "compute_no_result"
SYNTAX_ERROR = "compute_syntax_error"


@dataclass(frozen=True)
class Violation:
    """One reason this code will not be run, and where in it to look."""

    code: str
    line: int
    snippet: str
    detail: str

    def to_payload(self) -> dict[str, object]:
        return {
            "code": self.code,
            "line": self.line,
            "snippet": self.snippet,
            "detail": self.detail,
        }


def validate(code: str) -> tuple[Violation, ...]:
    """Every reason this code will not be run, in the order they appear.

    Every reason and not the first one: a model handed one violation at a time
    would spend a round of the Turn per mistake, and the Turn has four.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return (
            Violation(
                code=SYNTAX_ERROR,
                line=exc.lineno or 1,
                snippet=(exc.text or "").strip()[:120],
                detail=f"Python không đọc được dòng này: {exc.msg}.",
            ),
        )

    lines = code.splitlines()
    exempt = _positions_that_are_not_figures(tree)
    found: list[Violation] = []

    def note(node: ast.AST, code_name: str, detail: str) -> None:
        line = getattr(node, "lineno", 1)
        snippet = lines[line - 1].strip()[:120] if 0 < line <= len(lines) else ""
        found.append(
            Violation(code=code_name, line=line, snippet=snippet, detail=detail)
        )

    assigns_result = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Store) and node.id == RESULT_NAME:
                assigns_result = True
            if node.id in FORBIDDEN_NAMES or _is_dunder(node.id):
                note(
                    node,
                    FORBIDDEN_NAME,
                    f"{node.id!r} không dùng được ở đây; phép tính chỉ đọc "
                    "các bảng đã truyền vào.",
                )
        elif isinstance(node, ast.Attribute):
            problem = _attribute_problem(node.attr)
            if problem is not None:
                note(node, FORBIDDEN_NAME, problem)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for name in _imported_roots(node):
                if name not in ALLOWED_MODULES:
                    note(
                        node,
                        FORBIDDEN_IMPORT,
                        f"{name!r} không nhập được; chỉ có "
                        + ", ".join(sorted(ALLOWED_MODULES))
                        + ".",
                    )
        elif isinstance(node, ast.Call):
            coerced = _coerced_number(node)
            if coerced is not None and coerced not in STRUCTURAL_NUMBERS:
                note(
                    node,
                    LITERAL_NUMBER,
                    f"{coerced!r} viết dưới dạng chuỗi vẫn là một con số phải "
                    "lấy từ dữ liệu. Nếu nó là một giả định của câu hỏi, khai "
                    "nó ở constants kèm lý do.",
                )
        elif isinstance(node, ast.Constant):
            value = node.value
            if isinstance(value, bool) or not isinstance(value, (int, float, complex)):
                continue
            if id(node) in exempt:
                continue
            if isinstance(value, complex) or value not in STRUCTURAL_NUMBERS:
                note(
                    node,
                    LITERAL_NUMBER,
                    f"{value!r} là một con số phải lấy từ dữ liệu, không phải "
                    "gõ vào. Nếu nó là một giả định của câu hỏi, khai nó ở "
                    "constants kèm lý do.",
                )

    if not assigns_result:
        found.append(
            Violation(
                code=NO_RESULT,
                line=len(lines) or 1,
                snippet="",
                detail=(
                    "Phép tính phải kết thúc bằng result = <bảng>, và result "
                    "phải là một bảng hoặc một chuỗi số."
                ),
            )
        )

    found.sort(key=lambda violation: (violation.line, violation.code))
    return tuple(found)


def _is_dunder(name: str) -> bool:
    """A name Python reserves for its own machinery.

    Refused as a family rather than one at a time. Every published escape from a
    restricted namespace walks a chain of these — ``().__class__.__bases__``,
    ``__subclasses__``, ``__globals__`` — and a list of the ones known today is a
    list that goes stale the next time somebody finds a fourth.
    """
    return name.startswith("__") and name.endswith("__")


#: Attribute names that only ever name a way out of the calculation.
#:
#: A denylist, and it is a *readability* device rather than a boundary — which is
#: the distinction this file has always drawn about itself. The boundary is in
#: ``worker.py``, where the calls are taken off the module objects themselves;
#: what this adds is that the model reads a sentence naming its mistake before
#: anything runs, instead of a ``PermissionError`` out of a library it did not
#: know it was calling.
#:
#: It cannot be an allowlist. The reachable surface of ``pandas`` is thousands of
#: attribute names and the escape route was ``pd.io.common.os`` — a module object
#: hanging off a library module, with no import statement anywhere. Reading types
#: is not something an AST pass can do, so this pass stopped trying to be the
#: gate and became the message.
ESCAPE_ATTRIBUTES: frozenset[str] = frozenset(
    {
        "os",
        "posix",
        "nt",
        "sys",
        "subprocess",
        "ctypes",
        "socket",
        "shutil",
        "pathlib",
        "tempfile",
        "importlib",
        "builtins",
        "pickle",
        "marshal",
        "gc",
        "mmap",
        "tarfile",
        "zipfile",
        "gzip",
        "codecs",
        "threading",
        "multiprocessing",
        "_getframe",
        "f_globals",
        "f_builtins",
        "f_locals",
        "gi_frame",
        "cr_frame",
    }
)


def _attribute_problem(attr: str) -> str | None:
    """Why this attribute may not be reached, or ``None`` when it may."""
    if _is_dunder(attr):
        return (
            f"{attr!r} là chỗ Python giữ cho chính nó; phép tính chỉ dùng các "
            "phép trên bảng."
        )
    if attr in PURE_CONVERSIONS:
        return None
    if attr.startswith(_IO_PREFIXES):
        return (
            f"{attr!r} đọc hoặc ghi ra ngoài; số liệu chỉ vào qua các bảng đã "
            "truyền vào inputs."
        )
    if attr in ESCAPE_ATTRIBUTES:
        return (
            f"{attr!r} dẫn ra ngoài phép tính; một phép tính chỉ làm các phép "
            "trên các bảng đã truyền vào inputs."
        )
    return None


def _coerced_number(node: ast.Call) -> float | None:
    """The number a string is about to be turned into, if that is what this is."""
    func = node.func
    named = (
        func.id
        if isinstance(func, ast.Name)
        else func.attr
        if isinstance(func, ast.Attribute)
        else ""
    )
    if named not in COERCIONS:
        return None
    for argument in node.args:
        if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
            try:
                return float(argument.value.strip())
            except ValueError:
                continue
    return None


def _imported_roots(node: ast.Import | ast.ImportFrom) -> Iterator[str]:
    if isinstance(node, ast.Import):
        for alias in node.names:
            yield alias.name.split(".")[0]
        return
    # ``from . import x`` has no module; a relative import inside the sandbox
    # names nothing importable, so it is reported under its own empty root.
    yield (node.module or "").split(".")[0]


def _positions_that_are_not_figures(tree: ast.AST) -> frozenset[int]:
    """Numeric literals that describe position or precision rather than value.

    Identified by the node they sit under rather than by their own value, which
    is the only way to tell ``f0.iloc[3]`` from a claim that something is three.
    """
    exempt: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript):
            _mark(node.slice, exempt)
        elif isinstance(node, ast.Call):
            func = node.func
            named = (
                func.id
                if isinstance(func, ast.Name)
                else func.attr
                if isinstance(func, ast.Attribute)
                else ""
            )
            if named in COUNT_METHODS:
                for argument in node.args:
                    _mark(argument, exempt)
                for keyword in node.keywords:
                    _mark(keyword.value, exempt)
    return frozenset(exempt)


def _mark(node: ast.AST, exempt: set[int]) -> None:
    """Exempt the literals that are *positions*, and only those.

    The distinction is load-bearing and the first version got it wrong: it
    exempted every constant anywhere under a subscript, which quietly waved
    ``f0[f0['roe'] > 0.05]`` through. That is not an index — it is a threshold
    on a market figure wearing brackets, and it is the most natural way a model
    would write one. So the walk stops at anything that is not a position: an
    index, a slice bound, or a tuple of them. A comparison, a call or a piece of
    arithmetic inside the brackets is read exactly as it would be anywhere else.
    """
    if isinstance(node, ast.Constant):
        exempt.add(id(node))
        return
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        _mark(node.operand, exempt)
        return
    if isinstance(node, ast.Slice):
        for part in (node.lower, node.upper, node.step):
            if part is not None:
                _mark(part, exempt)
        return
    if isinstance(node, (ast.Tuple, ast.List)):
        for element in node.elts:
            _mark(element, exempt)


def first_code(violations: Sequence[Violation]) -> str:
    """The name the tool answers with when a calculation is refused."""
    return violations[0].code if violations else ""


__all__ = [
    "ESCAPE_ATTRIBUTES",
    "ALLOWED_MODULES",
    "COERCIONS",
    "COUNT_METHODS",
    "FORBIDDEN_IMPORT",
    "FORBIDDEN_NAME",
    "FORBIDDEN_NAMES",
    "LITERAL_NUMBER",
    "MAX_CODE_CHARS",
    "NO_RESULT",
    "PURE_CONVERSIONS",
    "RESULT_NAME",
    "STRUCTURAL_NUMBERS",
    "SYNTAX_ERROR",
    "Violation",
    "first_code",
    "validate",
]
