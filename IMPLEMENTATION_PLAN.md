# Agiloft MCP Server - Entity Operations Expansion Plan

## Executive Summary

Expand the Agiloft MCP server from 5 contract-only tools to a **generic, table-driven architecture** supporting 6 entities across 12 operation types, yielding ~50 MCP tools. The design avoids per-entity code duplication by using entity registry configuration and a single generic client/handler layer.

---

## 1. Current State Analysis

### What exists today
- **5 hardcoded MCP tools**: `agiloft_search_contracts`, `agiloft_get_contract`, `agiloft_create_contract`, `agiloft_update_contract`, `agiloft_delete_contract`
- **Contract-specific client methods** in `agiloft_client.py` (`search_contracts`, `get_contract`, `create_contract`, `update_contract`, `delete_contract`)
- **Per-tool handler functions** in `server.py` with an `if/elif` chain in `handle_call_tool`
- Total: ~300 lines in server.py, ~310 lines in agiloft_client.py

### Problems with current approach
1. Every new entity requires duplicating ~100 lines of handler code + ~80 lines of client code
2. Tool definitions are handcrafted JSON schemas inline — error-prone at scale
3. No attachment operations, no upsert, no actionButton/evaluateFormat
4. Search query construction has SQL injection concerns (string interpolation in `handle_search_contracts`)

---

## 2. Target Entities & Operations

### Entity Registry (6 entities)

| Entity Key | API Path | Request Schema | Data Schema | Property Count (Req/Data) |
|------------|----------|---------------|-------------|--------------------------|
| `contract` | `/contract` | `AL_Contract_Request` | `AL_Contract_Data` | 355 / 421 |
| `company` | `/company` | `AL_Company_Request` | `AL_Company_Data` | 118 / 143 |
| `attachment` | `/attachment` | `AL_Attachment_Request` | `AL_Attachment_Data` | 124 / 140 |
| `contact` | `/contacts` | `AL_Person_Request` | `AL_Person_Data` | 108 / 129 |
| `employee` | `/contacts.employees` | `AL_Person.Employee_Request` | `AL_Person.Employee_Data` | 154 / 182 |
| `customer` | `/contacts.customer` | `AL_Person.External_User_Request` | `AL_Person.External_User_Data` | 141 / 169 |

### Operations per Entity (12 types)

| Operation | HTTP Method | Path Pattern | Shared Schema | Priority |
|-----------|------------|--------------|---------------|----------|
| **create** | POST | `/{entity}` | Entity-specific Request | P0 |
| **get** | GET | `/{entity}/{id}` | — | P0 |
| **update** | PUT | `/{entity}/{id}` | Entity-specific Request | P0 |
| **delete** | DELETE | `/{entity}/{id}` | — | P0 |
| **search** | POST | `/{entity}/search` | `AL_Search_Request` | P0 |
| **upsert** | POST | `/{entity}/upsert` | `AL_Upsert_Request` + query param | P1 |
| **attach** | POST (multipart) | `/{entity}/attach/{id}` | file upload | P1 |
| **retrieve_attach** | POST | `/{entity}/retrieveAttach/{id}` | field + filePosition params | P1 |
| **remove_attach** | POST | `/{entity}/removeAttach/{id}` | field + filePosition params | P1 |
| **attach_info** | POST | `/{entity}/attachInfo/{id}` | field param | P1 |
| **action_button** | POST | `/{entity}/actionButton/{id}` | name param | P2 |
| **evaluate_format** | POST | `/{entity}/evaluateFormat/{id}` | `AL_EvaluateFormat_Request` | P2 |

**Total MCP tools**: 6 entities × 8 core ops (P0+P1) = 48 tools, + 12 P2 tools = **60 tools maximum** (P2 optional)

---

## 3. Architecture: Generic Table-Driven Design

### 3.1 Entity Registry (`src/entity_registry.py`) — NEW FILE

A single Python dict/dataclass defines everything the system needs to know about each entity:

