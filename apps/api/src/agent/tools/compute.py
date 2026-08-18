"""JSON-only client for the networkless, file-queue Python executor."""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.core.config import Settings, get_settings

from .catalog import ToolContext, ToolDataAccess, ToolSpec
from .data import _object_schema

MAX_CODE_CHARS = 8_000
MAX_INPUT_BYTES = 16 * 1024
POLL_SECONDS = 0.02


class ExecutorUnavailable(RuntimeError):
    """The isolated executor did not produce a bounded response."""


class ExecutorClient:
    """Exchange one atomic JSON request and response through the named volume."""

    def __init__(self, *, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.queue = Path(self.settings.executor_queue_dir)

    async def run(self, code: str, inputs: Mapping[str, Any]) -> Mapping[str, Any]:
        return await asyncio.to_thread(self._run, code, dict(inputs))

    def _run(self, code: str, inputs: Mapping[str, Any]) -> Mapping[str, Any]:
        if not code.strip() or len(code) > MAX_CODE_CHARS:
            raise ValueError(f"code must be between 1 and {MAX_CODE_CHARS} characters")
        serialized_inputs = json.dumps(inputs, ensure_ascii=False, allow_nan=False)
        if len(serialized_inputs.encode("utf-8")) > MAX_INPUT_BYTES:
            raise ValueError("inputs exceed the executor's JSON limit")
        self.queue.mkdir(parents=True, exist_ok=True)
        os.chmod(self.queue, 0o777)
        job_id = uuid.uuid4().hex
        request = self.queue / f"{job_id}.request.json"
        response = self.queue / f"{job_id}.response.json"
        temporary = self.queue / f"{job_id}.request.tmp"
        payload = {
            "version": 1,
            "code": code,
            "inputs": dict(inputs),
            "timeout_seconds": min(10.0, self.settings.executor_timeout_seconds),
        }
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, allow_nan=False), encoding="utf-8"
        )
        os.replace(temporary, request)
        deadline = time.monotonic() + self.settings.executor_timeout_seconds + 2.0
        try:
            while time.monotonic() < deadline:
                if response.exists():
                    result = json.loads(response.read_text(encoding="utf-8"))
                    if not isinstance(result, Mapping):
                        raise ExecutorUnavailable("the executor returned non-object JSON")
                    if result.get("ok") is not True:
                        raise ExecutorUnavailable(str(result.get("error") or "execution failed"))
                    derived = result.get("derived")
                    if not isinstance(derived, Mapping):
                        raise ExecutorUnavailable("the executor returned no derived result")
                    return {"derived": dict(derived)}
                time.sleep(POLL_SECONDS)
            raise ExecutorUnavailable("the executor did not answer before its deadline")
        finally:
            request.unlink(missing_ok=True)
            response.unlink(missing_ok=True)
            temporary.unlink(missing_ok=True)


class ComputeTools:
    """Expose bounded execution while keeping its output below registered evidence."""

    def __init__(self, *, client: ExecutorClient | None = None) -> None:
        self._client = client or ExecutorClient()

    def registrations(self) -> tuple[ToolSpec, ...]:
        return (
            ToolSpec(
                name="run_python",
                description=(
                    "Run bounded Python arithmetic over explicit JSON inputs in a "
                    "networkless container. Assign the JSON-serializable answer to "
                    "`result`. Output is derived evidence, not a registered signal."
                ),
                parameters=_object_schema(
                    {
                        "code": {"type": "string", "minLength": 1, "maxLength": MAX_CODE_CHARS},
                        "inputs": {"type": "object"},
                    },
                    ("code", "inputs"),
                ),
                callable=self.run_python,
                data_access=ToolDataAccess.EXTERNAL,
            ),
        )

    async def run_python(
        self, _context: ToolContext, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        inputs = arguments.get("inputs")
        if not isinstance(inputs, Mapping):
            raise ValueError("inputs must be a JSON object")
        return await self._client.run(str(arguments["code"]), inputs)


__all__ = ["ComputeTools", "ExecutorClient", "ExecutorUnavailable"]
