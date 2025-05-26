"""Command line interface for Gerrit Review MCP Server."""

def main():
    """Run the MCP server."""
    from .server import run_server
    run_server()

if __name__ == "__main__":
    main() 