```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional

@dataclass
class EntityConfig:
    """Configuration for a single Agiloft entity."""
    key: str                    # e.g., "contract"
    api_path: str               # e.g., "/contract"
    display_name: str           # e.g., "Contract" (for tool descriptions)
    display_name_plural: str    # e.g., "Contracts"

    # Key fields shown in tool schemas (for create/update hints)
    key_fields: Dict[str, dict]  # field_name -> {type, description}

    # Default fields returned by search
    default_search_fields: List[str]

    # Required fields for create (from OpenAPI spec)
    required_fields: List[str]

    # Whether this entity supports each operation type
    supports_attach: bool = True
    supports_action_button: bool = True
    supports_evaluate_format: bool = True

# The registry
ENTITY_REGISTRY: Dict[str, EntityConfig] = {
    "contract": EntityConfig(
        key="contract",
        api_path="/contract",
        display_name="Contract",
        display_name_plural="Contracts",
        key_fields={
            "record_type": {"type": "string", "description": "Contract record type (required)"},
            "contract_title1": {"type": "string", "description": "Contract title"},
            "company_name": {"type": "string", "description": "Associated company name"},
            "contract_amount": {"type": "number", "description": "Contract monetary amount"},
            "contract_start_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
            "contract_end_date": {"type": "string", "description": "End date (YYYY-MM-DD)"},
            "contract_term_in_months": {"type": "integer", "description": "Term length in months"},
            "internal_contract_owner": {"type": "string", "description": "Internal contract owner"},
            "contract_type": {"type": "string", "description": "Type of contract"},
            "contract_description": {"type": "string", "description": "Contract description"},
            "status": {"type": "string", "description": "Contract status"},
            "confidential": {"type": "string", "description": "Confidentiality level (required)"},
            "evaluation_frequency": {"type": "integer", "description": "Evaluation frequency (required)"},
            "auto_renewal_term_in_months": {"type": "integer", "description": "Auto-renewal term (required)"},
            "date_signed": {"type": "string", "description": "Date contract was signed"},
            "signer1_email": {"type": "string", "description": "Primary signer email"},
            "cost_center": {"type": "string", "description": "Cost center"},
            "annual_increase": {"type": "number", "description": "Annual increase percentage"},
        },
        default_search_fields=[
            "id", "record_type", "contract_title1", "company_name",
            "contract_amount", "contract_end_date", "internal_contract_owner",
            "date_signed", "status", "contract_type"
        ],
        required_fields=[
            "record_type", "auto_renewal_term_in_months", "confidential", "evaluation_frequency"
        ],
    ),
    "company": EntityConfig(
        key="company",
        api_path="/company",
        display_name="Company",
        display_name_plural="Companies",
        key_fields={
            "company_name": {"type": "string", "description": "Company name (required)"},
            "type_of_company": {"type": "string", "description": "Type of company (required)"},
            "status": {"type": "string", "description": "Company status (required)"},
            "industry": {"type": "string", "description": "Industry classification"},
            "parent_company_id": {"type": "string", "description": "Parent company ID"},
            "main_city": {"type": "string", "description": "Main office city"},
            "country": {"type": "string", "description": "Country"},
            "fax": {"type": "string", "description": "Fax number"},
            "account_rep": {"type": "string", "description": "Account representative"},
            "main_location_name": {"type": "string", "description": "Main location name"},
            "ongoing_notes": {"type": "string", "description": "Ongoing notes"},
        },
        default_search_fields=[
            "id", "company_name", "type_of_company", "status",
            "industry", "main_city", "country", "number_of_active_contracts"
        ],
        required_fields=["company_name", "type_of_company", "status"],
    ),
    "attachment": EntityConfig(
        key="attachment",
        api_path="/attachment",
        display_name="Attachment",
        display_name_plural="Attachments",
        key_fields={
            "title": {"type": "string", "description": "Attachment title (required)"},
            "status": {"type": "string", "description": "Attachment status (required)"},
            "attached_file": {"type": "string", "description": "Attached file reference (required)"},
            "expiration_date": {"type": "string", "description": "Expiration date (required)"},
            "attachment_type": {"type": "string", "description": "Type of attachment"},
            "contract_id": {"type": "string", "description": "Associated contract ID"},
            "document_source": {"type": "string", "description": "Document source"},
            "contract_type": {"type": "string", "description": "Associated contract type"},
            "sorting_order": {"type": "number", "description": "Display sorting order"},
            "include_in_approval_packet": {"type": "string", "description": "Include in approval packet flag"},
        },
        default_search_fields=[
            "id", "title", "status", "attachment_type", "contract_id",
            "expiration_date", "document_source", "sorting_order"
        ],
        required_fields=["attached_file", "title", "status", "expiration_date"],
    ),
    "contact": EntityConfig(
        key="contact",
        api_path="/contacts",
        display_name="Contact",
        display_name_plural="Contacts",
        key_fields={
            "first_name": {"type": "string", "description": "First name"},
            "last_name": {"type": "string", "description": "Last name"},
            "full_name": {"type": "string", "description": "Full name"},
            "email": {"type": "string", "description": "Email address"},
            "company_name": {"type": "array", "description": "Associated company names"},
            "company_id": {"type": "string", "description": "Associated company ID"},
            "status": {"type": "string", "description": "Contact status"},
            "type_of_contact": {"type": "string", "description": "Type of contact"},
            "direct_phone": {"type": "string", "description": "Direct phone number"},
            "cell_phone": {"type": "string", "description": "Cell phone number"},
            "title": {"type": "string", "description": "Job title"},
            "sso_auth_method": {"type": "string", "description": "SSO auth method (required)"},
        },
        default_search_fields=[
            "id", "full_name", "email", "company_name", "status",
            "type_of_contact", "direct_phone", "title"
        ],
        required_fields=["sso_auth_method"],
    ),
    "employee": EntityConfig(
        key="employee",
        api_path="/contacts.employees",
        display_name="Employee",
        display_name_plural="Employees",
        key_fields={
            "_login": {"type": "string", "description": "Login username (required)"},
            "password": {"type": "string", "description": "Password (required)"},
            "first_name": {"type": "string", "description": "First name"},
            "last_name": {"type": "string", "description": "Last name"},
            "full_name": {"type": "string", "description": "Full name"},
            "email": {"type": "string", "description": "Email address"},
            "company_name": {"type": "array", "description": "Associated company names"},
            "status": {"type": "string", "description": "Contact status"},
            "type_of_contact": {"type": "string", "description": "Type of contact"},
            "department0": {"type": "string", "description": "Department"},
            "title": {"type": "string", "description": "Job title"},
            "sso_auth_method": {"type": "string", "description": "SSO auth method (required)"},
            "preferred_interface": {"type": "string", "description": "Preferred UI interface"},
        },
        default_search_fields=[
            "id", "full_name", "email", "company_name", "status",
            "type_of_contact", "department0", "title", "_login"
        ],
        required_fields=["_login", "password", "sso_auth_method"],
    ),
    "customer": EntityConfig(
        key="customer",
        api_path="/contacts.customer",
        display_name="Customer Contact",
        display_name_plural="Customer Contacts",
        key_fields={
            "_login": {"type": "string", "description": "Login username (required)"},
            "password": {"type": "string", "description": "Password (required)"},
            "first_name": {"type": "string", "description": "First name"},
            "last_name": {"type": "string", "description": "Last name"},
            "full_name": {"type": "string", "description": "Full name"},
            "email": {"type": "string", "description": "Email address"},
            "company_name": {"type": "array", "description": "Associated company names"},
            "status": {"type": "string", "description": "Contact status"},
            "type_of_contact": {"type": "string", "description": "Type of contact"},
            "title": {"type": "string", "description": "Job title"},
            "sso_auth_method": {"type": "string", "description": "SSO auth method (required)"},
        },
        default_search_fields=[
            "id", "full_name", "email", "company_name", "status",
            "type_of_contact", "title", "_login"
        ],
        required_fields=["_login", "password", "sso_auth_method"],
    ),
}

def get_entity(key: str) -> EntityConfig:
    """Get entity config by key. Raises ValueError if not found."""
    if key not in ENTITY_REGISTRY:
        raise ValueError(f"Unknown entity: {key}. Valid entities: {list(ENTITY_REGISTRY.keys())}")
    return ENTITY_REGISTRY[key]
```

