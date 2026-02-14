#!/usr/bin/env python3
"""
Agiloft MCP Server

A Model Context Protocol server for interacting with Agiloft REST API.
Provides tools for entity CRUD operations, search, upsert, and
attachment management through a generic, table-driven architecture.
"""

import asyncio
import logging
from typing import Any, Dict, List

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import ServerCapabilities, ToolsCapability, Tool, TextContent
from mcp.server.stdio import stdio_server

# Handle both direct execution and package imports
try:
    from .agiloft_client import AgiloftClient
    from .config import Config
    from .tool_generator import generate_tools
    from .tool_handlers import dispatch_tool_call
except ImportError:
    from agiloft_client import AgiloftClient
    from config import Config
    from tool_generator import generate_tools
    from tool_handlers import dispatch_tool_call

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize configuration and client
config = Config()
if not config.validate():
    logger.warning(
        "Configuration may be incomplete. "
        "Check required fields: agiloft.base_url, agiloft.username, agiloft.password, agiloft.kb"
    )

agiloft_client = AgiloftClient(config)

# Create the MCP server
server = Server("agiloft-mcp-server")

# Generate tools and dispatch map at startup
_tools, _tool_dispatch = generate_tools()


@server.list_tools()
async def handle_list_tools() -> List[Tool]:
    """List available Agiloft tools."""
    return _tools


@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls by dispatching to the appropriate handler."""
    try:
        await agiloft_client.ensure_authenticated()
        return await dispatch_tool_call(name, arguments, agiloft_client, _tool_dispatch)
    except Exception as e:
        logger.error(f"Error in {name}: {e}")
        return [TextContent(type="text", text=f"Error: {e}")]


async def main():
    """Main server entry point."""
    # Configure logging based on config
    log_level = getattr(logging, config.get('server.log_level', 'INFO').upper())
    logging.getLogger().setLevel(log_level)

    logger.info("Starting Agiloft MCP Server...")
    logger.info(f"Base URL: {config.get('agiloft.base_url')}")
    logger.info(f"Knowledge Base: {config.get('agiloft.kb')}")
    logger.info(f"Registered tools: {len(_tools)}")
    for tool in _tools:
        logger.debug(f"  - {tool.name}")

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="agiloft-mcp-server",
                server_version="2.0.0",
                capabilities=ServerCapabilities(
                    tools=ToolsCapability(listChanged=False)
                )
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
