"""Configured MCP discovery and lifecycle."""

from .registry import (
    MCPRegistry,
    close_mcp_registry,
    initialize_mcp_registry,
    mcp_registry,
)

__all__ = [
    "MCPRegistry",
    "close_mcp_registry",
    "initialize_mcp_registry",
    "mcp_registry",
]