### 3.2 Generic Client (`src/agiloft_client.py`) — REFACTOR

Replace the 5 contract-specific methods with **generic entity methods**. The existing `_make_request` method is already entity-agnostic — we just need generic wrappers.

```python
# NEW generic methods (replace contract-specific methods)

async def search_records(self, entity_path: str, query: str = "",
                         fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Search records for any entity."""
    search_data = {
        "search": "",
        "field": fields or [],
        "query": query
    }
    response = await self._make_request("POST", f"{entity_path}/search", json=search_data)
    if not response.get('success', False):
        raise AgiloftAPIError(f"Search failed: {response.get('message', 'Unknown error')}")
    return response.get('result', [])

async def get_record(self, entity_path: str, record_id: int,
                     fields: Optional[List[str]] = None) -> Dict[str, Any]:
    """Get a specific record by ID for any entity."""
    params = {}
    if fields:
        params['fields'] = ','.join(fields)
    response = await self._make_request("GET", f"{entity_path}/{record_id}", params=params)
    # Handle multiple response formats (same logic as current get_contract)
    return self._extract_record(response, record_id)

async def create_record(self, entity_path: str,
                        data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a record for any entity."""
    response = await self._make_request("POST", entity_path, json=data)
    self._check_response(response, "Create")
    return response

async def update_record(self, entity_path: str, record_id: int,
                        data: Dict[str, Any]) -> Dict[str, Any]:
    """Update a record for any entity."""
    response = await self._make_request("PUT", f"{entity_path}/{record_id}", json=data)
    self._check_response(response, "Update")
    return response

async def delete_record(self, entity_path: str, record_id: int,
                        delete_rule: str = "UNLINK_WHERE_POSSIBLE_OTHERWISE_DELETE") -> Dict[str, Any]:
    """Delete a record for any entity."""
    params = {"deleteRule": delete_rule}
    response = await self._make_request("DELETE", f"{entity_path}/{record_id}", params=params)
    if not response.get('success', False):
        self._check_response(response, "Delete")
    return response

async def upsert_record(self, entity_path: str, query: str,
                        data: Dict[str, Any]) -> Dict[str, Any]:
    """Upsert (insert or update) a record for any entity.

    Args:
        entity_path: API path for the entity
        query: Match query in format fieldName~='value'
        data: Record data to insert/update
    """
    response = await self._make_request(
        "POST", f"{entity_path}/upsert",
        params={"query": query},
        json=data
    )
    self._check_response(response, "Upsert")
    return response

async def attach_file(self, entity_path: str, record_id: int,
                      field: str, file_name: str, file_data: bytes) -> Dict[str, Any]:
    """Attach a file to a record."""
    import aiohttp
    form_data = aiohttp.FormData()
    form_data.add_field('uploadFile', file_data, filename=file_name)
    params = {"field": field, "fileName": file_name}
    # Note: must NOT set Content-Type header — let aiohttp set multipart boundary
    response = await self._make_request(
        "POST", f"{entity_path}/attach/{record_id}",
        params=params, data=form_data,
        headers={"Content-Type": None}  # Override to let aiohttp set it
    )
    return response

async def retrieve_attachment(self, entity_path: str, record_id: int,
                              field: str, file_position: int = 0) -> Dict[str, Any]:
    """Retrieve an attachment from a record."""
    params = {"field": field, "filePosition": file_position}
    response = await self._make_request(
        "POST", f"{entity_path}/retrieveAttach/{record_id}", params=params
    )
    return response

async def remove_attachment(self, entity_path: str, record_id: int,
                            field: str, file_position: int = 0) -> Dict[str, Any]:
    """Remove an attachment from a record."""
    params = {"field": field, "filePosition": file_position}
    response = await self._make_request(
        "POST", f"{entity_path}/removeAttach/{record_id}", params=params
    )
    return response

async def get_attachment_info(self, entity_path: str, record_id: int,
                              field: str) -> Dict[str, Any]:
    """Get attachment metadata for a record."""
    params = {"field": field}
    response = await self._make_request(
        "POST", f"{entity_path}/attachInfo/{record_id}", params=params
    )
    return response

async def trigger_action_button(self, entity_path: str, record_id: int,
                                button_name: str) -> Dict[str, Any]:
    """Trigger an action button on a record."""
    params = {"name": button_name}
    response = await self._make_request(
        "POST", f"{entity_path}/actionButton/{record_id}", params=params
    )
    return response

async def evaluate_format(self, entity_path: str, record_id: int,
                          formula: str) -> Dict[str, Any]:
    """Evaluate a format/formula against a record."""
    response = await self._make_request(
        "POST", f"{entity_path}/evaluateFormat/{record_id}",
        json={"formula": formula}
    )
    return response
```

