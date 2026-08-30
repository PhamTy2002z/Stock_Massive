"""The process a calculation actually runs in. Imports nothing from this project.

Run as a script by ``runner.py`` — ``python -I -B worker.py`` — reading one JSON
request on stdin and writing one JSON response on stdout. It is a file rather
than a ``-c`` string so a traceback has a real line to point at, and it imports
nothing from ``src`` so that nothing this deployment knows how to reach can be
reached from inside a calculation: no session, no settings, no provider client.

Three things happen before the model's code is given control, and the order
matters.

**The ceilings go on.** CPU seconds and address space, so a loop that never ends
and an allocation that never fits both die as themselves rather than as a
request that hung. Address space is a Linux ceiling: macOS refuses
``RLIMIT_AS`` outright, so on a developer's machine the wall clock is the only
floor and the response says which limits were actually applied.

**The network is taken away.** The validator already refuses ``import socket``,
but ``pandas`` is in the namespace and pandas can be asked to read a URL. So the
socket module's constructors are replaced before user code runs, and the refusal
is an ``OSError`` the model reads rather than a request that quietly succeeds.

**Stdout is moved.** This process talks to its parent in JSON on stdout, so user
code printing anything at all would corrupt the protocol. Rather than refusing
``print`` and hoping nothing else writes, the real stdout is kept aside and
``sys.stdout`` is pointed at a buffer that is thrown away.

**The escape hatches are taken off the modules themselves.** This is the one
that is load-bearing, and it exists because the layer above it cannot be. The
validator reasons about *imports*; ``pandas`` and ``numpy`` hand out real module
objects as plain attributes — ``pd.io.common.os`` **is** ``sys.modules['os']``,
``np.ctypeslib.ctypes`` is the real ``ctypes`` — so a calculation reaches
``os.popen`` without ever writing the word ``import``. It was measured doing
exactly that: arbitrary commands and ``/etc/passwd``, with the validator
reporting zero violations.

Attribute reachability of a module singleton is unbounded, so the answer is not
a longer list of refused names. It is that there is exactly *one* ``os`` object
in this process, so taking the dangerous callables off it closes every path that
reaches it at once — the one written, the one nobody has found yet, and the one
a future pandas release adds. Privileges are dropped on top of that, so what is
left to reach is reached as nobody.
"""

from __future__ import annotations

import io
import json
import math
import os
import resource
import statistics
import sys
import traceback
from datetime import date, datetime
from decimal import Decimal

#: The two builtins this file needs *after* it has taken them away from everyone.
#:
#: Bound at import, before :func:`_close_the_escape_hatches` runs, because that
#: function replaces ``builtins.exec`` and ``builtins.compile`` on the module —
#: which is the point, and which would otherwise stop this process from running
#: the calculation it was started for. A name looked up at call time would find
#: the refusal; a reference taken now is the real one, and it is held by nothing
#: user code can name.
_EXEC = exec
_COMPILE = compile

#: Where user code says what it computed. The name is the contract; the
#: validator refuses code that never assigns it.
RESULT_NAME = "result"

#: The keys a calculation may set on ``result.attrs`` to say what its numbers
#: *mean*. Meaning and not colour: a calculation says a quarter is the winner and
#: the browser decides what winning looks like in the reader's theme. This is the
#: whole mechanism by which a comparison computed here reaches a chart as a
#: comparison rather than as two anonymous columns.
ROLE_ATTRS: tuple[str, ...] = (
    "column_roles",
    "point_roles",
    "cell_roles",
    "labels",
    "unit",
)

#: The modules a calculation may import, held equal to the validator's own list
#: by ``tests/studies/test_compute_runner.py``. Written out here rather than
#: imported because this file imports nothing from this project — that is the
#: boundary the sandbox is — and a process boundary is the one place a duplicated
#: constant is cheaper than the import that would remove it.
ALLOWED_MODULES: frozenset[str] = frozenset(
    {"pandas", "numpy", "math", "statistics", "datetime"}
)

