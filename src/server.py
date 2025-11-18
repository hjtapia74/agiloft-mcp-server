#!/usr/bin/env python3
"""
Agiloft MCP Server

A Model Context Protocol server for interacting with Agiloft REST API.
Provides tools for contract CRUD operations and search functionality.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import ServerCapabilities, ToolsCapability
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    LoggingLevel
)
# Handle both direct execution and package imports
try:
    from .agiloft_client import AgiloftClient
    from .config import Config
except ImportError:
    from agiloft_client import AgiloftClient
    from config import Config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize configuration and client
config = Config()
agiloft_client = AgiloftClient(config)

# Create the MCP server
server = Server("agiloft-mcp-server")

@server.list_tools()
async def handle_list_tools() -> List[Tool]:
    """List available Agiloft tools."""
    return [
        Tool(
            name="agiloft_search_contracts",
            description="Search for contracts using text or structured queries. Supports natural language search like 'contracts ending this year' or structured queries like 'status=Active AND amount>1000000'",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query - can be natural language text or structured query syntax"
                    },
                    "fields": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional: Specific fields to return. If not provided, returns essential fields",
                        "default": ["id", "contract_title1", "company_name", "contract_amount", "contract_end_date", "internal_contract_owner", "date_signed"]
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 50
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="agiloft_get_contract",
            description="Retrieve a specific contract by ID with full details",
            inputSchema={
                "type": "object",
                "properties": {
                    "contract_id": {
                        "type": "integer",
                        "description": "The ID of the contract to retrieve"
                    },
                    "fields": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional: Specific fields to return. If not provided, returns all fields"
                    }
                },
                "required": ["contract_id"]
            }
        ),
        Tool(
            name="agiloft_create_contract",
            description="Create a new contract in Agiloft",
            inputSchema={
                "type": "object",
                "properties": {
                    "contract_data": {
                        "type": "object",
                        "description": "Contract data object containing fields like title, company_name, contract_amount, etc.",
                        "properties": {
                            "contract_title1": {"type": "string", "description": "Contract title"},
                            "company_name": {"type": "string", "description": "Company name"},
                            "contract_amount": {"type": "number", "description": "Contract amount"},
                            "contract_start_date": {"type": "string", "description": "Start date (YYYY-MM-DD format)"},
                            "contract_end_date": {"type": "string", "description": "End date (YYYY-MM-DD format)"},
                            "contract_term_in_months": {"type": "integer", "description": "Contract term in months"},
                            "internal_contract_owner": {"type": "string", "description": "Internal owner name"}
                        }
                    }
                },
                "required": ["contract_data"]
            }
        ),
        Tool(
            name="agiloft_update_contract",
            description="Update an existing contract in Agiloft",
            inputSchema={
                "type": "object",
                "properties": {
                    "contract_id": {
                        "type": "integer",
                        "description": "The ID of the contract to update"
                    },
                    "contract_data": {
                        "type": "object",
                        "description": "Contract data object with fields to update"
                    }
                },
                "required": ["contract_id", "contract_data"]
            }
        ),
        Tool(
            name="agiloft_delete_contract",
            description="Delete a contract from Agiloft",
            inputSchema={
                "type": "object",
                "properties": {
                    "contract_id": {
                        "type": "integer",
                        "description": "The ID of the contract to delete"
                    },
                    "delete_rule": {
                        "type": "string",
                        "description": "Delete rule strategy",
                        "enum": ["ERROR_IF_DEPENDANTS", "APPLY_DELETE_WHERE_POSSIBLE", "DELETE_WHERE_POSSIBLE_OTHERWISE_UNLINK", "UNLINK_WHERE_POSSIBLE_OTHERWISE_DELETE"],
                        "default": "UNLINK_WHERE_POSSIBLE_OTHERWISE_DELETE"
                    }
                },
                "required": ["contract_id"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls."""
    try:
        # Ensure client is authenticated
        await agiloft_client.ensure_authenticated()
        
        if name == "agiloft_search_contracts":
            return await handle_search_contracts(arguments)
        elif name == "agiloft_get_contract":
            return await handle_get_contract(arguments)
        elif name == "agiloft_create_contract":
            return await handle_create_contract(arguments)
        elif name == "agiloft_update_contract":
            return await handle_update_contract(arguments)
        elif name == "agiloft_delete_contract":
            return await handle_delete_contract(arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")
            
    except Exception as e:
        logger.error(f"Error in {name}: {str(e)}")
        return [TextContent(type="text", text=f"Error: {str(e)}")]

async def handle_search_contracts(arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle contract search requests."""
    query = arguments.get("query", "")
    fields = arguments.get("fields", [
        "id", "contract_title1", "company_name", "contract_amount", 
        "contract_end_date", "internal_contract_owner", "date_signed", "record_type"
    ])
    limit = arguments.get("limit", 50)
    
    # Detect if it's a structured query or natural language
    is_structured = any(op in query.lower() for op in ["=", ">", "<", "and", "or", "status=", "amount>"])
    
    if is_structured:
        # Use as-is for structured queries
        search_query = query
    else:
        # Convert natural language to search - basic conversion
        search_query = f"contract_title1 LIKE '%{query}%' OR company_name LIKE '%{query}%'"
    
    try:
        results = await agiloft_client.search_contracts(
            query=search_query,
            fields=fields
        )
        
        # Limit results
        if isinstance(results, list) and len(results) > limit:
            results = results[:limit]
            
        return [TextContent(
            type="text", 
            text=f"Found {len(results) if isinstance(results, list) else 'unknown number of'} contracts:\n\n" + 
                 json.dumps(results, indent=2, default=str)
        )]
    except Exception as e:
        return [TextContent(type="text", text=f"Search failed: {str(e)}")]

async def handle_get_contract(arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle get contract requests."""
    contract_id = arguments.get("contract_id")
    fields = arguments.get("fields")
    
    try:
        contract = await agiloft_client.get_contract(contract_id, fields)
        return [TextContent(
            type="text", 
            text=f"Contract {contract_id}:\n\n" + json.dumps(contract, indent=2, default=str)
        )]
    except Exception as e:
        return [TextContent(type="text", text=f"Failed to get contract {contract_id}: {str(e)}")]

async def handle_create_contract(arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle create contract requests."""
    contract_data = arguments.get("contract_data", {})
    
    try:
        result = await agiloft_client.create_contract(contract_data)
        return [TextContent(
            type="text", 
            text=f"Contract created successfully:\n\n" + json.dumps(result, indent=2, default=str)
        )]
    except Exception as e:
        return [TextContent(type="text", text=f"Failed to create contract: {str(e)}")]

async def handle_update_contract(arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle update contract requests."""
    contract_id = arguments.get("contract_id")
    contract_data = arguments.get("contract_data", {})
    
    try:
        result = await agiloft_client.update_contract(contract_id, contract_data)
        return [TextContent(
            type="text", 
            text=f"Contract {contract_id} updated successfully:\n\n" + json.dumps(result, indent=2, default=str)
        )]
    except Exception as e:
        return [TextContent(type="text", text=f"Failed to update contract {contract_id}: {str(e)}")]

async def handle_delete_contract(arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle delete contract requests."""
    contract_id = arguments.get("contract_id")
    delete_rule = arguments.get("delete_rule", "UNLINK_WHERE_POSSIBLE_OTHERWISE_DELETE")
    
    try:
        result = await agiloft_client.delete_contract(contract_id, delete_rule)
        return [TextContent(
            type="text", 
            text=f"Contract {contract_id} deletion result:\n\n" + json.dumps(result, indent=2, default=str)
        )]
    except Exception as e:
        return [TextContent(type="text", text=f"Failed to delete contract {contract_id}: {str(e)}")]

async def main():
    """Main server entry point."""
    # Configure logging based on config
    log_level = getattr(logging, config.get('server.log_level', 'INFO').upper())
    logging.getLogger().setLevel(log_level)
    
    logger.info("Starting Agiloft MCP Server...")
    logger.info(f"Base URL: {config.get('agiloft.base_url')}")
    logger.info(f"Knowledge Base: {config.get('agiloft.kb')}")
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="agiloft-mcp-server",
                server_version="1.0.0",
                capabilities=ServerCapabilities(
                    tools=ToolsCapability(listChanged=False)
                )
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())