"""
MCP Tool Generator

Dynamically generates MCP Tool definitions and dispatch mappings
from the entity registry. Each entity gets a consistent set of tools
based on the operations it supports.
"""

from typing import Dict, List, Tuple

from mcp.types import Tool

# Handle both direct execution and package imports
try:
    from .entity_registry import ENTITY_REGISTRY, EntityConfig
except ImportError:
    from entity_registry import ENTITY_REGISTRY, EntityConfig

# Type alias: tool_name -> (entity_key, action)
ToolDispatch = Dict[str, Tuple[str, str]]

DELETE_RULES = [
    "ERROR_IF_DEPENDANTS",
    "APPLY_DELETE_WHERE_POSSIBLE",
    "DELETE_WHERE_POSSIBLE_OTHERWISE_UNLINK",
    "UNLINK_WHERE_POSSIBLE_OTHERWISE_DELETE",
]


def _tool_name(action: str, entity: EntityConfig, plural: bool = False) -> str:
    """Generate tool name like agiloft_{action}_{entity}."""
    entity_name = entity.key_plural if plural else entity.key
    return f"agiloft_{action}_{entity_name}"


def _data_schema(entity: EntityConfig, description: str) -> dict:
    """Build a data object schema with key fields + additionalProperties."""
    properties = {}
    for field_name, field_info in entity.key_fields.items():
        properties[field_name] = {
            "type": field_info["type"],
            "description": field_info["description"],
        }
    return {
        "type": "object",
        "description": description,
        "properties": properties,
        "additionalProperties": True,
    }


# --- Tool generators ---
# Each returns (Tool, action_string) so the dispatch map can be built.


def _gen_search_tool(entity: EntityConfig) -> Tuple[Tool, str]:
    searchable = ", ".join(entity.text_search_fields) if entity.text_search_fields else "key fields"
    return Tool(
        name=_tool_name("search", entity, plural=True),
        description=(
            f"Search for {entity.display_name_plural.lower()} in Agiloft. "
            f"Use structured queries like 'status=Active AND field>value' "
            f"or text search against {searchable}. "
            f"Returns matching records with key fields."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        f"Structured query (e.g. 'status=Active AND field>value') "
                        f"or text to search in {searchable} using LIKE matching"
                    ),
                },
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        f"Fields to return. Defaults to: "
                        f"{', '.join(entity.default_search_fields[:5])}..."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results to return (default 50)",
                    "default": 50,
                    "minimum": 1,
                    "maximum": 500,
                },
            },
            "required": ["query"],
        },
    ), "search"


def _gen_get_tool(entity: EntityConfig) -> Tuple[Tool, str]:
    return Tool(
        name=_tool_name("get", entity),
        description=(
            f"Retrieve a specific {entity.display_name.lower()} by ID with full details."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "record_id": {
                    "type": "integer",
                    "description": f"The ID of the {entity.display_name.lower()} to retrieve",
                    "minimum": 1,
                },
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific fields to return. If omitted, returns all fields.",
                },
            },
            "required": ["record_id"],
        },
    ), "get"


def _gen_create_tool(entity: EntityConfig) -> Tuple[Tool, str]:
    required_desc = ", ".join(entity.required_fields) if entity.required_fields else "none"
    return Tool(
        name=_tool_name("create", entity),
        description=(
            f"Create a new {entity.display_name.lower()} in Agiloft. "
            f"Required fields: {required_desc}. "
            f"Key fields are shown in the schema; any valid Agiloft field can be included."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "data": _data_schema(
                    entity,
                    f"{entity.display_name} data. Key fields shown below; "
                    f"any valid Agiloft {entity.display_name.lower()} field can be included.",
                ),
            },
            "required": ["data"],
        },
    ), "create"