**Backward compatibility**: Keep the existing contract-specific methods as thin wrappers that delegate to the generic methods. This ensures existing code using `agiloft_client.search_contracts()` still works.

### 3.3 Generic Tool Generator (`src/tool_generator.py`) — NEW FILE

Dynamically generates MCP Tool definitions from the entity registry:

```python
from mcp.types import Tool
from entity_registry import ENTITY_REGISTRY, EntityConfig

def generate_tools_for_entity(entity: EntityConfig, operations: list[str]) -> list[Tool]:
    """Generate MCP Tool definitions for an entity based on requested operations."""
    tools = []

    generators = {
        "search": _gen_search_tool,
        "get": _gen_get_tool,
        "create": _gen_create_tool,
        "update": _gen_update_tool,
        "delete": _gen_delete_tool,
        "upsert": _gen_upsert_tool,
        "attach_file": _gen_attach_file_tool,
        "get_attachment_info": _gen_attach_info_tool,
        "retrieve_attachment": _gen_retrieve_attach_tool,
        "remove_attachment": _gen_remove_attach_tool,
        "action_button": _gen_action_button_tool,
        "evaluate_format": _gen_evaluate_format_tool,
    }

    for op in operations:
        if op in generators:
            tools.append(generators[op](entity))

    return tools

def generate_all_tools() -> list[Tool]:
    """Generate all MCP tools for all registered entities."""
    all_tools = []
    for entity in ENTITY_REGISTRY.values():
        # P0: Core CRUD + Search
        ops = ["search", "get", "create", "update", "delete"]
        # P1: Upsert + Attachment operations
        ops += ["upsert", "attach_file", "get_attachment_info",
                "retrieve_attachment", "remove_attachment"]
        # P2: Action button + Evaluate format
        if entity.supports_action_button:
            ops.append("action_button")
        if entity.supports_evaluate_format:
            ops.append("evaluate_format")
        all_tools.extend(generate_tools_for_entity(entity, ops))
    return all_tools
```

