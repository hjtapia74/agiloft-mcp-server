"""
Composite Workflow Tool Generator

Generates MCP Tool definitions for higher-level business workflow tools
that chain multiple API calls in a single invocation. These complement
the granular CRUD tools from tool_generator.py.
"""

from typing import Dict, List, Tuple

from mcp.types import Tool

# Type alias matching tool_generator.py pattern
WorkflowDispatch = Dict[str, str]  # tool_name -> handler_name


def generate_workflow_tools() -> Tuple[List[Tool], WorkflowDispatch]:
    """Generate composite workflow tools and dispatch mapping.

    Returns:
        Tuple of (list of Tool objects, dispatch dict: tool_name -> handler_name)
    """
    tools: List[Tool] = []
    dispatch: WorkflowDispatch = {}

    for tool, handler_name in _ALL_WORKFLOW_TOOLS:
        tools.append(tool)
        dispatch[tool.name] = handler_name

    return tools, dispatch


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

_PREFLIGHT_CREATE_CONTRACT = Tool(
    name="agiloft_preflight_create_contract",
    description=(
        "Validate contract creation prerequisites WITHOUT creating anything. "
        "Checks contract type availability, company existence, and type compatibility. "
        "Returns ready_to_create status, required fields, warnings, and next steps."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "contract_type": {
                "type": "string",
                "description": (
                    "Contract type name to validate (e.g. 'Master Services Agreement'). "
                    "If omitted, returns all active contract types for selection."
                ),
            },
            "company_name": {
                "type": "string",
                "description": (
                    "Company name to validate. If provided, checks existence and "
                    "type compatibility with the selected contract type."
                ),
            },
        },
        "required": [],
    },
)

_CREATE_CONTRACT_WITH_COMPANY = Tool(
    name="agiloft_create_contract_with_company",
    description=(
        "Create a contract with automatic company resolution. "
        "Searches for the company by name, optionally creates it if missing, "
        "then creates the contract. Returns the created contract and company details."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "contract_data": {
                "type": "object",
                "description": (
                    "Contract fields to create. Must include record_type, "
                    "auto_renewal_term_in_months, confidential, evaluation_frequency. "
                    "company_name will be set from the resolved company."
                ),
                "additionalProperties": True,
            },
            "company_name": {
                "type": "string",
                "description": "Company name to search for and link to the contract",
            },
            "create_company_if_missing": {
                "type": "boolean",
                "description": "Create the company if it doesn't exist (default false)",
                "default": False,
            },
            "company_data": {
                "type": "object",
                "description": (
                    "Company data for creation if create_company_if_missing is true. "
                    "Must include type_of_company and status if creating."
                ),
                "additionalProperties": True,
            },
        },
        "required": ["contract_data", "company_name"],
    },
)

_GET_CONTRACT_SUMMARY = Tool(
    name="agiloft_get_contract_summary",
    description=(
        "Get a comprehensive contract summary in one call. "
        "Retrieves the contract, associated company details, and attachment count. "
        "Returns an enriched view with all related information."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "contract_id": {
                "type": "integer",
                "description": "The ID of the contract to summarize",
                "minimum": 1,
            },
        },
        "required": ["contract_id"],
    },
)

_FIND_EXPIRING_CONTRACTS = Tool(
    name="agiloft_find_expiring_contracts",
    description=(
        "Find contracts expiring within a date range. "
        "Returns contracts with enriched urgency categories "
        "(URGENT/UPCOMING/PLANNING) and renewal recommendations."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "days_from_now": {
                "type": "integer",
                "description": "Number of days from today to search for expiring contracts",
                "minimum": 1,
                "default": 90,
            },
            "include_expired": {
                "type": "boolean",
                "description": "Include already-expired contracts (default false)",
                "default": False,
            },
            "status_filter": {
                "type": "string",
                "description": (
                    "Filter by contract status/wfstate (e.g. 'Active'). "
                    "If omitted, returns all statuses."
                ),
            },
        },
        "required": [],
    },
)