def _gen_update_tool(entity: EntityConfig) -> Tuple[Tool, str]:
    return Tool(
        name=_tool_name("update", entity),
        description=(
            f"Update an existing {entity.display_name.lower()} in Agiloft. "
            f"Only include fields that need to be changed."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "record_id": {
                    "type": "integer",
                    "description": f"The ID of the {entity.display_name.lower()} to update",
                    "minimum": 1,
                },
                "data": _data_schema(
                    entity,
                    f"Fields to update on the {entity.display_name.lower()}.",
                ),
            },
            "required": ["record_id", "data"],
        },
    ), "update"


def _gen_delete_tool(entity: EntityConfig) -> Tuple[Tool, str]:
    return Tool(
        name=_tool_name("delete", entity),
        description=(
            f"Delete a {entity.display_name.lower()} from Agiloft. This is irreversible. "
            f"The delete_rule controls how dependent records are handled."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "record_id": {
                    "type": "integer",
                    "description": f"The ID of the {entity.display_name.lower()} to delete",
                    "minimum": 1,
                },
                "delete_rule": {
                    "type": "string",
                    "description": "How to handle dependent records",
                    "enum": DELETE_RULES,
                    "default": "UNLINK_WHERE_POSSIBLE_OTHERWISE_DELETE",
                },
            },
            "required": ["record_id"],
        },
    ), "delete"


def _gen_upsert_tool(entity: EntityConfig) -> Tuple[Tool, str]:
    return Tool(
        name=_tool_name("upsert", entity),
        description=(
            f"Insert or update a {entity.display_name.lower()}. "
            f"If a record matching the query exists, updates it; otherwise creates a new one. "
            f"Query format: fieldName~='value' (e.g., salesforce_contract_id~='SF-12345')."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Match query: fieldName~='value' to find existing record",
                },
                "data": _data_schema(
                    entity,
                    f"{entity.display_name} data to insert or update.",
                ),
            },
            "required": ["query", "data"],
        },
    ), "upsert"


def _gen_attach_file_tool(entity: EntityConfig) -> Tuple[Tool, str]:
    return Tool(
        name=_tool_name("attach_file", entity),
        description=(
            f"Upload a file attachment to a {entity.display_name.lower()} record. "
            f"Requires the record ID, target field name, file name, and base64-encoded file content."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "record_id": {
                    "type": "integer",
                    "description": f"The ID of the {entity.display_name.lower()} record",
                    "minimum": 1,
                },
                "field": {
                    "type": "string",
                    "description": "The file field name to attach to (e.g., 'attached_file')",
                },
                "file_name": {
                    "type": "string",
                    "description": "Name of the file being uploaded",
                },
                "file_content_base64": {
                    "type": "string",
                    "description": "Base64-encoded file content",
                },
            },
            "required": ["record_id", "field", "file_name", "file_content_base64"],
        },
    ), "attach_file"


def _gen_retrieve_attach_tool(entity: EntityConfig) -> Tuple[Tool, str]:
    return Tool(
        name=_tool_name("retrieve_attachment", entity),
        description=(
            f"Download an attachment from a {entity.display_name.lower()} record. "
            f"Use get_attachment_info first to find the correct field and file position."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "record_id": {
                    "type": "integer",
                    "description": f"The ID of the {entity.display_name.lower()} record",
                    "minimum": 1,
                },
                "field": {
                    "type": "string",
                    "description": "The file field name to retrieve from",
                },
                "file_position": {
                    "type": "integer",
                    "description": "Position of the file in the field (0-based, default 0)",
                    "default": 0,
                    "minimum": 0,
                },
            },
            "required": ["record_id", "field"],
        },
    ), "retrieve_attachment"


def _gen_remove_attach_tool(entity: EntityConfig) -> Tuple[Tool, str]:
    return Tool(
        name=_tool_name("remove_attachment", entity),
        description=(
            f"Remove an attachment from a {entity.display_name.lower()} record's file field. "
            f"Use get_attachment_info first to confirm the file position."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "record_id": {
                    "type": "integer",
                    "description": f"The ID of the {entity.display_name.lower()} record",
                    "minimum": 1,
                },
                "field": {
                    "type": "string",
                    "description": "The file field name to remove from",
                },
                "file_position": {
                    "type": "integer",
                    "description": "Position of the file to remove (0-based, default 0)",
                    "default": 0,
                    "minimum": 0,
                },
            },
            "required": ["record_id", "field"],
        },
    ), "remove_attachment"