### 3.4 Generic Tool Handler (`src/tool_handlers.py`) — NEW FILE

A single dispatcher that routes any `agiloft_{action}_{entity}` tool call:

```python
async def handle_tool_call(name: str, arguments: dict, client: AgiloftClient) -> list[TextContent]:
    """Generic handler for all entity tool calls."""
    # Parse tool name: agiloft_{action}_{entity}
    entity_key, action = parse_tool_name(name)
    entity = get_entity(entity_key)

    handlers = {
        "search": handle_search,
        "get": handle_get,
        "create": handle_create,
        "update": handle_update,
        "delete": handle_delete,
        "upsert": handle_upsert,
        "attach_file": handle_attach_file,
        "get_attachment_info": handle_attachment_info,
        "retrieve_attachment": handle_retrieve_attachment,
        "remove_attachment": handle_remove_attachment,
        "action_button": handle_action_button,
        "evaluate_format": handle_evaluate_format,
    }

    handler = handlers.get(action)
    if not handler:
        raise ValueError(f"Unknown action: {action}")

    return await handler(entity, arguments, client)
```

---

## 4. MCP Tool Naming Convention

### Pattern: `agiloft_{action}_{entity}`

| Action | Tool Name Example | Description |
|--------|------------------|-------------|
| search | `agiloft_search_contracts` | Search records |
| get | `agiloft_get_contract` | Get record by ID |
| create | `agiloft_create_contract` | Create a new record |
| update | `agiloft_update_contract` | Update an existing record |
| delete | `agiloft_delete_contract` | Delete a record |
| upsert | `agiloft_upsert_contract` | Insert or update a record |
| attach_file | `agiloft_attach_file_contract` | Upload a file to a record |
| get_attachment_info | `agiloft_get_attachment_info_contract` | Get attachment metadata |
| retrieve_attachment | `agiloft_retrieve_attachment_contract` | Download an attachment |
| remove_attachment | `agiloft_remove_attachment_contract` | Remove an attachment |
| action_button | `agiloft_action_button_contract` | Trigger an action button |
| evaluate_format | `agiloft_evaluate_format_contract` | Evaluate a formula |

### Entity naming in tools

| Entity | Singular (get/create/update/delete) | Plural (search) |
|--------|-------------------------------------|-----------------|
| Contract | `contract` | `contracts` |
| Company | `company` | `companies` |
| Attachment | `attachment` | `attachments` |
| Contact | `contact` | `contacts` |
| Employee | `employee` | `employees` |
| Customer | `customer` | `customers` |