#: What the sandbox's builtins are. Everything a table calculation needs and
#: nothing that opens or evaluates. ``print`` is absent on purpose: stdout is the
#: protocol. ``__import__`` is present but guarded, because the validator allows
#: five modules and a calculation that may write ``import math`` has to be able
#: to run it.
SAFE_BUILTIN_NAMES: tuple[str, ...] = (
    "abs",
    "all",
    "any",
    "bool",
    "dict",
    "divmod",
    "enumerate",
    "filter",
    "float",
    "frozenset",
    "int",
    "len",
    "list",
    "map",
    "max",
    "min",
    "pow",
    "range",
    "reversed",
    "round",
    "set",
    "slice",
    "sorted",
    "str",
    "sum",
    "tuple",
    "zip",
    "ArithmeticError",
    "Exception",
    "KeyError",
    "TypeError",
    "ValueError",
    "ZeroDivisionError",
    "True",
    "False",
    "None",
)


#: The calls that let code do something other than arithmetic, by the module
#: that owns them.
#:
#: Grouped by *capability* rather than by convenience, because the grouping is
#: the argument that this is complete for what it covers. Everything dangerous a
#: calculation could want needs one of: starting a process, opening a file,
#: loading native code, reaching an object it was not handed, or turning bytes
#: back into calls. Close those five at the object that owns them and every
#: client of them closes too — ``gzip``, ``tarfile``, ``zipfile``, ``tempfile``,
#: ``codecs`` and ``shutil`` all reach the disk through ``open``, so none of them
#: needs a line here. The sixth, the network, is closed by
#: :func:`_close_the_network` for a reason of its own.
#:
#: ``os`` and ``posix`` are listed separately and given the same list because
#: ``os.open`` and ``posix.open`` are two names for one function held on two
#: module objects: replacing one leaves the other, and ``posix`` is reachable —
#: measured, at ``pd._testing._io.tarfile.shutil.posix``.
#:
#: Opening a file is **not** here, and neither is ``builtins.exec``. Both were
#: measured breaking honest arithmetic: pandas and numpy import lazily — ``np.rec``
#: is fetched the first time a calculation calls ``pct_change``, ``describe``,
#: ``rank`` or ``groupby`` — and an import runs a module body with ``exec`` after
#: reading it with ``_io.open`` and ``_io.open_code``. Closing those closes the
#: library this sandbox exists to run. So file access is *narrowed* instead, by
#: :data:`_SOURCE_ONLY`, and ``exec`` is left alone because everything it can
#: reach is in this table.
_FILE_CALLS = ("fdopen", "openpty", "pipe", "pipe2", "dup", "dup2",
               "read", "write", "pread", "pwrite", "sendfile", "truncate",
               "ftruncate", "remove", "unlink", "rmdir", "removedirs", "rename",
               "renames", "replace", "mkdir", "makedirs", "link", "symlink",
               "chmod", "chown", "chdir", "chroot")

_SPAWN_CALLS = ("system", "popen", "fork", "forkpty", "posix_spawn",
                "posix_spawnp", "spawnv", "spawnve", "spawnvp", "spawnvpe",
                "spawnl", "spawnle", "spawnlp", "spawnlpe", "execv", "execve",
                "execvp", "execvpe", "execl", "execle", "execlp", "execlpe",
                "kill", "killpg", "putenv", "unsetenv", "startfile")

ESCAPE_HATCHES: tuple[tuple[str, tuple[str, ...]], ...] = (
    # Starting a process, and opening a file descriptor.
    ("os", _SPAWN_CALLS + _FILE_CALLS),
    ("posix", _SPAWN_CALLS + _FILE_CALLS),
    ("nt", _SPAWN_CALLS + _FILE_CALLS),
    (
        "subprocess",
        ("Popen", "run", "call", "check_call", "check_output",
         "getoutput", "getstatusoutput"),
    ),
    # Opening a file is narrowed rather than closed — see _SOURCE_ONLY.
    ("builtins", ("input", "breakpoint")),
    # Loading native code, which is a way to have any of the above back.
    (
        "ctypes",
        ("CDLL", "PyDLL", "WinDLL", "OleDLL", "cdll", "pydll", "windll",
         "oledll", "cast", "memmove", "memset", "string_at", "wstring_at"),
    ),
    # Reaching an object this calculation was not handed. A frame carries
    # ``f_builtins`` — the real ones, not the reduced mapping user code is given
    # — and ``gc`` will simply hand over every object in the process.
    ("sys", ("_getframe", "settrace", "setprofile")),
    ("gc", ("get_objects", "get_referrers", "get_referents")),
    # Turning bytes back into calls. ``pickle`` runs whatever ``__reduce__``
    # names, which is a call this file never sees written down.
    #
    # ``marshal`` is deliberately absent beside it, and measured: the import
    # system reads every ``.pyc`` through ``marshal.loads``, so closing it closes
    # the library. It is also the weaker of the two — what comes back is a code
    # object, which is inert until something runs it, and everything that could
    # is in this table.
    ("pickle", ("load", "loads", "Unpickler")),
)

