"""
MCP Tool Handlers

Generic handlers for all entity tool calls. Each handler receives an
EntityConfig, arguments dict, and AgiloftClient, and returns MCP TextContent.

The dispatch_tool_call function routes tool names to the correct handler
using the dispatch map from tool_generator.
"""

import base64
import json
import logging
import re
from typing import Any, Dict, List

from mcp.types import TextContent

# Handle both direct execution and package imports
try:
    from .agiloft_client import AgiloftClient
    from .entity_registry import EntityConfig, get_entity
except ImportError:
    from agiloft_client import AgiloftClient
    from entity_registry import EntityConfig, get_entity

logger = logging.getLogger(__name__)


# --- Query sanitization (fixes SQL injection vulnerability) ---

def _sanitize_query_value(value: str) -> str:
    """Escape special characters in query values to prevent injection."""
    sanitized = value.replace("'", "''")
    sanitized = sanitized.replace("--", "")
    sanitized = sanitized.replace(";", "")
    return sanitized


def _is_structured_query(query: str) -> bool:
    """Detect if a query string uses structured (SQL-like) syntax."""
    structured_patterns = [
        r"\b\w+\s*[=<>!]+\s*",      # field = value, field > value
        r"\bAND\b", r"\bOR\b",       # boolean operators
        r"\bLIKE\b", r"\bIN\b",      # SQL keywords
        r"\bNOT\b", r"\bBETWEEN\b",
        r"\bIS\b\s+\bNULL\b",
    ]
    return any(re.search(pattern, query, re.IGNORECASE) for pattern in structured_patterns)


# --- Response formatting ---

def _format_response(operation: str, entity: EntityConfig, data: Any,
                     record_id: int = None) -> List[TextContent]:
    """Format a standardized success response."""
    result: Dict[str, Any] = {
        "success": True,
        "operation": operation,
        "entity": entity.key,
    }
    if record_id is not None:
        result["record_id"] = record_id
    if isinstance(data, list):
        result["count"] = len(data)
    result["data"] = data

    return [TextContent(
        type="text",
        text=json.dumps(result, indent=2, default=str),
    )]


def _format_error(operation: str, entity: EntityConfig, error: str,
                  record_id: int = None) -> List[TextContent]:
    """Format a standardized error response."""
    result: Dict[str, Any] = {
        "success": False,
        "operation": operation,
        "entity": entity.key,
        "error": error,
    }
    if record_id is not None:
        result["record_id"] = record_id

    return [TextContent(
        type="text",
        text=json.dumps(result, indent=2, default=str),
    )]


# --- Individual operation handlers ---

async def handle_search(entity: EntityConfig, arguments: Dict[str, Any],
                        client: AgiloftClient) -> List[TextContent]:
    """Handle search requests for any entity."""
    query = arguments.get("query", "")
    fields = arguments.get("fields", entity.default_search_fields)
    limit = arguments.get("limit", 50)

    try:
        if _is_structured_query(query):
            # Structured query: pass through as-is
            results = await client.search_records(entity.api_path, query, fields)
        elif entity.text_search_fields and query.strip():
            # Text search: query each text field with ~= and merge results
            # (Agiloft doesn't support OR across different fields with ~=)
            sanitized = _sanitize_query_value(query)
            seen_ids = set()
            results = []
            for text_field in entity.text_search_fields:
                field_query = f"{text_field}~='{sanitized}'"
                field_results = await client.search_records(
                    entity.api_path, field_query, fields
                )
                for record in field_results:
                    rid = record.get("id")
                    if rid not in seen_ids:
                        seen_ids.add(rid)
                        results.append(record)
        else:
            results = await client.search_records(entity.api_path, query, fields)

        if isinstance(results, list) and len(results) > limit:
            results = results[:limit]
        return _format_response("search", entity, results)
    except Exception as e:
        return _format_error("search", entity, str(e))


async def handle_get(entity: EntityConfig, arguments: Dict[str, Any],
                     client: AgiloftClient) -> List[TextContent]:
    """Handle get-by-id requests for any entity."""
    record_id = arguments.get("record_id")
    fields = arguments.get("fields")

    try:
        record = await client.get_record(entity.api_path, record_id, fields)
        return _format_response("get", entity, record, record_id)
    except Exception as e:
        return _format_error("get", entity, str(e), record_id)


def _strip_empty_values(data: Dict[str, Any]) -> Dict[str, Any]:
    """Remove keys with empty/None values to avoid linked field validation errors."""
    return {k: v for k, v in data.items() if v is not None and v != ""}


async def handle_create(entity: EntityConfig, arguments: Dict[str, Any],
                        client: AgiloftClient) -> List[TextContent]:
    """Handle create requests for any entity."""
    data = _strip_empty_values(arguments.get("data", {}))

    try:
        result = await client.create_record(entity.api_path, data)
        return _format_response("create", entity, result)
    except Exception as e:
        return _format_error("create", entity, str(e))


async def handle_update(entity: EntityConfig, arguments: Dict[str, Any],
                        client: AgiloftClient) -> List[TextContent]:
    """Handle update requests for any entity."""
    record_id = arguments.get("record_id")
    data = _strip_empty_values(arguments.get("data", {}))

    try:
        result = await client.update_record(entity.api_path, record_id, data)
        return _format_response("update", entity, result, record_id)
    except Exception as e:
        return _format_error("update", entity, str(e), record_id)


