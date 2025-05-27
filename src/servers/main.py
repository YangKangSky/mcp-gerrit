"""Main FastMCP server setup for Gerrit integration (单服务兼容写法)."""

import logging
from servers.gerrit_service import gerrit_mcp

logger = logging.getLogger("mcp-gerrit.server.main")

def run_server(transport="stdio"):
    logger.info("Starting Gerrit MCP server (main entry point)")
    gerrit_mcp.run(transport=transport)

if __name__ == "__main__":
    run_server() 