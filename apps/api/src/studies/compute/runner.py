"""Spawning the calculation, and translating however it ended into one answer.

The sandbox is a separate process for one reason: nothing else stops a
calculation that never returns. A thread cannot be killed, an ``exec`` in this
process shares this process's memory and file descriptors, and a signal-based
timeout inside the interpreter is a suggestion a tight numpy loop never reads.
A child can be given a CPU ceiling by the kernel and killed by the clock.

Every exit path is turned into a named failure here rather than an exception,
because every one of them is something the model can act on: a calculation that
took too long should be narrower, one that ran out of memory should read fewer
rows, one that raised should fix the column name it got wrong.

``preexec_fn`` is deliberately not used to apply the limits, even though it is
the obvious place. This runs inside a worker thread of a threaded server, and
``preexec_fn`` between ``fork`` and ``exec`` in a multi-threaded process can
deadlock on a lock some other thread happened to hold. The child sets its own
ceilings instead, first thing, before it imports anything.
"""

from __future__ import annotations

import json
import signal
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

#: How many CPU seconds one calculation may spend. Five, because the measured
#: shapes — a pivot of ten symbols across thirty-four quarters, a rolling mean
#: over two hundred and fifty sessions — finish inside two orders of magnitude
#: of that, and anything that does not is a loop rather than a calculation.
CPU_SECONDS = 5

#: How long the parent waits before killing the child. Above the CPU ceiling so
#: that a calculation which burned its CPU dies as ``compute_timeout`` from the
#: kernel's signal rather than from this clock — and this clock still catches the
#: case the kernel cannot, a child asleep on something that costs no CPU.
WALL_SECONDS = CPU_SECONDS + 3

#: The address space one calculation may hold, on the platforms that enforce it.
#: Measured rather than guessed: this project's own image reports 195 MB of
#: address space with pandas and numpy imported, so this leaves roughly three
#: hundred megabytes for the numbers — comfortably above the largest frame the
#: ceilings below allow, and far under any container this runs in.
MEMORY_BYTES = 512 * 1024 * 1024

#: How large a calculation's answer may be. A picture, not a dataset: past five
#: hundred rows nobody reads the table, and past twelve columns nobody reads the
#: row. The refusal names both numbers so the next attempt is narrower rather
#: than another guess.
MAX_RESULT_ROWS = 500
MAX_RESULT_COLUMNS = 12

#: How much the child may write before the parent stops believing it. Two
#: megabytes is an order of magnitude above the largest answer the ceilings
#: above allow, so anything past it is a child that has stopped speaking the
#: protocol.
MAX_OUTPUT_CHARS = 2_000_000

TIMEOUT = "compute_timeout"
MEMORY_EXCEEDED = "compute_memory_exceeded"
RUNTIME_ERROR = "compute_runtime_error"
RESULT_TOO_LARGE = "compute_result_too_large"

WORKER = Path(__file__).with_name("worker.py")


