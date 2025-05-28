"""
Gerrit MCP Tool Registration & Implementation
- No GerritService class, direct tool registration and implementation
- Follows mcp-atlassian/servers/confluence.py style
"""

import os
from typing import Optional, Dict, Any
from dataclasses import dataclass
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP, Context
from utils.logger import logger
from data.gerrit_api import make_gerrit_rest_request
from urllib.parse import quote, urlparse

# Configuration and context
load_dotenv()

@dataclass
class GerritContext:
    host: str
    user: str
    http_password: Optional[str] = None

def get_gerrit_config() -> dict:
    return {
        "GERRIT_HOST": os.getenv("GERRIT_HOST", ""),
        "GERRIT_USER": os.getenv("GERRIT_USER", ""),
        "GERRIT_HTTP_PASSWORD": os.getenv("GERRIT_HTTP_PASSWORD", ""),
        "READ_ONLY_MODE": os.getenv("READ_ONLY_MODE", "false").lower() == "true",
        "ENABLED_TOOLS": os.getenv("ENABLED_TOOLS", None),
    }

def is_gerrit_auth_configured(config: dict) -> bool:
    return bool(config.get("GERRIT_HOST")) and bool(config.get("GERRIT_USER"))

@asynccontextmanager
async def gerrit_lifespan(server: FastMCP) -> AsyncIterator[GerritContext]:
    logger.info("Gerrit MCP server lifespan starting...")
    config = get_gerrit_config()
    host = config["GERRIT_HOST"]
    user = config["GERRIT_USER"]
    http_password = config["GERRIT_HTTP_PASSWORD"]
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
        logger.info("Gerrit MCP server lifespan shutting down.")

# MCP instance
gerrit_mcp = FastMCP(
    "Gerrit Review",
    description="MCP server for reviewing Gerrit changes. Set GERRIT_HOST with protocol prefix (http:// or https://)",
    lifespan=gerrit_lifespan,
    dependencies=["python-dotenv", "requests"]
)

@gerrit_mcp.tool()
def fetch_gerrit_change(
    ctx: Context,
    change_id: str,
    patchset_number: Optional[str] = None
) -> Dict[str, Any]:
    """
    [tags: read, gerrit]
    Fetch detailed information about a Gerrit change, including all revisions, files, and metadata.

    Args:
        ctx (Context): The MCP request context, including Gerrit credentials.
        change_id (str): The Gerrit change ID (e.g., '12345').
        patchset_number (Optional[str]): The patchset number to fetch (if None, fetches the current revision).

    Returns:
        Dict[str, Any]: A dictionary containing change info, project, revision, patchset, and file diffs.
    """
    logger.info(f"[Gerrit] fetch_gerrit_change called with change_id={change_id}, patchset_number={patchset_number}")
    change_endpoint = f"a/changes/{change_id}/detail?o=CURRENT_REVISION&o=CURRENT_COMMIT&o=MESSAGES&o=DETAILED_LABELS&o=DETAILED_ACCOUNTS&o=ALL_REVISIONS&o=ALL_COMMITS&o=ALL_FILES&o=COMMIT_FOOTERS"
    change_info = make_gerrit_rest_request(ctx, change_endpoint)
    if not change_info:
        logger.warning(f"[Gerrit] No change info found for change_id={change_id}")
        raise ValueError(f"Change {change_id} not found")
    project = change_info.get("project")
    if not project:
        logger.warning(f"[Gerrit] No project info in change {change_id}")
        raise ValueError("Project information not found in change")
    current_revision = change_info.get("current_revision")
    revisions = change_info.get("revisions", {})
    if patchset_number:
        target_revision = None
        for rev, rev_info in revisions.items():
            if str(rev_info.get("_number")) == str(patchset_number):
                target_revision = rev
                break
        if not target_revision:
            available_patchsets = sorted([str(info.get("_number")) for info in revisions.values()])
            logger.warning(f"[Gerrit] Patchset {patchset_number} not found for change_id={change_id}. Available: {available_patchsets}")
            raise ValueError(f"Patchset {patchset_number} not found. Available patchsets: {', '.join(available_patchsets)}")
    else:
        target_revision = current_revision
    if not target_revision or target_revision not in revisions:
        logger.warning(f"[Gerrit] Revision info not found for change_id={change_id}, target_revision={target_revision}")
        raise ValueError("Revision information not found")
    revision_info = revisions[target_revision]
    processed_files = []
    for file_path, file_info in revision_info.get("files", {}).items():
        if file_path == "/COMMIT_MSG":
            continue
        encoded_path = quote(file_path, safe='')
        diff_endpoint = f"a/changes/{change_id}/revisions/{target_revision}/files/{encoded_path}/diff"
        diff_info = make_gerrit_rest_request(ctx, diff_endpoint)
        file_data = {
            "path": file_path,
            "status": file_info.get("status", "MODIFIED"),
            "lines_inserted": file_info.get("lines_inserted", 0),
            "lines_deleted": file_info.get("lines_deleted", 0),
            "size_delta": file_info.get("size_delta", 0),
            "diff": diff_info
        }
        processed_files.append(file_data)
    logger.info(f"[Gerrit] fetch_gerrit_change succeeded for change_id={change_id}, patchset_number={patchset_number}, files_count={len(processed_files)}")
    return {
        "change_info": change_info,
        "project": project,
        "revision": target_revision,
        "patchset": revision_info,
        "files": processed_files
    }