#: The calls that open a file, and the modules that hold them.
#:
#: Narrowed rather than closed, because the import system is a legitimate file
#: reader and it has to keep working: every one of these is how CPython reads a
#: module off disk. What they are narrowed *to* is the whole of that purpose —
#: a path that is Python source or bytecode. ``/etc/passwd`` is not a module, and
#: neither is the process environment of PID 1, which is the file that made the
#: escape worth writing.
#:
#: What stays reachable through them is Python code sitting on this machine's
#: disk, which is not a secret. What stops being reachable is every file that is.
_SOURCE_ONLY: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("builtins", ("open",)),
    ("io", ("open", "open_code", "FileIO")),
    ("_io", ("open", "open_code", "FileIO")),
    ("os", ("open",)),
    ("posix", ("open",)),
    ("nt", ("open",)),
)

#: What a narrowed opener will still open. A suffix is the whole test, because
#: reading a module is the whole purpose.
_SOURCE_SUFFIXES = (".py", ".pyc", ".pyo", ".pyd", ".so", ".dylib")


#: Modules that may not be imported, however the import is spelled.
#:
#: A denylist, and it is the right shape here where it would be the wrong shape
#: above, because of what these have in common: each is a *capability* rather
#: than a library, and each may not be loaded yet. That second half is the whole
#: reason this list exists. A module already in ``sys.modules`` is covered by the
#: table above, which replaced its calls on the one object everything shares; a
#: module not yet loaded has no object to replace, so importing it would hand
#: back a fresh one with every call intact.
#:
#: Which is why ``posix``, ``_io``, ``_thread``, ``signal`` and ``resource`` are
#: **not** here despite being capabilities: the interpreter loads all five before
#: this process reads its first line, so the table above already holds them —
#: and denying them breaks honest work, measured. ``numpy.rec`` imports ``_io``
#: on the first ``pct_change`` of a Turn.
IMPORT_DENYLIST: frozenset[str] = frozenset(
    {
        "_posixsubprocess",
        "_socket",
        "_ssl",
        "socket",
        "ctypes",
        "_ctypes",
        "subprocess",
        "multiprocessing",
        "_multiprocessing",
        "pty",
        "fcntl",
        "termios",
        "mmap",
    }
)

#: What a calculation is told when it reaches one of them. A sentence rather
#: than an ``AttributeError``, because the model reads this, and a message about
#: a missing attribute is one it will try to work around.
BLOCKED_MESSAGE = "một phép tính chỉ làm các phép trên bảng, không chạm hệ thống"


def _close_the_escape_hatches() -> None:
    """Take the dangerous calls off the module objects themselves.

    Not out of the sandbox's namespace — off the singletons. There is one ``os``
    module in this process, and ``pd.io.common.os``, ``np.ctypeslib.os`` and
    whatever path nobody has written down yet all name that same object.
    Replacing the callable closes them together; removing a name from the
    namespace closes none of them, which is what the measurement showed.

    Every refusal is a ``PermissionError``, which is an ``OSError``, which is
    what the standard library already catches where it probes for a file it may
    not have — so nothing on the way out of this process breaks on one.

    A module this build does not have is skipped rather than imported: a
    calculation cannot reach through something that is not installed.
    """

    def refused(*_args: object, **_kwargs: object) -> None:
        raise PermissionError(BLOCKED_MESSAGE)

    for name, attributes in ESCAPE_HATCHES:
        module = sys.modules.get(name)
        if module is None:
            continue
        for attribute in attributes:
            if hasattr(module, attribute):
                try:
                    setattr(module, attribute, refused)
                except Exception:  # pragma: no cover - a read-only module
                    pass


