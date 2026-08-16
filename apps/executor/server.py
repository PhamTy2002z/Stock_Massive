"""Networkless JSON file-queue worker for bounded derived calculations."""

from __future__ import annotations

import json
import os
import selectors
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

QUEUE = Path(os.environ.get("EXECUTOR_QUEUE_DIR", "/queue"))
POLL_SECONDS = 0.02
MAX_OUTPUT_BYTES = 64 * 1024
MAX_CAPTURE_CHARS = 16 * 1024

RUNNER = r'''
import contextlib
import io
import json
import sys
import traceback

request = json.loads(sys.stdin.read())
namespace = {"inputs": request["inputs"]}
capture = io.StringIO()
try:
    with contextlib.redirect_stdout(capture):
        exec(compile(request["code"], "<agent-computation>", "exec"), namespace, namespace)
    if "result" not in namespace:
        raise ValueError("code must assign a JSON-serializable value to `result`")
    payload = {
        "ok": True,
        "result": namespace["result"],
        "stdout": capture.getvalue()[:16384],
    }
except BaseException as exc:
    payload = {
        "ok": False,
        "error": f"{type(exc).__name__}: {exc}",
        "stdout": capture.getvalue()[:16384],
    }
try:
    encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False)
except (TypeError, ValueError) as exc:
    encoded = json.dumps({"ok": False, "error": f"result is not JSON-serializable: {exc}"})
sys.stdout.write(encoded)
'''


def _bounded_child(request: dict[str, Any]) -> dict[str, Any]:
    timeout = min(10.0, max(0.1, float(request.get("timeout_seconds", 10.0))))
    payload = json.dumps(
        {"code": str(request["code"]), "inputs": request["inputs"]},
        ensure_ascii=False,
    ).encode("utf-8")
    with tempfile.TemporaryDirectory(dir="/tmp") as working_directory:
        process = subprocess.Popen(
            [sys.executable, "-I", "-S", "-c", RUNNER],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=working_directory,
            env={},
        )
        assert process.stdin is not None
        assert process.stdout is not None
        process.stdin.write(payload)
        process.stdin.close()
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        output = bytearray()
        deadline = time.monotonic() + timeout
        while process.poll() is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                process.kill()
                process.wait()
                return {"ok": False, "error": "execution exceeded the wall-clock limit"}
            if selector.select(timeout=min(remaining, 0.1)):
                chunk = os.read(process.stdout.fileno(), 4096)
                output.extend(chunk)
                if len(output) > MAX_OUTPUT_BYTES:
                    process.kill()
                    process.wait()
                    return {"ok": False, "error": "execution exceeded the output limit"}
        output.extend(process.stdout.read(MAX_OUTPUT_BYTES + 1))
        if len(output) > MAX_OUTPUT_BYTES:
            return {"ok": False, "error": "execution exceeded the output limit"}
    try:
        child = json.loads(output.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"ok": False, "error": "executor child returned invalid JSON"}
    if not isinstance(child, dict) or child.get("ok") is not True:
        return {
            "ok": False,
            "error": str(child.get("error", "execution failed")) if isinstance(child, dict) else "execution failed",
        }
    return {
        "ok": True,
        "derived": {
            "source": "isolated_python",
            "as_of": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "claim_class": "derived",
            "result": child["result"],
            "stdout": str(child.get("stdout", ""))[:MAX_CAPTURE_CHARS],
        },
    }


def _write_response(request_path: Path, response: dict[str, Any]) -> None:
    response_path = request_path.with_name(request_path.name.replace(".request.json", ".response.json"))
    temporary = response_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(response, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, response_path)


def main() -> None:
    QUEUE.mkdir(parents=True, exist_ok=True)
    while True:
        for request_path in sorted(QUEUE.glob("*.request.json")):
            try:
                request = json.loads(request_path.read_text(encoding="utf-8"))
                if not isinstance(request, dict):
                    raise ValueError("request must be a JSON object")
                response = _bounded_child(request)
            except Exception as exc:
                response = {"ok": False, "error": f"invalid request: {exc}"}
            _write_response(request_path, response)
            request_path.unlink(missing_ok=True)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