def run(
    *,
    code: str,
    frames: Sequence[Mapping[str, Any]],
    constants: Mapping[str, Any] | None = None,
    output_kind: str | None = None,
    cpu_seconds: int = CPU_SECONDS,
    wall_seconds: int = WALL_SECONDS,
    memory_bytes: int = MEMORY_BYTES,
    max_rows: int = MAX_RESULT_ROWS,
    max_columns: int = MAX_RESULT_COLUMNS,
) -> Mapping[str, Any]:
    """Run one calculation and hand back either a frame payload or a named failure.

    ``frames`` are payloads, not :class:`Frame` objects: the child is a plain
    Python process that knows nothing about this project's types, and handing it
    anything richer than JSON would be handing it an import.

    ``max_rows`` and ``max_columns`` default to the ceilings a *model's*
    calculation answers to and are arguments because a template's may honestly
    be wider: a heatmap of one session's seventeen quarter hours is eighteen
    columns and is still one picture. They bound the shape of an answer, never
    what may be written to produce it — the literal rule is the validator's and
    a template has no allowance there.
    """
    request = {
        "code": code,
        "frames": [
            {
                "columns": list(frame.get("columns") or []),
                "rows": [list(row) for row in (frame.get("rows") or [])],
            }
            for frame in frames
        ],
        "constants": dict(constants or {}),
        "output_kind": output_kind,
        "limits": {
            "cpu_seconds": cpu_seconds,
            "memory_bytes": memory_bytes,
            "max_rows": max_rows,
            "max_columns": max_columns,
        },
    }

    # A directory of its own, and an empty environment. The first is so a
    # calculation that somehow writes has nowhere shared to write to; the second
    # is so nothing this deployment holds in its environment — a database URL, a
    # provider key — is readable from inside one.
    with tempfile.TemporaryDirectory(prefix="compute-") as workspace:
        try:
            finished = subprocess.run(
                [sys.executable, "-I", "-B", str(WORKER)],
                input=json.dumps(request, ensure_ascii=False, default=str),
                capture_output=True,
                text=True,
                timeout=wall_seconds,
                cwd=workspace,
                env={"PATH": "", "HOME": workspace, "TMPDIR": workspace},
                check=False,
            )
        except subprocess.TimeoutExpired:
            return _failed(
                TIMEOUT,
                f"phép tính chạy quá {wall_seconds} giây và đã bị dừng; "
                "thu hẹp bảng hoặc bỏ vòng lặp.",
            )

    if finished.returncode != 0:
        return _from_exit(finished.returncode, finished.stderr)
    if len(finished.stdout) > MAX_OUTPUT_CHARS:
        return _failed(
            RESULT_TOO_LARGE,
            "kết quả lớn hơn mức một bảng có thể mang; thu gọn bằng .tail().",
        )
    try:
        return json.loads(finished.stdout)
    except (ValueError, TypeError):
        return _failed(RUNTIME_ERROR, _tail(finished.stderr) or "phép tính không trả lời.")


def _from_exit(returncode: int, stderr: str) -> Mapping[str, Any]:
    """What a non-zero exit meant, in the vocabulary the model reads.

    A negative code is a signal, and the two that matter are the two ceilings:
    ``SIGXCPU`` is the CPU limit firing and ``SIGKILL`` is what an out-of-memory
    kill looks like from here. Everything else is the child failing at something
    it was not asked about, which is this system's problem and not the model's —
    so it is reported as a runtime error with whatever the child said.
    """
    if returncode in (-signal.SIGXCPU, -signal.SIGALRM):
        return _failed(
            TIMEOUT,
            f"phép tính dùng quá {CPU_SECONDS} giây tính toán và đã bị dừng.",
        )
    if returncode == -signal.SIGKILL:
        return _failed(
            MEMORY_EXCEEDED,
            "phép tính xin nhiều bộ nhớ hơn mức cho phép; đọc ít hàng hơn.",
        )
    if "MemoryError" in stderr:
        return _failed(
            MEMORY_EXCEEDED,
            "phép tính xin nhiều bộ nhớ hơn mức cho phép; đọc ít hàng hơn.",
        )
    return _failed(RUNTIME_ERROR, _tail(stderr) or f"phép tính dừng với mã {returncode}.")


def _tail(stderr: str) -> str:
    """The last thing the child said, without telling anyone where it lives."""
    lines = [line.strip() for line in (stderr or "").splitlines() if line.strip()]
    kept = [line for line in lines if not line.startswith("File ")]
    return " / ".join(kept[-3:])[:400]


def _failed(code: str, detail: str) -> Mapping[str, Any]:
    return {"ok": False, "error": code, "detail": detail}


__all__ = [
    "CPU_SECONDS",
    "MAX_OUTPUT_CHARS",
    "MAX_RESULT_COLUMNS",
    "MAX_RESULT_ROWS",
    "MEMORY_BYTES",
    "MEMORY_EXCEEDED",
    "RESULT_TOO_LARGE",
    "RUNTIME_ERROR",
    "TIMEOUT",
    "WALL_SECONDS",
    "WORKER",
    "run",
]