### Full tool list (48 P0+P1 tools)

**Contract (10)**: `agiloft_search_contracts`, `agiloft_get_contract`, `agiloft_create_contract`, `agiloft_update_contract`, `agiloft_delete_contract`, `agiloft_upsert_contract`, `agiloft_attach_file_contract`, `agiloft_get_attachment_info_contract`, `agiloft_retrieve_attachment_contract`, `agiloft_remove_attachment_contract`

**Company (10)**: `agiloft_search_companies`, `agiloft_get_company`, `agiloft_create_company`, `agiloft_update_company`, `agiloft_delete_company`, `agiloft_upsert_company`, `agiloft_attach_file_company`, `agiloft_get_attachment_info_company`, `agiloft_retrieve_attachment_company`, `agiloft_remove_attachment_company`

**Attachment (10)**: `agiloft_search_attachments`, `agiloft_get_attachment`, `agiloft_create_attachment`, `agiloft_update_attachment`, `agiloft_delete_attachment`, `agiloft_upsert_attachment`, `agiloft_attach_file_attachment`, `agiloft_get_attachment_info_attachment`, `agiloft_retrieve_attachment_attachment`, `agiloft_remove_attachment_attachment`

**Contact (10)**: `agiloft_search_contacts`, `agiloft_get_contact`, `agiloft_create_contact`, `agiloft_update_contact`, `agiloft_delete_contact`, `agiloft_upsert_contact`, `agiloft_attach_file_contact`, `agiloft_get_attachment_info_contact`, `agiloft_retrieve_attachment_contact`, `agiloft_remove_attachment_contact`

**Employee (10)**: `agiloft_search_employees`, `agiloft_get_employee`, `agiloft_create_employee`, `agiloft_update_employee`, `agiloft_delete_employee`, `agiloft_upsert_employee`, `agiloft_attach_file_employee`, `agiloft_get_attachment_info_employee`, `agiloft_retrieve_attachment_employee`, `agiloft_remove_attachment_employee`

**Customer (10)**: `agiloft_search_customers`, `agiloft_get_customer`, `agiloft_create_customer`, `agiloft_update_customer`, `agiloft_delete_customer`, `agiloft_upsert_customer`, `agiloft_attach_file_customer`, `agiloft_get_attachment_info_customer`, `agiloft_retrieve_attachment_customer`, `agiloft_remove_attachment_customer`

---

## 5. Handling Massive Schemas (355+ Properties)

### Strategy: Key Fields in Schema + Open `data` Object

The MCP tool `inputSchema` should NOT enumerate all 355+ contract properties. Instead:

1. **List 10-18 "key fields"** explicitly in the schema with descriptions — these guide the LLM on the most common fields
2. **Accept an open `data` object** that passes through any additional fields — the LLM can still set obscure fields by name
3. **Document required fields** clearly in the tool description

Example for `agiloft_create_contract`:
```json
{
  "type": "object",
  "properties": {
    "data": {
      "type": "object",
      "description": "Contract data. Key fields shown below; any valid Agiloft contract field can be included.",
      "properties": {
        "record_type": {"type": "string", "description": "Contract record type (REQUIRED)"},
        "contract_title1": {"type": "string", "description": "Contract title"},
        "company_name": {"type": "string", "description": "Company name"},
        "contract_amount": {"type": "number", "description": "Monetary amount"},
        "contract_start_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
        "contract_end_date": {"type": "string", "description": "End date (YYYY-MM-DD)"},
        "contract_term_in_months": {"type": "integer", "description": "Term in months"},
        "internal_contract_owner": {"type": "string", "description": "Internal owner"},
        "contract_type": {"type": "string", "description": "Contract type"},
        "status": {"type": "string", "description": "Contract status"},
        "confidential": {"type": "string", "description": "Confidentiality (REQUIRED)"},
        "auto_renewal_term_in_months": {"type": "integer", "description": "Auto-renewal term (REQUIRED)"},
        "evaluation_frequency": {"type": "integer", "description": "Eval frequency (REQUIRED)"}
      },
      "additionalProperties": true
    }
  },
  "required": ["data"]
}
```

This approach:
- Keeps tool schemas under 2KB (well within MCP limits)
- Gives LLMs enough context to construct valid requests
- Allows power users to pass any valid field
- Marks required fields clearly in descriptions

