"""`python -m helix.mcp` — run the Helix MCP server over stdio."""

from helix.mcp.server import serve

if __name__ == "__main__":
    serve()
