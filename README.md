# Agiloft MCP Server

A Model Context Protocol (MCP) server for interacting with Agiloft's REST API. This server enables AI assistants to perform contract CRUD operations and search functionality through the MCP framework.

## Features

- **5 MCP Tools** for contract operations:
  - Search contracts with natural language or structured queries
  - Retrieve specific contracts by ID
  - Create new contracts
  - Update existing contracts
  - Delete contracts with configurable rules

- **Automatic Authentication Management**:
  - Bearer token authentication with automatic refresh
  - 15-minute token lifecycle with proactive refresh (1 minute before expiration)
  - Automatic retry on 401 errors

- **Robust Architecture**:
  - Fully async/await based using `aiohttp` and `asyncio`
  - Comprehensive error handling with custom exception hierarchy
  - Configurable via environment variables or JSON config file
  - Extensive logging for debugging and monitoring

## Installation

### Prerequisites

- Python 3.8 or higher
- Access to an Agiloft instance with REST API enabled
- Agiloft credentials (username, password, knowledge base name)

### Setup

1. Clone the repository:
```bash
git clone https://github.com/hjtapia74/agiloft-mcp-server.git
cd agiloft-mcp-server
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure the server (choose one method):

   **Option A: Environment Variables**
   ```bash
   export AGILOFT_BASE_URL="https://your-instance.saas.agiloft.com/ewws/alrest/YourKB"
   export AGILOFT_USERNAME="your-username"
   export AGILOFT_PASSWORD="your-password"
   export AGILOFT_KB="YourKB"
   ```

   **Option B: Configuration File**
   ```bash
   cp example_config.json config.json
   # Edit config.json with your credentials
   ```

## Configuration

Configuration follows priority order: **Environment variables > config.json > defaults**

### Required Configuration

| Parameter | Environment Variable | Description |
|-----------|---------------------|-------------|
| `agiloft.base_url` | `AGILOFT_BASE_URL` | Base URL for your Agiloft instance |
| `agiloft.username` | `AGILOFT_USERNAME` | Login username |
| `agiloft.password` | `AGILOFT_PASSWORD` | Login password |
| `agiloft.kb` | `AGILOFT_KB` | Knowledge base name |

### Optional Configuration

| Parameter | Environment Variable | Default | Description |
|-----------|---------------------|---------|-------------|
| `agiloft.language` | `AGILOFT_LANGUAGE` | `en` | Language code |
| `server.log_level` | `MCP_LOG_LEVEL` | `INFO` | Logging level |
| `server.timeout` | `MCP_TIMEOUT` | `30` | HTTP timeout (seconds) |
| `server.max_retries` | `MCP_MAX_RETRIES` | `3` | Max API retries |

## Usage

### Running the MCP Server

```bash
python src/server.py
```

The server runs in stdio mode and communicates via standard input/output, making it compatible with MCP clients.

### Testing the Agiloft Client

Test the client functionality independently:

```bash
python test_script.py
```

This script tests:
- Authentication
- Contract search operations
- CRUD operations (with confirmation prompts)

### Running Tests

```bash
# Run all tests
PYTHONPATH=. python -m pytest tests/ -v

# Run specific test modules
PYTHONPATH=. python -m pytest tests/test_config.py -v
PYTHONPATH=. python -m pytest tests/test_agiloft_client.py -v
```

### Code Quality

```bash
# Format code
black src/ test_script.py

# Lint code
flake8 src/ test_script.py
```

## Available MCP Tools

### 1. agiloft_search_contracts

Search for contracts using natural language or structured queries.

**Parameters:**
- `query` (required): Search query - natural language text or structured syntax
- `fields` (optional): Specific fields to return (defaults to essential fields)
- `limit` (optional): Maximum results (default: 50)

**Examples:**
```javascript
// Natural language
{"query": "contracts ending this year"}

// Structured query
{"query": "status=Active AND contract_amount>1000000"}
```

### 2. agiloft_get_contract

Retrieve a specific contract by ID.

**Parameters:**
- `contract_id` (required): The contract ID
- `fields` (optional): Specific fields to return

### 3. agiloft_create_contract

Create a new contract.

**Parameters:**
- `contract_data` (required): Object with contract fields

**Example:**
```javascript
{
  "contract_data": {
    "contract_title1": "Software License Agreement",
    "company_name": "Acme Corp",
    "contract_amount": 50000,
    "contract_start_date": "2025-01-01",
    "contract_end_date": "2025-12-31"
  }
}
```

### 4. agiloft_update_contract

Update an existing contract.

**Parameters:**
- `contract_id` (required): The contract ID to update
- `contract_data` (required): Object with fields to update

### 5. agiloft_delete_contract

Delete a contract.

**Parameters:**
- `contract_id` (required): The contract ID to delete
- `delete_rule` (optional): Delete strategy (default: `UNLINK_WHERE_POSSIBLE_OTHERWISE_DELETE`)

**Delete Rules:**
- `ERROR_IF_DEPENDANTS`: Fail if dependencies exist
- `APPLY_DELETE_WHERE_POSSIBLE`: Delete where possible
- `DELETE_WHERE_POSSIBLE_OTHERWISE_UNLINK`: Try delete, fallback to unlink
- `UNLINK_WHERE_POSSIBLE_OTHERWISE_DELETE`: Try unlink, fallback to delete

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────┐
│                    MCP Client (AI)                      │
└─────────────────────────┬───────────────────────────────┘
                          │ stdio
┌─────────────────────────▼───────────────────────────────┐
│              src/server.py (MCP Server)                 │
│  - Tool registration and routing                        │
│  - Request/response handling                            │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│         src/agiloft_client.py (API Client)              │
│  - Authentication & token management                    │
│  - HTTP request handling                                │
│  - Automatic retry logic                                │
└─────────────────────────┬───────────────────────────────┘
                          │ HTTPS
┌─────────────────────────▼───────────────────────────────┐
│              Agiloft REST API                           │
└─────────────────────────────────────────────────────────┘
```

### File Structure

```
agiloft-mcp-server/
├── src/
│   ├── __init__.py
│   ├── server.py              # MCP server implementation
│   ├── agiloft_client.py      # Agiloft API client
│   ├── config.py              # Configuration manager
│   └── exceptions.py          # Custom exceptions
├── tests/
│   ├── test_server.py
│   ├── test_agiloft_client.py
│   ├── test_config.py
│   └── test_exceptions.py
├── test_script.py             # Manual testing script
├── run_server.py              # Server launcher
├── requirements.txt           # Python dependencies
├── config.json                # Configuration (not in git)
├── example_config.json        # Configuration template
└── README.md
```

## Error Handling

The server includes custom exception classes for better error handling:

- `AgiloftError`: Base exception for all Agiloft-related errors
- `AgiloftAuthError`: Authentication failures
- `AgiloftAPIError`: API request/response errors (includes status codes and response text)
- `AgiloftConfigError`: Configuration issues

All errors are logged with comprehensive context for debugging.

## Security Considerations

- **Never commit `config.json`** - it's excluded in `.gitignore`
- Use environment variables for credentials in production
- Tokens are automatically managed and refreshed
- Passwords are masked in log output

## Contributing

Contributions are welcome! Please ensure:

1. Code follows existing style (use `black` for formatting)
2. All tests pass (`pytest tests/`)
3. New features include tests
4. Update documentation as needed

## License

[Add your license here]

## Support

For issues and questions:
- Open an issue on GitHub
- Review the `CLAUDE.md` file for development guidelines

## Acknowledgments

Built with:
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
- [Agiloft REST API](https://agiloft.com/)
- Python aiohttp, asyncio, and pytest