### Key fields per entity (curated for LLM usability)

**Contract** (18 key fields): `record_type`, `contract_title1`, `company_name`, `contract_amount`, `contract_start_date`, `contract_end_date`, `contract_term_in_months`, `internal_contract_owner`, `contract_type`, `contract_description`, `status`, `confidential`, `evaluation_frequency`, `auto_renewal_term_in_months`, `date_signed`, `signer1_email`, `cost_center`, `annual_increase`

**Company** (11 key fields): `company_name`, `type_of_company`, `status`, `industry`, `parent_company_id`, `main_city`, `country`, `fax`, `account_rep`, `main_location_name`, `ongoing_notes`

**Attachment** (10 key fields): `title`, `status`, `attached_file`, `expiration_date`, `attachment_type`, `contract_id`, `document_source`, `contract_type`, `sorting_order`, `include_in_approval_packet`

**Contact** (12 key fields): `first_name`, `last_name`, `full_name`, `email`, `company_name`, `company_id`, `status`, `type_of_contact`, `direct_phone`, `cell_phone`, `title`, `sso_auth_method`

**Employee** (13 key fields): `_login`, `password`, `first_name`, `last_name`, `full_name`, `email`, `company_name`, `status`, `type_of_contact`, `department0`, `title`, `sso_auth_method`, `preferred_interface`

**Customer** (11 key fields): `_login`, `password`, `first_name`, `last_name`, `full_name`, `email`, `company_name`, `status`, `type_of_contact`, `title`, `sso_auth_method`

---

## 6. Tool Descriptions for LLM Optimization

Tool descriptions must be clear, concise, and action-oriented. They should tell the LLM:
1. What the tool does
2. When to use it vs alternatives
3. Key constraints

Examples:

```
agiloft_search_contracts:
  "Search for contracts in Agiloft. Use structured queries like 'status=Active AND contract_amount>1000000'
   or text search against title and company fields. Returns matching contracts with key fields."

agiloft_upsert_contract:
  "Insert or update a contract. If a record matching the query exists, updates it; otherwise creates a new one.
   Query format: fieldName~='value' (e.g., salesforce_contract_id~='SF-12345')."

agiloft_attach_file_contract:
  "Upload a file attachment to a contract record. Requires the record ID, target field name (e.g., 'attached_file'),
   file name, and base64-encoded file content."

agiloft_get_attachment_info_contract:
  "Get metadata about files attached to a contract record's file field, including file names, sizes, and positions.
   Use this before retrieve_attachment to find the correct file position."
```

---

## 7. Phased Rollout

### Phase 1: Generic Infrastructure + Contract Parity (Week 1)
**Goal**: Refactor to generic architecture, maintain backward compatibility with existing 5 contract tools, add missing contract operations.

**Files to create/modify**:
- CREATE `src/entity_registry.py` — Entity configuration for `contract` only
- REFACTOR `src/agiloft_client.py` — Add generic methods, keep contract methods as wrappers
- CREATE `src/tool_generator.py` — Generate Tool definitions from registry
- CREATE `src/tool_handlers.py` — Generic tool dispatch and handlers
- REFACTOR `src/server.py` — Use tool_generator + tool_handlers, keep tool names identical

**New contract tools added**: `agiloft_upsert_contract`, `agiloft_attach_file_contract`, `agiloft_retrieve_attachment_contract`, `agiloft_remove_attachment_contract`, `agiloft_get_attachment_info_contract`

**Deliverable**: 10 contract tools (5 existing + 5 new), generic infrastructure in place

### Phase 2: Company + Attachment Entities (Week 2)
**Goal**: Add Company and Attachment entities using the generic infrastructure. Zero new handler code — just registry entries.

**Files to modify**:
- UPDATE `src/entity_registry.py` — Add `company` and `attachment` configs

**New tools**: 20 tools (10 company + 10 attachment)

**Deliverable**: 30 total tools across 3 entities

### Phase 3: Contact Entities (Week 3)
**Goal**: Add Contact, Employee, and Customer Contact entities.

**Files to modify**:
- UPDATE `src/entity_registry.py` — Add `contact`, `employee`, `customer` configs

**New tools**: 30 tools (10 per contact sub-type)

