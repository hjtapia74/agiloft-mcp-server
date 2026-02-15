"""
Agiloft Entity Registry

Defines entity configurations for the MCP server. Each entity maps to an
Agiloft API resource with its metadata, key fields, and operation support.

To add a new entity, add an EntityConfig entry to ENTITY_REGISTRY.
No other files need to change.
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class EntityConfig:
    """Configuration for a single Agiloft entity."""
    key: str                        # Internal key: "contract"
    key_plural: str                 # Plural form for tool names: "contracts"
    api_path: str                   # API path: "/contract"
    display_name: str               # Human-readable: "Contract"
    display_name_plural: str        # Human-readable plural: "Contracts"

    # Key fields shown in tool schemas (field_name -> {type, description})
    key_fields: Dict[str, dict]

    # Default fields returned by search
    default_search_fields: List[str]

    # Required fields for create operations
    required_fields: List[str]

    # Fields to search with LIKE when query is natural language
    text_search_fields: List[str] = field(default_factory=list)

    # Operation support flags
    supports_attach: bool = True
    supports_action_button: bool = True
    supports_evaluate_format: bool = True


# Phase 1: Contract entity
# Phase 2: Company, Attachment entities
# Phase 3: Contact, Employee, Customer entities
ENTITY_REGISTRY: Dict[str, EntityConfig] = {
    "contract": EntityConfig(
        key="contract",
        key_plural="contracts",
        api_path="/contract",
        display_name="Contract",
        display_name_plural="Contracts",
        text_search_fields=["contract_title1", "company_name"],
        key_fields={
            "record_type": {"type": "string", "description": "Contract record type (REQUIRED)"},
            "contract_title1": {"type": "string", "description": "Contract title"},
            "company_name": {"type": "string", "description": "Associated company name"},
            "contract_amount": {"type": "number", "description": "Contract monetary amount"},
            "contract_start_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
            "contract_end_date": {"type": "string", "description": "End date (YYYY-MM-DD)"},
            "contract_term_in_months": {"type": "integer", "description": "Term length in months"},
            "internal_contract_owner": {"type": "string", "description": "Internal contract owner"},
            "contract_type": {"type": "string", "description": "Type of contract (linked field - must match existing value, e.g. 'Master Services Agreement', 'Services Agreement', 'SaaS Agreement', 'Non-Disclosure Agreement')"},
            "contract_description": {"type": "string", "description": "Contract description"},
            "wfstate": {"type": "string", "description": "Contract status (workflow state)"},
            "confidential": {"type": "string", "description": "Confidentiality level (REQUIRED)"},
            "evaluation_frequency": {"type": "integer", "description": "Evaluation frequency (REQUIRED)"},
            "auto_renewal_term_in_months": {"type": "integer", "description": "Auto-renewal term (REQUIRED)"},
            "date_signed": {"type": "string", "description": "Date contract was signed"},
            "signer1_email": {"type": "string", "description": "Primary signer email"},
            "cost_center": {"type": "string", "description": "Cost center"},
            "annual_increase": {"type": "number", "description": "Annual increase percentage"},
        },
        default_search_fields=[
            "id", "record_type", "contract_title1", "company_name",
            "contract_amount", "contract_end_date", "internal_contract_owner",
            "date_signed", "wfstate", "contract_type"
        ],
        required_fields=[
            "record_type", "auto_renewal_term_in_months", "confidential", "evaluation_frequency"
        ],
    ),
    "company": EntityConfig(
        key="company",
        key_plural="companies",
        api_path="/company",
        display_name="Company",
        display_name_plural="Companies",
        text_search_fields=["company_name"],
        key_fields={
            "company_name": {"type": "string", "description": "Company name (REQUIRED)"},
            "type_of_company": {"type": "string", "description": "Type of company (REQUIRED)"},
            "status": {"type": "string", "description": "Company status (REQUIRED)"},
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
        key_plural="attachments",
        api_path="/attachment",
        display_name="Attachment",
        display_name_plural="Attachments",
        text_search_fields=["title"],
        key_fields={
            "title": {"type": "string", "description": "Attachment title (REQUIRED)"},
            "status": {"type": "string", "description": "Attachment status (REQUIRED)"},
            "attached_file": {"type": "string", "description": "Attached file reference (REQUIRED)"},
            "expiration_date": {"type": "string", "description": "Expiration date (REQUIRED)"},
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
        key_plural="contacts",
        api_path="/contacts",
        display_name="Contact",
        display_name_plural="Contacts",
        text_search_fields=["full_name", "company_name"],
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
            "sso_auth_method": {"type": "string", "description": "SSO auth method (REQUIRED)"},
        },
        default_search_fields=[
            "id", "full_name", "email", "company_name", "status",
            "type_of_contact", "direct_phone", "title"
        ],
        required_fields=["sso_auth_method"],
    ),
    "employee": EntityConfig(
        key="employee",
        key_plural="employees",
        api_path="/contacts.employees",
        display_name="Employee",
        display_name_plural="Employees",
        text_search_fields=["full_name", "company_name"],
        key_fields={
            "_login": {"type": "string", "description": "Login username (REQUIRED)"},
            "password": {"type": "string", "description": "Password (REQUIRED)"},
            "first_name": {"type": "string", "description": "First name"},
            "last_name": {"type": "string", "description": "Last name"},
            "full_name": {"type": "string", "description": "Full name"},
            "email": {"type": "string", "description": "Email address"},
            "company_name": {"type": "array", "description": "Associated company names"},
            "status": {"type": "string", "description": "Contact status"},
            "type_of_contact": {"type": "string", "description": "Type of contact"},
            "department0": {"type": "string", "description": "Department"},
            "title": {"type": "string", "description": "Job title"},
            "sso_auth_method": {"type": "string", "description": "SSO auth method (REQUIRED)"},
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
        key_plural="customers",
        api_path="/contacts.customer",
        display_name="Customer Contact",
        display_name_plural="Customer Contacts",
        text_search_fields=["full_name", "company_name"],
        key_fields={
            "_login": {"type": "string", "description": "Login username (REQUIRED)"},
            "password": {"type": "string", "description": "Password (REQUIRED)"},
            "first_name": {"type": "string", "description": "First name"},
            "last_name": {"type": "string", "description": "Last name"},
            "full_name": {"type": "string", "description": "Full name"},
            "email": {"type": "string", "description": "Email address"},
            "company_name": {"type": "array", "description": "Associated company names"},
            "status": {"type": "string", "description": "Contact status"},
            "type_of_contact": {"type": "string", "description": "Type of contact"},
            "title": {"type": "string", "description": "Job title"},
            "sso_auth_method": {"type": "string", "description": "SSO auth method (REQUIRED)"},
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
        valid = ", ".join(ENTITY_REGISTRY.keys())
        raise ValueError(f"Unknown entity: '{key}'. Valid entities: {valid}")
    return ENTITY_REGISTRY[key]


def list_entities() -> List[str]:
    """Return list of registered entity keys."""
    return list(ENTITY_REGISTRY.keys())