def _narrow_the_file_openers() -> None:
    """Let the import system read a module, and nothing read anything else.

    Every opener in :data:`_SOURCE_ONLY` keeps its real implementation behind a
    check on what it was asked to open. The check is a suffix, because the one
    caller that legitimately survives this is CPython loading a ``.py``, a
    ``.pyc`` or a shared object.

    The real callable is captured per name, so the several modules that hold the
    *same* function — ``builtins.open``, ``io.open`` and ``_io.open`` are one
    object under three names — each keep a working one behind their own guard.
    """
    for module_name, attributes in _SOURCE_ONLY:
        module = sys.modules.get(module_name)
        if module is None:
            continue
        for attribute in attributes:
            real = getattr(module, attribute, None)
            if real is None:
                continue

            def source_only(path, *args, _real=real, **kwargs):
                if not str(path).endswith(_SOURCE_SUFFIXES):
                    raise PermissionError(BLOCKED_MESSAGE)
                return _real(path, *args, **kwargs)

            try:
                setattr(module, attribute, source_only)
            except Exception:  # pragma: no cover - a read-only module
                pass


def _close_the_import_gate() -> None:
    """Refuse the raw capability modules, however the import is spelled.

    The third gate on imports, and the only one that holds against code this
    process never read. The validator refuses a module by reading the source,
    which is the gate that gives the model something it can act on; the
    sandbox's own ``__import__`` refuses anything outside five names, which
    holds for code that arrived through the namespace it was given. This one is
    on the *real* ``builtins.__import__`` and on ``importlib.import_module``, so
    it holds for an import written inside a string that something else ran.

    A denylist here rather than the five-name allowlist the sandbox uses,
    because this one also has to let pandas finish importing itself: ``np.rec``,
    ``dateutil`` and ``pytz`` are all fetched lazily, on the first calculation
    that needs them, long after this runs.
    """
    import builtins as _builtins
    import importlib as _importlib

    real_import = _builtins.__import__
    real_import_module = _importlib.import_module

    def refuse(name: str) -> None:
        if name.split(".")[0] in IMPORT_DENYLIST:
            raise PermissionError(BLOCKED_MESSAGE)

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        refuse(name)
        return real_import(name, globals, locals, fromlist, level)

    def guarded_import_module(name, package=None):
        refuse(name)
        return real_import_module(name, package)

    _builtins.__import__ = guarded_import
    _importlib.import_module = guarded_import_module


def _drop_privileges() -> bool:
    """Become nobody, when this process is somebody who could be.

    The container this runs in is root, so "reaches nothing this process could
    not reach" was true and was the problem rather than the reassurance. After
    this, what is left of the filesystem is read as an unprivileged user: PID 1's
    environment — where this deployment's database URL and provider key live —
    stops being readable, which is the leak that made the escape worth writing.

    Reported rather than assumed, like the ceilings: it needs privileges to give
    privileges away, so on a developer's machine it does nothing and says so.
    """
    if not hasattr(os, "setuid") or os.geteuid() != 0:
        return False
    target = 65534
    try:
        import pwd

        target = pwd.getpwnam("nobody").pw_uid
    except Exception:  # pragma: no cover - an image without the account
        pass
    try:
        os.setgroups([])
        os.setgid(target)
        os.setuid(target)
    except Exception:  # pragma: no cover - refused is the same as absent here
        return False
    return True


def main() -> int:
    request = json.load(sys.stdin)
    limits = request.get("limits") or {}
    applied = _apply_limits(limits)

    real_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        response = _run(request, applied)
    finally:
        sys.stdout = real_stdout

    response["limitsApplied"] = applied
    json.dump(response, real_stdout, ensure_ascii=False, default=str)
    real_stdout.write("\n")
    real_stdout.flush()
    return 0


