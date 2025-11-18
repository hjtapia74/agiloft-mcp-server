# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an Agiloft Model Context Protocol (MCP) server that provides tools for interacting with Agiloft's REST API. The server enables AI assistants to perform contract CRUD operations and search functionality through the MCP framework.

## Architecture

The codebase follows a clean, modular architecture:

- **`src/server.py`**: Main MCP server implementation using the `mcp` framework. Defines 5 MCP tools for contract operations and handles tool execution through async handlers.
- **`src/agiloft_client.py`**: Agiloft REST API client with automatic token management. Handles authentication, session management, and 15-minute token refresh cycles.
- **`src/config.py`**: Configuration manager supporting environment variables, JSON config files, and defaults with dot-notation access.

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
# Test the Agiloft client functionality
python test_script.py

# Run the MCP server (stdio mode)
python src/server.py

# Install dependencies
pip install -r requirements.txt
```

### Linting and Code Quality
```bash
# Format code
black src/ test_script.py

# Lint code  
flake8 src/ test_script.py

# Run unit tests
PYTHONPATH=. python -m pytest tests/ -v

# Run specific test modules
PYTHONPATH=. python -m pytest tests/test_config.py -v
PYTHONPATH=. python -m pytest tests/test_exceptions.py -v
```

## MCP Tools Available

1. **agiloft_search_contracts**: Search contracts using natural language or structured queries
2. **agiloft_get_contract**: Retrieve specific contract by ID with optional field filtering
3. **agiloft_create_contract**: Create new contracts with validation
4. **agiloft_update_contract**: Update existing contract fields
5. **agiloft_delete_contract**: Delete contracts with configurable delete rules

## Key Technical Details

- **Authentication**: Uses Bearer tokens with automatic refresh 1 minute before expiration
- **Session Management**: Async context manager pattern with proper resource cleanup
- **Error Handling**: Custom exception hierarchy (`AgiloftError`, `AgiloftAuthError`, `AgiloftAPIError`, `AgiloftConfigError`) with enhanced error context including URLs, status codes, and response details
- **Configuration**: Supports both file-based and environment variable configuration with validation
- **Async Architecture**: Fully async/await based using aiohttp and asyncio
- **Testing**: Comprehensive unit test suite with pytest, including async test support and mocking

## Testing Strategy

Use `test_script.py` to validate functionality before MCP integration:
- Authentication testing
- Contract search operations
- CRUD operations with confirmation prompts
- Comprehensive error reporting

The test script requires valid Agiloft credentials and will perform read operations by default, with optional write operations requiring user confirmation.