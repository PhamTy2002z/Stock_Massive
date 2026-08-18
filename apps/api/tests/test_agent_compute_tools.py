from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

import pytest

from src.agent.tools.catalog import ToolContext
from src.agent.tools.compute import ComputeTools

CONTEXT = ToolContext(user_id=7, trading_day=date(2026, 8, 17))


class StubExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Mapping[str, Any]]] = []

    async def run(self, code: str, inputs: Mapping[str, Any]) -> Mapping[str, Any]:
        self.calls.append((code, inputs))
        return {
            "derived": {
                "source": "isolated_python",
                "as_of": "2026-08-17T00:00:00Z",
                "claim_class": "derived",
                "result": 42,
                "stdout": "",
            }
        }


@pytest.mark.asyncio
async def test_run_python_keeps_the_result_inside_a_derived_evidence_envelope():
    executor = StubExecutor()
    tools = ComputeTools(client=executor)  # type: ignore[arg-type]

    result = await tools.run_python(
        CONTEXT,
        {"code": "result = inputs['price'] * 2", "inputs": {"price": 21}},
    )

    assert executor.calls == [("result = inputs['price'] * 2", {"price": 21})]
    assert result["derived"]["claim_class"] == "derived"
    assert result["derived"]["result"] == 42


@pytest.mark.asyncio
async def test_run_python_requires_json_inputs_to_be_an_object():
    tools = ComputeTools(client=StubExecutor())  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="JSON object"):
        await tools.run_python(CONTEXT, {"code": "result = 1", "inputs": [1]})