async def handle_delete(entity: EntityConfig, arguments: Dict[str, Any],
                        client: AgiloftClient) -> List[TextContent]:
    """Handle delete requests for any entity."""
    record_id = arguments.get("record_id")
    delete_rule = arguments.get("delete_rule", "UNLINK_WHERE_POSSIBLE_OTHERWISE_DELETE")

    try:
        result = await client.delete_record(entity.api_path, record_id, delete_rule)
        return _format_response("delete", entity, result, record_id)
    except Exception as e:
        return _format_error("delete", entity, str(e), record_id)


async def handle_upsert(entity: EntityConfig, arguments: Dict[str, Any],
                        client: AgiloftClient) -> List[TextContent]:
    """Handle upsert (insert or update) requests for any entity."""
    query = arguments.get("query", "")
    data = _strip_empty_values(arguments.get("data", {}))

    try:
        result = await client.upsert_record(entity.api_path, query, data)
        return _format_response("upsert", entity, result)
    except Exception as e:
        return _format_error("upsert", entity, str(e))


async def handle_attach_file(entity: EntityConfig, arguments: Dict[str, Any],
                             client: AgiloftClient) -> List[TextContent]:
    """Handle file attachment upload requests."""
    record_id = arguments.get("record_id")
    field_name = arguments.get("field")
    file_name = arguments.get("file_name")
    file_content_b64 = arguments.get("file_content_base64", "")

    try:
        file_data = base64.b64decode(file_content_b64)
    except Exception as e:
        return _format_error("attach_file", entity, f"Invalid base64 content: {e}", record_id)

    try:
        result = await client.attach_file(
            entity.api_path, record_id, field_name, file_name, file_data
        )
        return _format_response("attach_file", entity, result, record_id)
    except Exception as e:
        return _format_error("attach_file", entity, str(e), record_id)


async def handle_retrieve_attachment(entity: EntityConfig, arguments: Dict[str, Any],
                                     client: AgiloftClient) -> List[TextContent]:
    """Handle attachment retrieval requests."""
    record_id = arguments.get("record_id")
    field_name = arguments.get("field")
    file_position = arguments.get("file_position", 0)

    try:
        result = await client.retrieve_attachment(
            entity.api_path, record_id, field_name, file_position
        )
        return _format_response("retrieve_attachment", entity, result, record_id)
    except Exception as e:
        return _format_error("retrieve_attachment", entity, str(e), record_id)


async def handle_remove_attachment(entity: EntityConfig, arguments: Dict[str, Any],
                                   client: AgiloftClient) -> List[TextContent]:
    """Handle attachment removal requests."""
    record_id = arguments.get("record_id")
    field_name = arguments.get("field")
    file_position = arguments.get("file_position", 0)

    try:
        result = await client.remove_attachment(
            entity.api_path, record_id, field_name, file_position
        )
        return _format_response("remove_attachment", entity, result, record_id)
    except Exception as e:
        return _format_error("remove_attachment", entity, str(e), record_id)


async def handle_attachment_info(entity: EntityConfig, arguments: Dict[str, Any],
                                 client: AgiloftClient) -> List[TextContent]:
    """Handle attachment metadata requests."""
    record_id = arguments.get("record_id")
    field_name = arguments.get("field")

    try:
        result = await client.get_attachment_info(
            entity.api_path, record_id, field_name
        )
        return _format_response("get_attachment_info", entity, result, record_id)
    except Exception as e:
        return _format_error("get_attachment_info", entity, str(e), record_id)


async def handle_action_button(entity: EntityConfig, arguments: Dict[str, Any],
                                client: AgiloftClient) -> List[TextContent]:
    """Handle action button trigger requests."""
    record_id = arguments.get("record_id")
    button_name = arguments.get("button_name")

    try:
        result = await client.trigger_action_button(entity.api_path, record_id, button_name)
        return _format_response("action_button", entity, result, record_id)
    except Exception as e:
        return _format_error("action_button", entity, str(e), record_id)


async def handle_evaluate_format(entity: EntityConfig, arguments: Dict[str, Any],
                                  client: AgiloftClient) -> List[TextContent]:
    """Handle evaluate format requests."""
    record_id = arguments.get("record_id")
    formula = arguments.get("formula")

    try:
        result = await client.evaluate_format(entity.api_path, record_id, formula)
        return _format_response("evaluate_format", entity, result, record_id)
    except Exception as e:
        return _format_error("evaluate_format", entity, str(e), record_id)


# --- Dispatch ---

HANDLER_DISPATCH = {
    "search": handle_search,
    "get": handle_get,
    "create": handle_create,
    "update": handle_update,
    "delete": handle_delete,
    "upsert": handle_upsert,
    "attach_file": handle_attach_file,
    "retrieve_attachment": handle_retrieve_attachment,
    "remove_attachment": handle_remove_attachment,
    "get_attachment_info": handle_attachment_info,
    "action_button": handle_action_button,
    "evaluate_format": handle_evaluate_format,
}


async def dispatch_tool_call(name: str, arguments: Dict[str, Any],
                             client: AgiloftClient,
                             tool_dispatch: Dict[str, tuple]) -> List[TextContent]:
    """Dispatch a tool call to the appropriate handler.

    Args:
        name: Tool name (e.g., "agiloft_search_contracts")
        arguments: Tool arguments from MCP
        client: AgiloftClient instance
        tool_dispatch: Mapping of tool_name -> (entity_key, action) from generate_tools()
    """
    if name not in tool_dispatch:
        raise ValueError(f"Unknown tool: {name}")

    entity_key, action = tool_dispatch[name]
    entity = get_entity(entity_key)

    handler = HANDLER_DISPATCH.get(action)
    if not handler:
        raise ValueError(f"Unknown action: {action}")

    return await handler(entity, arguments, client)
