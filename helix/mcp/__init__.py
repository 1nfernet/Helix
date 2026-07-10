"""Helix as an MCP server — drive the deterministic compiler from any agent."""

from helix.mcp.server import build_response, serve

__all__ = ["serve", "build_response"]
