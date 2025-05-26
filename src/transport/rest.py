# REST Transport: FastMCP服务启动入口

import os
from src.utils.logger import logger
from mcp.server.fastmcp import FastMCP, Context
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Optional, Dict, Any
from src.core.gerrit_service import GerritService

# Load environment variables
load_dotenv()

@dataclass
class GerritContext:
    host: str
    user: str
    http_password: Optional[str] = None

@asynccontextmanager
async def gerrit_lifespan(server: FastMCP) -> AsyncIterator[GerritContext]:
    host = os.getenv("GERRIT_HOST", "")
    user = os.getenv("GERRIT_USER", "")
    http_password = os.getenv("GERRIT_HTTP_PASSWORD", "")
    if host and host.endswith("/"):
        host = host[:-1]
        logger.info(f"Removed trailing slash from GERRIT_HOST: {host}")
    if not all([host, user]):
        logger.error("Missing required environment variables:")
        if not host: logger.error("- GERRIT_HOST not set")
        if not user: logger.error("- GERRIT_USER not set")
        raise ValueError(
            "Missing required environment variables: GERRIT_HOST, GERRIT_USER. "
            "Please set these in your environment or .env file."
        )
    if not http_password:
        logger.warning("GERRIT_HTTP_PASSWORD not set - REST API calls will fail")
    ctx = GerritContext(host=host, user=user, http_password=http_password)
    try:
        yield ctx
    finally:
        pass

gerrit_service = GerritService()

mcp = FastMCP(
    "Gerrit Review",
    description="MCP server for reviewing Gerrit changes. Set GERRIT_HOST with protocol prefix (http:// or https://)",
    lifespan=gerrit_lifespan,
    dependencies=["python-dotenv", "requests"]
)

@mcp.tool()
def fetch_gerrit_change(ctx: Context, change_id: str, patchset_number: str = None) -> Dict[str, Any]:
    return gerrit_service.fetch_change(ctx, change_id, patchset_number)

@mcp.tool()
def fetch_patchset_diff(ctx: Context, change_id: str, base_patchset: str, target_patchset: str, file_path: Optional[str] = None) -> Dict[str, Any]:
    return gerrit_service.fetch_patchset_diff(ctx, change_id, base_patchset, target_patchset, file_path)

def run_server():
    """Run the MCP server."""
    try:
        logger.info("Starting Gerrit Review MCP server")
        mcp.run(transport='stdio')
    except Exception as e:
        logger.error(f"Failed to start MCP server: {str(e)}")
        raise 