@gerrit_mcp.tool()
def fetch_patchset_diff(
    ctx: Context,
    change_id: str,
    base_patchset: str,
    target_patchset: str,
    file_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    [tags: read, gerrit]
    Fetch the diff between two patchsets for a given Gerrit change.

    Args:
        ctx (Context): The MCP request context, including Gerrit credentials.
        change_id (str): The Gerrit change ID (e.g., '12345').
        base_patchset (str): The base patchset number.
        target_patchset (str): The target patchset number.
        file_path (Optional[str]): If provided, only fetch the diff for this file.

    Returns:
        Dict[str, Any]: A dictionary containing base/target revision, patchset numbers, and changed files with diffs.
    """
    logger.info(f"[Gerrit] fetch_patchset_diff called with change_id={change_id}, base_patchset={base_patchset}, target_patchset={target_patchset}, file_path={file_path}")
    change_endpoint = f"a/changes/{change_id}/detail?o=ALL_REVISIONS&o=ALL_FILES"
    change_info = make_gerrit_rest_request(ctx, change_endpoint)
    if not change_info:
        logger.warning(f"[Gerrit] No change info found for change_id={change_id}")
        raise ValueError(f"Change {change_id} not found")
    revisions = change_info.get("revisions", {})
    base_revision = None
    target_revision = None
    for rev, rev_info in revisions.items():
        if str(rev_info.get("_number")) == str(base_patchset):
            base_revision = rev
        if str(rev_info.get("_number")) == str(target_patchset):
            target_revision = rev
    if not base_revision or not target_revision:
        available_patchsets = sorted([str(info.get("_number")) for info in revisions.values()])
        logger.warning(f"[Gerrit] Patchset(s) not found for change_id={change_id}. Available: {available_patchsets}")
        raise ValueError(f"Patchset(s) not found. Available patchsets: {', '.join(available_patchsets)}")
    diff_endpoint = f"a/changes/{change_id}/revisions/{target_revision}/files"
    if base_revision:
        diff_endpoint += f"?base={base_revision}"
    files_diff = make_gerrit_rest_request(ctx, diff_endpoint)
    changed_files = {}
    for fpath, file_info in files_diff.items():
        if fpath == "/COMMIT_MSG":
            continue
        if file_info.get("status") != "SAME":
            encoded_path = quote(fpath, safe='')
            file_diff_endpoint = f"a/changes/{change_id}/revisions/{target_revision}/files/{encoded_path}/diff"
            if base_revision:
                file_diff_endpoint += f"?base={base_revision}"
            diff_info = make_gerrit_rest_request(ctx, file_diff_endpoint)
            changed_files[fpath] = {
                "status": file_info.get("status", "MODIFIED"),
                "lines_inserted": file_info.get("lines_inserted", 0),
                "lines_deleted": file_info.get("lines_deleted", 0),
                "size_delta": file_info.get("size_delta", 0),
                "diff": diff_info
            }
    logger.info(f"[Gerrit] fetch_patchset_diff succeeded for change_id={change_id}, base_patchset={base_patchset}, target_patchset={target_patchset}, changed_files_count={len(changed_files)}")
    return {
        "base_revision": base_revision,
        "target_revision": target_revision,
        "base_patchset": base_patchset,
        "target_patchset": target_patchset,
        "files": changed_files
    }

@gerrit_mcp.tool()
def get_repository_path_from_change(
    ctx: Context,
    change_url: str,
    clone_url_type: str = "http"
) -> Dict[str, Any]:
    """
    [tags: read, gerrit]
    Extract full clone URL from a Gerrit Change Request URL.

    Args:
        ctx1 (Context): The MCP request context, including Gerrit credentials.
        change_url (str): The Gerrit Change Request URL (e.g., 'http://gerrit01.sdt.com/c/RDK/qjybrowser/+/40261').
        clone_url_type (str): 'http' (default) or 'ssh'.

    Returns:
        Dict[str, Any]: A dictionary containing:
            - full_clone_url: The full clone URL (http(s) or ssh)
    """
    logger.info(f"[Gerrit] get_repository_path_from_change called with change_url={change_url}, clone_url_type={clone_url_type}")
    import os
    try:
        # 1. 解析 change_url
        parsed = urlparse(change_url)
        protocol = parsed.scheme
        host = parsed.hostname
        path_parts = parsed.path.strip('/').split('/')
        plus_index = path_parts.index('+') if '+' in path_parts else -1
        if plus_index > 1:
            project = '/'.join(path_parts[1:plus_index])
            change_id = path_parts[plus_index + 1]
        else:
            change_id = path_parts[-1]
            change_info = fetch_gerrit_change(ctx, change_id)
            project = change_info['project']

        # 2. 获取 user
        user = getattr(ctx, 'user', None) or os.getenv("GERRIT_USER", "")

        # 3. 拼接 full_clone_url
        if clone_url_type == "ssh":
            user_prefix = f"{user}@" if user else ""
            full_clone_url = f"ssh://{user_prefix}{host}:29418/{project}.git"
        else:
            user_prefix = f"{user}@" if user else ""
            full_clone_url = f"{protocol}://{user_prefix}{host}/a/{project}.git"

        return {
            "full_clone_url": full_clone_url
        }
    except Exception as e:
        logger.error(f"[Gerrit] Error extracting repository path: {str(e)}")
        raise ValueError(f"Failed to extract repository path: {str(e)}") 