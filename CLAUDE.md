# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an Agiloft Model Context Protocol (MCP) server that provides 72 tools for interacting with Agiloft's REST API. The server uses a generic, table-driven architecture to support 6 entities (Contract, Company, Attachment, Contact, Employee, Customer) with 12 operations each.

## Architecture

The codebase follows a table-driven, modular architecture:

- **`src/server.py`**: Thin MCP server orchestrator (~50 lines). Calls `generate_tools()` at startup and dispatches to `dispatch_tool_call()`.
- **`src/entity_registry.py`**: `EntityConfig` dataclass and `ENTITY_REGISTRY` dict defining all 6 entities. Adding a new entity = adding one entry here, no other files change.
- **`src/tool_generator.py`**: Dynamically generates 72 MCP `Tool` definitions and a dispatch map from the entity registry.
- **`src/tool_handlers.py`**: Generic dispatch + per-operation handler functions. Handles query building, empty value stripping, and response formatting.
- **`src/agiloft_client.py`**: Generic entity-agnostic API client with backward-compatible contract wrappers. Manages authentication and token refresh.
- **`src/config.py`**: Configuration manager supporting environment variables, JSON config files, and defaults with dot-notation access.
- **`src/exceptions.py`**: Custom exception hierarchy.

## Agiloft API Quirks (Important)

- **Linked fields** require colon prefix: `:Services Agreement`, `:Iverson, Inc.`
- **Partial match** uses `~=` operator, NOT `LIKE` (LIKE is unreliable across tables)
- **`~=` with OR** does NOT work across different fields; search handler runs separate queries per text_search_field and merges by ID
- **`search` body field** returns 400 on all tables; only the `query` field works
- **Empty strings** on linked fields cause "does not allow extra values" errors; `_strip_empty_values()` handles this
- **Contract status** field is `wfstate`, not `status`

## Configuration

Configuration follows priority order: Environment variables > config.json > defaults

Required configuration:
- `agiloft.base_url`: Agiloft instance URL
- `agiloft.username`: Login username
- `agiloft.password`: Login password (use `AGILOFT_PASSWORD` env var)
- `agiloft.kb`: Knowledge base name

## Common Commands

### Development and Testing
```bash
# Run the MCP server (use this entry point)
python run_server.py

# Interactive testing with MCP Inspector
npx @modelcontextprotocol/inspector python src/server.py

# Test the Agiloft client functionality
python test_script.py

# Install dependencies
pip install -r requirements.txt
```

### Linting and Code Quality
```bash
# Format code
black src/ test_script.py

# Lint code
flake8 src/ test_script.py

# Run all unit tests (123 tests)
PYTHONPATH=. python -m pytest tests/ -v

# Run specific test modules
PYTHONPATH=. python -m pytest tests/test_entity_registry.py -v
PYTHONPATH=. python -m pytest tests/test_tool_generator.py -v
PYTHONPATH=. python -m pytest tests/test_server.py -v
PYTHONPATH=. python -m pytest tests/test_agiloft_client.py -v
```

## MCP Tools (72 total)

### 6 Entities
Contract, Company, Attachment, Contact, Employee, Customer

### 12 Operations Per Entity
search, get, create, update, delete, upsert, attach_file, retrieve_attachment, remove_attachment, get_attachment_info, action_button, evaluate_format

### Tool Naming
- Singular for single-record ops: `agiloft_get_contract`
- Plural for search: `agiloft_search_contracts`
- Pattern: `agiloft_{operation}_{entity}`

## Key Technical Details

- **Authentication**: Uses Bearer tokens with automatic refresh 1 minute before expiration
- **Session Management**: Async context manager pattern with proper resource cleanup
- **Error Handling**: Custom exception hierarchy (`AgiloftError`, `AgiloftAuthError`, `AgiloftAPIError`, `AgiloftConfigError`) with enhanced error context
- **Configuration**: Supports both file-based and environment variable configuration with validation
- **Async Architecture**: Fully async/await based using aiohttp and asyncio
- **Testing**: 123 unit tests with pytest, including async test support and mocking

## Testing Strategy

- **Unit tests** (`tests/`): Mocked HTTP, covers registry, tool generation, handlers, client, config, exceptions
- **MCP Inspector**: Interactive browser-based testing against live Agiloft
- **test_script.py**: Integration testing against live Agiloft with confirmation prompts for writes
- **OpenAPI spec**: `AgiloftOpenAPIJSON.json` (gitignored) used for field validation