def _gen_attach_info_tool(entity: EntityConfig) -> Tuple[Tool, str]:
    return Tool(
        name=_tool_name("get_attachment_info", entity),
        description=(
            f"Get metadata about files attached to a {entity.display_name.lower()} record's "
            f"file field, including file names, sizes, and positions. "
            f"Use this before retrieve_attachment to find the correct file position."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "record_id": {
                    "type": "integer",
                    "description": f"The ID of the {entity.display_name.lower()} record",
                    "minimum": 1,
                },
                "field": {
                    "type": "string",
                    "description": "The file field name to get info for",
                },
            },
            "required": ["record_id", "field"],
        },
    ), "get_attachment_info"


def _gen_action_button_tool(entity: EntityConfig) -> Tuple[Tool, str]:
    return Tool(
        name=_tool_name("action_button", entity),
        description=(
            f"Trigger an action button on a {entity.display_name.lower()} record. "
            f"Executes the named workflow action button."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "record_id": {
                    "type": "integer",
                    "description": f"The ID of the {entity.display_name.lower()} record",
                    "minimum": 1,
                },
                "button_name": {
                    "type": "string",
                    "description": "Name of the action button to trigger",
                },
            },
            "required": ["record_id", "button_name"],
        },
    ), "action_button"


def _gen_evaluate_format_tool(entity: EntityConfig) -> Tuple[Tool, str]:
    return Tool(
        name=_tool_name("evaluate_format", entity),
        description=(
            f"Evaluate a formula/format expression against a {entity.display_name.lower()} record. "
            f"Returns the computed result."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "record_id": {
                    "type": "integer",
                    "description": f"The ID of the {entity.display_name.lower()} record",
                    "minimum": 1,
                },
                "formula": {
                    "type": "string",
                    "description": "Agiloft formula expression to evaluate",
                },
            },
            "required": ["record_id", "formula"],
        },
    ), "evaluate_format"


# Generator registry
_GENERATORS = {
    "search": _gen_search_tool,
    "get": _gen_get_tool,
    "create": _gen_create_tool,
    "update": _gen_update_tool,
    "delete": _gen_delete_tool,
    "upsert": _gen_upsert_tool,
    "attach_file": _gen_attach_file_tool,
    "retrieve_attachment": _gen_retrieve_attach_tool,
    "remove_attachment": _gen_remove_attach_tool,
    "get_attachment_info": _gen_attach_info_tool,
    "action_button": _gen_action_button_tool,
    "evaluate_format": _gen_evaluate_format_tool,
}


def generate_tools() -> Tuple[List[Tool], ToolDispatch]:
    """Generate all MCP tools and the dispatch mapping.

    Returns:
        Tuple of (list of Tool objects, dispatch dict: tool_name -> (entity_key, action))
    """
    tools: List[Tool] = []
    dispatch: ToolDispatch = {}

    for entity in ENTITY_REGISTRY.values():
        # P0: Core CRUD + Search
        ops = ["search", "get", "create", "update", "delete"]
        # P1: Upsert + Attachment operations
        ops += ["upsert"]
        if entity.supports_attach:
            ops += ["attach_file", "retrieve_attachment",
                    "remove_attachment", "get_attachment_info"]
        # P2: Action button + Evaluate format
        if entity.supports_action_button:
            ops.append("action_button")
        if entity.supports_evaluate_format:
            ops.append("evaluate_format")

        for op in ops:
            generator = _GENERATORS.get(op)
            if generator:
                tool, action = generator(entity)
                tools.append(tool)
                dispatch[tool.name] = (entity.key, action)

    return tools, dispatch