def _apply_limits(limits: dict) -> list[str]:
    """Put the ceilings on, and say which ones this platform accepted.

    Reported rather than assumed. A memory ceiling that silently did not apply
    is the kind of protection a reader believes in until the day it matters, and
    the difference between Linux and macOS here is real.
    """
    applied: list[str] = []
    cpu_seconds = int(limits.get("cpu_seconds") or 0)
    if cpu_seconds > 0:
        try:
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
            applied.append("cpu")
        except (ValueError, OSError):  # pragma: no cover - platform dependent
            pass
    memory_bytes = int(limits.get("memory_bytes") or 0)
    if memory_bytes > 0:
        try:
            resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
            applied.append("memory")
        except (ValueError, OSError):
            # macOS has no working RLIMIT_AS. The wall clock in the parent is
            # then the only floor, which is why it exists there and not here.
            pass
    try:
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
        applied.append("files")
    except (ValueError, OSError):  # pragma: no cover - platform dependent
        pass
    return applied


def _close_the_network() -> None:
    """Make every outbound connection an error the model can read.

    ``socket.socket`` is replaced by a *class* rather than a function, because
    the standard library subclasses it and instantiates it by name; a function
    in its place fails somewhere further down with a message about types, which
    is a refusal the model cannot act on even though the connection was
    correctly never made.
    """
    import socket

    message = "một phép tính không đọc được ra ngoài"

    class _NoSocket:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            raise OSError(message)

    def refused(*_args: object, **_kwargs: object) -> None:
        raise OSError(message)

    socket.socket = _NoSocket  # type: ignore[assignment]
    socket.create_connection = refused  # type: ignore[assignment]
    socket.getaddrinfo = refused  # type: ignore[assignment]


def _run(request: dict, applied: list[str]) -> dict:
    try:
        import numpy as np
        import pandas as pd
    except Exception as exc:  # pragma: no cover - a broken install, not a bug here
        return _failed("compute_runtime_error", f"không nạp được thư viện: {exc}")

    # After the imports and before anything the model wrote. Both orders matter:
    # pandas has to load while this process can still read its own installation,
    # and nothing the model wrote may run before the hatches are shut.
    if _drop_privileges():
        applied.append("privileges")
    _close_the_network()
    _close_the_escape_hatches()
    _narrow_the_file_openers()
    _close_the_import_gate()

    limits = request.get("limits") or {}
    max_rows = int(limits.get("max_rows") or 500)
    max_columns = int(limits.get("max_columns") or 12)

    namespace: dict = {
        "__builtins__": _safe_builtins(),
        "pd": pd,
        "np": np,
        "math": math,
        "statistics": statistics,
    }
    for index, frame in enumerate(request.get("frames") or []):
        namespace[f"f{index}"] = pd.DataFrame(
            frame.get("rows") or [], columns=list(frame.get("columns") or [])
        )
    constants = dict(request.get("constants") or {})
    namespace["constants"] = constants
    # Bound by name as well as in the mapping. A calculation that has to write
    # ``constants["ceiling"]`` every time is a calculation whose declared
    # assumptions read as plumbing; bound directly they read as what they are.
    for name, value in constants.items():
        if name.isidentifier() and name not in namespace:
            namespace[name] = value

    try:
        _EXEC(_COMPILE(request.get("code") or "", "<compute>", "exec"), namespace)
    except MemoryError:
        return _failed(
            "compute_memory_exceeded",
            "phép tính xin nhiều bộ nhớ hơn mức cho phép; thu hẹp bảng lại.",
        )
    except BaseException as exc:  # noqa: BLE001 - a failure here is a result
        return _failed("compute_runtime_error", _where_it_broke(exc))

    answer = namespace.get(RESULT_NAME)
    if isinstance(answer, pd.Series):
        answer = answer.to_frame(name=answer.name or "value")
    if not isinstance(answer, pd.DataFrame):
        return _failed(
            "compute_no_result",
            "result phải là một bảng (DataFrame) hoặc một chuỗi số (Series); "
            f"nó đang là {type(answer).__name__}.",
        )

    attrs = dict(getattr(answer, "attrs", {}) or {})
    frame = _shaped(answer, pd, attrs)
    rows = len(frame["rows"])
    columns = len(frame["columns"])
    if rows > max_rows or columns > max_columns:
        return _failed(
            "compute_result_too_large",
            f"kết quả có {rows} hàng × {columns} cột, quá mức "
            f"{max_rows} × {max_columns}. Thu gọn bằng .tail() hoặc chọn ít cột hơn.",
        )
    requested_kind = request.get("output_kind")
    if requested_kind:
        frame["kind"] = str(requested_kind)
    return {"ok": True, "frame": frame}