_ONBOARD_COMPANY_WITH_CONTACT = Tool(
    name="agiloft_onboard_company_with_contact",
    description=(
        "Onboard a company with an optional primary contact in one operation. "
        "Checks if the company exists first, creates it if needed, "
        "then creates the contact linked to the company."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "company_data": {
                "type": "object",
                "description": (
                    "Company fields. Must include company_name, type_of_company, status."
                ),
                "properties": {
                    "company_name": {
                        "type": "string",
                        "description": "Company name (required)",
                    },
                    "type_of_company": {
                        "type": "string",
                        "description": "Type of company (required - e.g. Customer, Vendor)",
                    },
                    "status": {
                        "type": "string",
                        "description": "Company status (required - e.g. Active)",
                    },
                },
                "additionalProperties": True,
            },
            "contact_data": {
                "type": "object",
                "description": (
                    "Contact fields for the primary contact. "
                    "company_name will be auto-linked. "
                    "If omitted, only the company is created."
                ),
                "properties": {
                    "first_name": {"type": "string", "description": "First name"},
                    "last_name": {"type": "string", "description": "Last name"},
                    "email": {"type": "string", "description": "Email address"},
                    "title": {"type": "string", "description": "Job title"},
                },
                "additionalProperties": True,
            },
            "skip_if_exists": {
                "type": "boolean",
                "description": (
                    "If true and company already exists, skip creation and return "
                    "existing record. If false (default), return an error."
                ),
                "default": False,
            },
        },
        "required": ["company_data"],
    },
)

_ATTACH_FILE_TO_CONTRACT = Tool(
    name="agiloft_attach_file_to_contract",
    description=(
        "Upload a file attachment to a contract. This is the CORRECT way to attach "
        "files to contracts in Agiloft. DO NOT use agiloft_attach_file_contract "
        "(which tries to attach directly to the contract table and will fail). "
        "This tool creates an Attachment record linked to the contract, then "
        "uploads the file to it. Returns the new attachment ID and file info. "
        "CRITICAL: file_path MUST be an absolute path on the local macOS filesystem "
        "(e.g. '/Users/jane/Downloads/contract.pdf'). Do NOT use sandbox paths "
        "like /mnt/, /home/claude/, or /tmp/. Do NOT try to encode the file to base64. "
        "If you do not know the local file path, ASK THE USER for it."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "contract_id": {
                "type": "integer",
                "description": "The ID of the contract to attach the file to",
                "minimum": 1,
            },
            "file_path": {
                "type": "string",
                "description": (
                    "REQUIRED. Absolute path to the file on the local macOS filesystem. "
                    "Must start with /Users/. Example: '/Users/hector/Downloads/contract.pdf'. "
                    "The MCP server reads the file directly from disk. "
                    "Do NOT use sandbox paths (/mnt/, /home/claude/, /tmp/sandbox/). "
                    "If you don't have the real file path, ask the user."
                ),
            },
            "file_name": {
                "type": "string",
                "description": (
                    "Name for the uploaded file (e.g. 'contract.pdf'). "
                    "If omitted, uses the filename from file_path."
                ),
            },
            "attachment_title": {
                "type": "string",
                "description": (
                    "Title for the attachment record (optional - defaults to file_name)"
                ),
            },
        },
        "required": ["contract_id", "file_path"],
    },
)

# Master list: (Tool, handler_name)
_ALL_WORKFLOW_TOOLS = [
    (_PREFLIGHT_CREATE_CONTRACT, "preflight_create_contract"),
    (_CREATE_CONTRACT_WITH_COMPANY, "create_contract_with_company"),
    (_GET_CONTRACT_SUMMARY, "get_contract_summary"),
    (_FIND_EXPIRING_CONTRACTS, "find_expiring_contracts"),
    (_ONBOARD_COMPANY_WITH_CONTACT, "onboard_company_with_contact"),
    (_ATTACH_FILE_TO_CONTRACT, "attach_file_to_contract"),
]
