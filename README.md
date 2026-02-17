# Agiloft MCP Server

A Model Context Protocol (MCP) server for interacting with Agiloft's REST API. This server enables AI assistants to perform CRUD operations, search, upsert, attachment management, and workflow actions across multiple Agiloft entities through a generic, table-driven architecture.

## Features

- **72 MCP Tools** across 6 entities with 12 operations each:
  - **Entities**: Contract, Company, Attachment, Contact, Employee, Customer
  - **Operations**: Search, Get, Create, Update, Delete, Upsert, Attach File, Retrieve Attachment, Remove Attachment, Get Attachment Info, Action Button, Evaluate Format

- **Automatic Authentication Management**:
  - Bearer token authentication with automatic refresh
  - 15-minute token lifecycle with proactive refresh (1 minute before expiration)
  - Automatic retry on 401 errors

- **Table-Driven Architecture**:
  - Adding a new entity requires only a single registry entry (~30 lines) — no other files change
  - Adding a new operation applies to all entities automatically
  - Generic client methods with backward-compatible contract wrappers

- **Robust Design**:
  - Fully async/await based using `aiohttp` and `asyncio`
  - Comprehensive error handling with custom exception hierarchy
  - Empty value stripping to prevent linked field validation errors
  - Multi-field text search with deduplication
  - Configurable via environment variables or JSON config file

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
python run_server.py
```

The server runs in stdio mode and communicates via standard input/output, making it compatible with MCP clients.

### Claude Desktop Integration

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "agiloft": {
      "command": "python",
      "args": ["/path/to/agiloft-mcp-server/run_server.py"],
      "env": {
        "AGILOFT_PASSWORD": "your-password"
      }
    }
  }
}
```

Claude Desktop will start and manage the server automatically.

### MCP Inspector (Interactive Testing)

```bash
npx @modelcontextprotocol/inspector python src/server.py
```

Opens a web UI to browse all 72 tools, view schemas, and invoke them manually.

### Running Tests

```bash
# Run all tests (123 tests)
PYTHONPATH=. python -m pytest tests/ -v

# Run specific test modules
PYTHONPATH=. python -m pytest tests/test_entity_registry.py -v
PYTHONPATH=. python -m pytest tests/test_tool_generator.py -v
PYTHONPATH=. python -m pytest tests/test_server.py -v
```

### Code Quality

```bash
# Format code
black src/ test_script.py

# Lint code
flake8 src/ test_script.py
```

## Supported Entities & Tools

### Tool Naming Convention

- **Singular** for single-record operations: `agiloft_get_contract`, `agiloft_create_company`
- **Plural** for search: `agiloft_search_contracts`, `agiloft_search_companies`
- **Pattern**: `agiloft_{operation}_{entity}`

### Tools Per Entity (12 each)

| Operation | Tool Example | Description |
|-----------|-------------|-------------|
| `search` | `agiloft_search_contracts` | Search with structured queries or text |
| `get` | `agiloft_get_contract` | Retrieve a record by ID |
| `create` | `agiloft_create_contract` | Create a new record |
| `update` | `agiloft_update_contract` | Update an existing record |
| `delete` | `agiloft_delete_contract` | Delete a record |
| `upsert` | `agiloft_upsert_contract` | Insert or update based on a match query |
| `attach_file` | `agiloft_attach_file_contract` | Upload a file attachment |
| `retrieve_attachment` | `agiloft_retrieve_attachment_contract` | Download an attachment |
| `remove_attachment` | `agiloft_remove_attachment_contract` | Remove an attachment |
| `get_attachment_info` | `agiloft_get_attachment_info_contract` | Get attachment metadata |
| `action_button` | `agiloft_action_button_contract` | Trigger a workflow action button |
| `evaluate_format` | `agiloft_evaluate_format_contract` | Evaluate a formula against a record |

### Entity Details

| Entity | API Path | Key Required Fields |
|--------|----------|-------------------|
| Contract | `/contract` | `record_type`, `auto_renewal_term_in_months`, `confidential`, `evaluation_frequency` |
| Company | `/company` | `company_name`, `type_of_company`, `status` |
| Attachment | `/attachment` | `attached_file`, `title`, `status`, `expiration_date` |
| Contact | `/contacts` | `sso_auth_method` |
| Employee | `/contacts.employees` | `_login`, `password`, `sso_auth_method` |
| Customer | `/contacts.customer` | `_login`, `password`, `sso_auth_method` |

### Search Examples

```javascript
// Text search (uses ~= partial match across text fields)
{"query": "Iverson"}

// Structured query
{"query": "wfstate=Active"}

// With field selection and limit
{"query": "contract_amount>50000", "fields": ["id", "contract_title1", "contract_amount"], "limit": 10}
```