**Deliverable**: 60 total tools across 6 entities

### Phase 4: P2 Operations + Polish (Week 4)
**Goal**: Add actionButton and evaluateFormat operations, comprehensive testing, documentation.

**Files to modify**:
- UPDATE `src/tool_generator.py` — Add P2 tool generators
- UPDATE `src/tool_handlers.py` — Add P2 handlers

**New tools**: 12 tools (2 per entity)

**Deliverable**: Up to 72 total tools, full test coverage

---

## 8. File Structure

### Current structure:
```
src/
├── __init__.py
├── server.py          # MCP server + tool definitions + handlers (all in one)
├── agiloft_client.py  # Contract-specific API client
├── config.py          # Configuration manager
└── exceptions.py      # Custom exceptions
```

### Proposed structure:
```
src/
├── __init__.py
├── server.py              # MCP server setup + startup (thin orchestrator)
├── agiloft_client.py      # Generic API client (entity-agnostic methods)
├── config.py              # Configuration manager (unchanged)
├── exceptions.py          # Custom exceptions (unchanged)
├── entity_registry.py     # Entity configs + registry dict (NEW)
├── tool_generator.py      # MCP Tool schema generation from registry (NEW)
└── tool_handlers.py       # Generic tool dispatch + handler functions (NEW)
```

### Why this structure works
- **`server.py`** becomes a thin ~50-line orchestrator: create server, call `generate_all_tools()`, dispatch to `handle_tool_call()`
- **Adding a new entity** = add one `EntityConfig` entry to `entity_registry.py` (~30 lines) — no other files change
- **Adding a new operation** = add one generator in `tool_generator.py` + one handler in `tool_handlers.py` — applies to all entities automatically
- **Each file has a single responsibility**: registry knows entities, generator knows MCP schemas, handlers know API calls

---

## 9. Testing Strategy

### Unit tests for each new module:
- `tests/test_entity_registry.py` — Validate registry entries, key field coverage
- `tests/test_tool_generator.py` — Verify generated Tool schemas are valid MCP schemas
- `tests/test_tool_handlers.py` — Test handler dispatch, argument parsing, error handling (mocked client)
- `tests/test_agiloft_client_generic.py` — Test generic client methods (mocked HTTP)

### Integration test approach:
- Update `test_script.py` to cycle through all entities with read operations
- Add a `--entity` flag to test specific entities
- Keep write operations behind confirmation prompts

### Backward compatibility tests:
- Verify the 5 original tool names still work
- Verify existing `agiloft_client.search_contracts()` etc. still function

---

## 10. Key Design Decisions & Rationale

| Decision | Rationale |
|----------|-----------|
| Table-driven registry instead of class inheritance | Simpler, more explicit, easier to review entity configs at a glance |
| Keep contract-specific methods as wrappers | Backward compatibility for test_script.py and any external consumers |
| Open `additionalProperties: true` on data objects | 355+ fields can't all be in schema; LLMs can still use any field by name |
| Separate tool_generator.py from tool_handlers.py | Tool schema generation is a distinct concern from execution |
| Singular entity in tool names (get_contract, not get_contracts) | Matches REST convention — singular for single-record operations |
| Plural for search (search_contracts, not search_contract) | Search returns multiple records; plural reads naturally |
| `contacts.customer` maps to `customer` in tool names | The API path `contacts.customer` is an implementation detail; "customer" is the user-facing concept |
| Phase 1 maintains exact current tool names | Zero breaking changes for existing MCP clients |

---

## 11. Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| 60+ tools may slow MCP tool discovery | Group tools logically; consider lazy tool loading if MCP supports it |
| File upload (attach) requires multipart handling | Test thoroughly; aiohttp FormData handles this but needs Content-Type header override |
| Contact sub-types share similar fields | Registry makes differences explicit; test each sub-type independently |
| Massive OpenAPI spec may have undocumented quirks | Build against actual API behavior, not just spec; keep test_script.py updated |
| SQL injection in search queries | Phase 1 should fix the current string interpolation vulnerability in handle_search_contracts |

---

## Summary

This plan transforms the Agiloft MCP server from a 5-tool contract-only system to a **60+ tool multi-entity platform** through a generic, table-driven architecture. Adding a new entity requires only ~30 lines of registry configuration. The phased approach ensures backward compatibility while delivering incremental value each week.
