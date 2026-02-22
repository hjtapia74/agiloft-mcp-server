#!/usr/bin/env python3
"""
Agiloft MCP Server

A Model Context Protocol server for interacting with Agiloft REST API.
Provides tools for entity CRUD operations, search, upsert, and
attachment management through a generic, table-driven architecture.
Also provides MCP Prompts for guided business workflows and composite
workflow tools that chain multiple API calls.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import (
    ServerCapabilities,
    ToolsCapability,
    PromptsCapability,
    Tool,
    TextContent,
    Prompt,
    GetPromptResult,
)
from mcp.server.stdio import stdio_server

# Handle both direct execution and package imports
try:
    from .agiloft_client import AgiloftClient
    from .config import Config
    from .tool_generator import generate_tools
    from .tool_handlers import dispatch_tool_call
    from .prompt_registry import list_prompts as _list_prompts, get_prompt as _get_prompt
    from .workflow_tools import generate_workflow_tools
    from .workflow_handlers import dispatch_workflow_call
except ImportError:
    from agiloft_client import AgiloftClient
    from config import Config
    from tool_generator import generate_tools
    from tool_handlers import dispatch_tool_call
    from prompt_registry import list_prompts as _list_prompts, get_prompt as _get_prompt
    from workflow_tools import generate_workflow_tools
    from workflow_handlers import dispatch_workflow_call

# Configure logging to file (stderr is captured by Claude Desktop differently)
import os as _os
_log_dir = _os.path.expanduser("~/Library/Logs/Claude")
_os.makedirs(_log_dir, exist_ok=True)
_log_file = _os.path.join(_log_dir, "agiloft-server-debug.log")
# Use force=True to override any prior logging config from imported modules
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(_log_file), logging.StreamHandler()],
    force=True,
)
logger = logging.getLogger(__name__)
logger.info(f"Logging initialized, writing to {_log_file}")

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

# Generate entity tools and dispatch map at startup
_entity_tools, _entity_dispatch = generate_tools()

# Generate workflow tools and dispatch map
_workflow_tools, _workflow_dispatch = generate_workflow_tools()

# Combined tool list
_all_tools = _entity_tools + _workflow_tools


@server.list_tools()
async def handle_list_tools() -> List[Tool]:
    """List all available Agiloft tools (entity + workflow)."""
    return _all_tools


@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls by dispatching to entity or workflow handler."""
    # Log arguments but truncate large values (e.g. base64 file content)
    safe_args = {}
    for k, v in (arguments or {}).items():
        if isinstance(v, str) and len(v) > 200:
            safe_args[k] = f"{v[:100]}... ({len(v)} chars)"
        else:
            safe_args[k] = v
    logger.info(f"call_tool: {name} args={safe_args}")
    try:
        await agiloft_client.ensure_authenticated()

        # Try workflow dispatch first (smaller set, fast lookup)
        if name in _workflow_dispatch:
            result = await dispatch_workflow_call(
                name, arguments, agiloft_client, _workflow_dispatch
            )
            logger.info(f"call_tool: {name} completed successfully")
            return result

        # Fall through to entity dispatch
        result = await dispatch_tool_call(name, arguments, agiloft_client, _entity_dispatch)
        logger.info(f"call_tool: {name} completed successfully")
        return result
    except Exception as e:
        logger.error(f"Error in {name}: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Error: {e}")]


@server.list_prompts()
async def handle_list_prompts() -> List[Prompt]:
    """List available MCP prompts for guided workflows."""
    return _list_prompts()


@server.get_prompt()
async def handle_get_prompt(
    name: str, arguments: Optional[Dict[str, str]] = None
) -> GetPromptResult:
    """Render a prompt by name with the given arguments."""
    return _get_prompt(name, arguments)


async def main():
    """Main server entry point."""
    # Configure logging based on config
    log_level = getattr(logging, config.get('server.log_level', 'INFO').upper())
    logging.getLogger().setLevel(log_level)

    logger.info("Starting Agiloft MCP Server...")
    logger.info(f"Base URL: {config.get('agiloft.base_url')}")
    logger.info(f"Knowledge Base: {config.get('agiloft.kb')}")
    logger.info(f"Registered entity tools: {len(_entity_tools)}")
    logger.info(f"Registered workflow tools: {len(_workflow_tools)}")
    logger.info(f"Registered prompts: {len(_list_prompts())}")
    logger.info(f"Total tools: {len(_all_tools)}")
    for tool in _all_tools:
        logger.debug(f"  - {tool.name}")

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="agiloft-mcp-server",
                server_version="3.0.0",
                capabilities=ServerCapabilities(
                    tools=ToolsCapability(listChanged=False),
                    prompts=PromptsCapability(listChanged=False),
                )
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