### Create Example

Linked fields (like `company_name`, `contract_type`) require a colon prefix:

```javascript
{
  "data": {
    "record_type": "Contract",
    "confidential": "No",
    "evaluation_frequency": 0,
    "auto_renewal_term_in_months": 0,
    "contract_title1": "Software License Agreement",
    "company_name": ":Acme Corp",
    "contract_type": ":Services Agreement",
    "contract_amount": "50000"
  }
}
```

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────┐
│                    MCP Client (AI)                       │
└─────────────────────────┬───────────────────────────────┘
                          │ stdio
┌─────────────────────────▼───────────────────────────────┐
│              src/server.py (MCP Server)                  │
│  - Thin orchestrator (~50 lines)                        │
│  - Calls generate_tools() and dispatch_tool_call()      │
└────────────┬────────────────────────────┬───────────────┘
             │                            │
┌────────────▼──────────┐  ┌──────────────▼───────────────┐
│  src/tool_generator.py │  │   src/tool_handlers.py       │
│  - Generates 72 Tool   │  │   - Generic dispatch          │
│    definitions from     │  │   - Per-operation handlers    │
│    entity registry      │  │   - Query building            │
└────────────┬──────────┘  └──────────────┬───────────────┘
             │                            │
┌────────────▼────────────────────────────▼───────────────┐
│            src/entity_registry.py                        │
│  - EntityConfig dataclass per entity                     │
│  - Key fields, search fields, required fields            │
│  - Operation support flags                               │
└─────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│         src/agiloft_client.py (API Client)               │
│  - Generic entity-agnostic methods                       │
│  - Authentication & token management                     │
│  - Backward-compatible contract wrappers                 │
└─────────────────────────┬───────────────────────────────┘
                          │ HTTPS
┌─────────────────────────▼───────────────────────────────┐
│              Agiloft REST API                            │
└─────────────────────────────────────────────────────────┘
```

### File Structure

```
agiloft-mcp-server/
├── src/
│   ├── __init__.py
│   ├── server.py              # MCP server (thin orchestrator)
│   ├── agiloft_client.py      # Generic API client
│   ├── entity_registry.py     # Entity configs & registry
│   ├── tool_generator.py      # MCP Tool schema generation
│   ├── tool_handlers.py       # Generic tool dispatch & handlers
│   ├── config.py              # Configuration manager
│   └── exceptions.py          # Custom exceptions
├── tests/
│   ├── test_server.py         # Handler & dispatch tests
│   ├── test_agiloft_client.py # Client method tests
│   ├── test_entity_registry.py # Registry validation tests
│   ├── test_tool_generator.py # Tool generation tests
│   ├── test_config.py         # Config tests
│   └── test_exceptions.py     # Exception tests
├── run_server.py              # Server launcher (use this)
├── test_script.py             # Manual integration testing
├── requirements.txt           # Python dependencies
├── config.json                # Configuration (not in git)
├── example_config.json        # Configuration template
├── CLAUDE.md                  # Development guidelines
└── README.md
```

### Adding a New Entity

Add a single `EntityConfig` entry to `src/entity_registry.py`:

```python
"new_entity": EntityConfig(
    key="new_entity",
    key_plural="new_entities",
    api_path="/new_entity",
    display_name="New Entity",
    display_name_plural="New Entities",
    text_search_fields=["name_field"],
    key_fields={
        "name_field": {"type": "string", "description": "Name (REQUIRED)"},
        # ... more fields
    },
    default_search_fields=["id", "name_field"],
    required_fields=["name_field"],
),
```

No other files need to change. The tool generator and handlers pick it up automatically.

## Agiloft API Notes

- **Linked fields** require a colon prefix: `:Services Agreement`, `:Iverson, Inc.`
- **Text search** uses the `~=` operator (partial match), not `LIKE`
- **Contract status** field is `wfstate`, not `status`
- **Empty strings** on linked fields cause validation errors (handled automatically)

## Error Handling

Custom exception classes for structured error handling:

- `AgiloftError`: Base exception for all Agiloft-related errors
- `AgiloftAuthError`: Authentication failures
- `AgiloftAPIError`: API request/response errors (includes status codes and response text)
- `AgiloftConfigError`: Configuration issues

## Security Considerations

- **Never commit `config.json`** — it's excluded in `.gitignore`
- Use environment variables for credentials in production
- Tokens are automatically managed and refreshed

## License

[Add your license here]

## Acknowledgments

Built with:
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
- [Agiloft REST API](https://agiloft.com/)
- Python aiohttp, asyncio, and pytest
