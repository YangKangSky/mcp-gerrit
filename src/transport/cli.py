"""Command line interface for Gerrit Review MCP Server."""

import sys
import os

# Add the project root directory to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def main():
    """Run the MCP server."""
    from src.transport.rest import run_server
    run_server()

if __name__ == "__main__":
    main() 