"""MCP discovery moves deployment evidence without moving the core fixture pin."""

from __future__ import annotations

import json
import sys
from datetime import date

import pytest

from src.agent.mcp.registry import MCPRegistry
from src.agent.tools.catalog import ToolCatalog, ToolContext, ToolSpec
from src.core.config import Settings


SERVER = """
from mcp.server import MCPServer

server = MCPServer(name="fixture", version="1.0")

@server.tool(name={tool_name!r}, structured_output=True)
def exposed(value: int) -> dict[str, int]:
    return {{"value": value}}

if __name__ == "__main__":
    server.run()
"""


async def core(_context, _arguments):
    return {"ok": True}


def core_spec():
    return ToolSpec(
        name="core",
        description="Stable internal tool.",
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
        callable=core,
    )


async def registry_for(tmp_path, server_name: str, tool_name: str) -> MCPRegistry:
    script = tmp_path / f"{server_name}.py"
    script.write_text(SERVER.format(tool_name=tool_name))
    settings = Settings(
        mcp_enabled=True,
        mcp_servers=json.dumps(
            {
                server_name: {
                    "transport": "stdio",
                    "command": sys.executable,
                    "args": [str(script)],
                }
            }
        ),
    )
    registry = MCPRegistry(settings=settings)
    await registry.start()
    return registry


@pytest.mark.asyncio
async def test_discovery_wraps_a_real_stdio_server_and_versions_it_separately(tmp_path):
    first = await registry_for(tmp_path, "fixture_one", "echo")
    second = await registry_for(tmp_path, "fixture_two", "double")
    try:
        first_tools = first.registrations()
        second_tools = second.registrations()
        assert [tool.name for tool in first_tools] == ["mcp__fixture_one__echo"]

        core_only = ToolCatalog((core_spec(),), trace_writer=lambda _trace: None)
        with_first = ToolCatalog(
            (core_spec(), *first_tools),
            trace_writer=lambda _trace: None,
            mcp_servers_version=first.version,
        )

        assert with_first.tool_catalog_version == core_only.tool_catalog_version
        assert first.version != second.version
        assert with_first.mcp_servers_version == first.version

        result = await with_first.dispatch(
            "mcp__fixture_one__echo",
            {"value": 7},
            ToolContext(user_id=1, trading_day=date(2026, 8, 17)),
        )
        claim = result["external_claim"]
        assert claim["claim_class"] == "external_claim"
        assert claim["source"] == "MCP:fixture_one"
        assert claim["data"] == {"value": 7}
    finally:
        await first.close()
        await second.close()