def _safe_builtins() -> dict:
    source = __builtins__ if isinstance(__builtins__, dict) else vars(__builtins__)
    safe = {name: source[name] for name in SAFE_BUILTIN_NAMES if name in source}
    real_import = source["__import__"]

    def guarded(name, globals=None, locals=None, fromlist=(), level=0):
        """The second gate on imports, behind the validator's first one.

        Behind, and still here. The validator refuses a module by reading the
        code, which is the gate that gives the model a message it can act on;
        this one holds when the code reached this process some other way, and a
        defence only checked behind another defence is a defence nobody has
        watched work.
        """
        if level != 0 or name.split(".")[0] not in ALLOWED_MODULES:
            raise ImportError(f"{name!r} không nhập được trong một phép tính")
        return real_import(name, globals, locals, fromlist, level)

    safe["__import__"] = guarded
    return safe


def _shaped(answer, pd, attrs: dict) -> dict:
    """One DataFrame as the payload a Frame is built from.

    The index is turned into a column when it carries anything — a date, a
    symbol, a quarter — because a Frame is positional rows against named
    columns and has nowhere else to put it. A default counter index is dropped,
    since a column of 0,1,2 is not a fact about a company.
    """
    index = answer.index
    dated = isinstance(index, (pd.DatetimeIndex, pd.PeriodIndex))
    # A counter is any unnamed whole-number index, not only a ``RangeIndex``.
    # ``concat`` of two frames produces an unnamed Int64Index of duplicates, and
    # kept as a column that is a leading column of zeros where the reader
    # expected the first figure.
    counter = not index.name and (
        isinstance(index, pd.RangeIndex) or pd.api.types.is_integer_dtype(index)
    )
    if dated or not counter:
        answer = answer.reset_index()

    columns = [str(name) for name in answer.columns]
    rows = [
        [_plain(value) for value in record]
        for record in answer.itertuples(index=False, name=None)
    ]
    return {
        "kind": "series" if dated else "table",
        "columns": columns,
        "rows": rows,
        "unit": _text(attrs.get("unit")),
        "labels": {
            str(key): str(value)
            for key, value in (attrs.get("labels") or {}).items()
        },
        "columnRoles": {
            str(key): str(value)
            for key, value in (attrs.get("column_roles") or {}).items()
        },
        "pointRoles": [_text(role) for role in (attrs.get("point_roles") or [])],
        "cellRoles": [_cell_role(entry) for entry in (attrs.get("cell_roles") or [])],
    }


def _cell_role(entry) -> dict:
    """One cell's role, accepting the two spellings a calculation may write.

    A mapping is what the wire uses; a triple is what a calculation building them
    in a loop naturally produces. Both are read here rather than one being
    refused, because the refusal would be about spelling and would cost a round
    of the Turn.
    """
    if isinstance(entry, dict):
        return {
            "row": int(entry.get("row", -1)),
            "column": str(entry.get("column", "")),
            "role": str(entry.get("role", "")),
        }
    row, column, role = list(entry)[:3]
    return {"row": int(row), "column": str(column), "role": str(role)}


def _text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _plain(value):
    """One cell as JSON, with "missing" spelled the one way a Frame reads."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int,)):
        return int(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return _plain(value.item())
        except (ValueError, AttributeError):
            pass
    if value != value:  # NaT and every other self-unequal missing marker
        return None
    return str(value)


def _where_it_broke(exc: BaseException) -> str:
    """The last three lines of the traceback, with this machine left out of them.

    A model that reads ``KeyError: 'roe'`` fixes its column name on the next
    round; a model that reads a host path learns something about a filesystem it
    has no business knowing.
    """
    own = [
        entry
        for entry in traceback.extract_tb(exc.__traceback__)
        if entry.filename == "<compute>"
    ]
    lines = [
        part.strip()
        for chunk in (
            *traceback.format_list(own),
            *traceback.format_exception_only(type(exc), exc),
        )
        for part in chunk.rstrip().splitlines()
        if part.strip()
    ]
    return " / ".join(lines[-3:]) or f"{type(exc).__name__}: {exc}"


def _failed(code: str, detail: str) -> dict:
    return {"ok": False, "error": code, "detail": detail}


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess
    sys.exit(main())
