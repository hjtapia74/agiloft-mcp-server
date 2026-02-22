"""
Composite Workflow Handlers

Handler implementations for business workflow tools that chain multiple
Agiloft API calls. Each handler receives arguments and an AgiloftClient,
makes the necessary API calls, and returns enriched responses with
next_steps guidance.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from mcp.types import TextContent

# Handle both direct execution and package imports
try:
    from .agiloft_client import AgiloftClient
except ImportError:
    from agiloft_client import AgiloftClient

logger = logging.getLogger(__name__)

# Contract fields that are linked to other tables and MUST have a colon (:)
# prefix when setting values via the API (e.g. ":Services Agreement").
CONTRACT_LINKED_FIELDS = {
    "company_name",
    "contract_type",
    "internal_contract_owner",
}


def _ensure_linked_prefix(data: Dict[str, Any], linked_fields: set) -> Dict[str, Any]:
    """Add colon prefix to linked field values if not already present.

    Agiloft linked fields require values to start with ':' (e.g. ':Acme Corp').
    This helper ensures the prefix is always present for known linked fields.
    """
    result = dict(data)
    for field_name in linked_fields:
        value = result.get(field_name)
        if isinstance(value, str) and value and not value.startswith(":"):
            result[field_name] = f":{value}"
    return result


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------

def _workflow_response(
    operation: str,
    data: Any,
    next_steps: Optional[List[str]] = None,
    warnings: Optional[List[str]] = None,
) -> List[TextContent]:
    """Build an enriched workflow response with guidance."""
    result: Dict[str, Any] = {
        "success": True,
        "operation": operation,
    }
    result["data"] = data
    if next_steps:
        result["next_steps"] = next_steps
    if warnings:
        result["warnings"] = warnings

    return [TextContent(
        type="text",
        text=json.dumps(result, indent=2, default=str),
    )]


def _workflow_error(
    operation: str,
    error: str,
    partial_data: Optional[Any] = None,
) -> List[TextContent]:
    """Build an error response, optionally including partial results."""
    result: Dict[str, Any] = {
        "success": False,
        "operation": operation,
        "error": error,
    }
    if partial_data is not None:
        result["partial_data"] = partial_data

    return [TextContent(
        type="text",
        text=json.dumps(result, indent=2, default=str),
    )]


# ---------------------------------------------------------------------------
# Handler: preflight_create_contract
# ---------------------------------------------------------------------------

async def handle_preflight_create_contract(
    arguments: Dict[str, Any], client: AgiloftClient
) -> List[TextContent]:
    """Validate contract creation prerequisites without creating anything."""
    contract_type_name = arguments.get("contract_type", "")
    company_name = arguments.get("company_name", "")

    data: Dict[str, Any] = {}
    warnings: List[str] = []
    next_steps: List[str] = []
    ready_to_create = True

    try:
        # Step 1: Contract type validation
        if not contract_type_name:
            # Return all active contract types for selection
            types = await client.search_records(
                "/contract_type",
                "status=Active",
                ["id", "contract_type", "party_type", "description",
                 "default_contract_term_in_months", "default_autorenewal_term_in_months"],
            )
            data["available_contract_types"] = types
            data["ready_to_create"] = False
            next_steps.append(
                "Select a contract type from the list and call this tool again "
                "with the contract_type parameter."
            )
            return _workflow_response(
                "preflight_create_contract", data,
                next_steps=next_steps, warnings=warnings,
            )

        # Validate specific contract type exists and is active
        type_query = f"contract_type='{contract_type_name}' AND status=Active"
        type_results = await client.search_records(
            "/contract_type", type_query,
            ["id", "contract_type", "party_type", "description",
             "default_contract_term_in_months", "default_autorenewal_term_in_months",
             "available_for_record_types"],
        )

        if not type_results:
            data["ready_to_create"] = False
            warnings.append(
                f"Contract type '{contract_type_name}' not found or not active."
            )
            # Fetch active types as fallback
            active_types = await client.search_records(
                "/contract_type", "status=Active",
                ["id", "contract_type", "party_type"],
            )
            data["available_contract_types"] = active_types
            next_steps.append("Choose from the available active contract types.")
            return _workflow_response(
                "preflight_create_contract", data,
                next_steps=next_steps, warnings=warnings,
            )

        contract_type_info = type_results[0]
        data["contract_type"] = contract_type_info

        # Step 2: Company validation
        if company_name:
            company_query = f"company_name~='{company_name}'"
            company_results = await client.search_records(
                "/company", company_query,
                ["id", "company_name", "type_of_company", "status"],
            )

            if not company_results:
                ready_to_create = False
                warnings.append(
                    f"Company '{company_name}' not found. "
                    "Create it first or check the name."
                )
                next_steps.append(
                    "Use agiloft_create_company or agiloft_onboard_company_with_contact "
                    "to create the company first."
                )
            else:
                data["company"] = company_results[0]
                # Check party_type compatibility
                party_type = contract_type_info.get("party_type", "")
                company_type = company_results[0].get("type_of_company", "")
                if party_type and company_type and party_type != company_type:
                    warnings.append(
                        f"Type mismatch: contract type expects party_type='{party_type}' "
                        f"but company is type_of_company='{company_type}'. "
                        "This may cause issues."
                    )

                if company_results[0].get("status") != "Active":
                    warnings.append(
                        f"Company '{company_name}' status is "
                        f"'{company_results[0].get('status')}', not Active."
                    )
        else:
            next_steps.append(
                "Provide a company_name to validate company compatibility."
            )

        # Step 3: Required fields reminder
        data["required_fields"] = {
            "record_type": "Contract, Child Contract, or Amendment",
            "auto_renewal_term_in_months": "integer",
            "confidential": "string",
            "evaluation_frequency": "integer",
            "contract_type": f":{contract_type_name}",
        }
        if company_name and data.get("company"):
            data["required_fields"]["company_name"] = f":{company_name}"

        # CRITICAL: Linked field colon prefix reminder
        data["linked_fields_warning"] = (
            "CRITICAL: The following fields are LINKED FIELDS and their values "
            "MUST start with a colon (:) prefix when creating or updating. "
            "Without the colon prefix, the API will reject the value or fail silently."
        )
        data["linked_fields"] = {
            "contract_type": f":{contract_type_name}",
            "company_name": f":{company_name}" if company_name else "(provide company name with : prefix)",
            "internal_contract_owner": ":<owner name> (e.g. :Robert Barash)",
        }

        data["ready_to_create"] = ready_to_create and not warnings

        if data["ready_to_create"]:
            next_steps.append(
                "All validations passed. Use agiloft_create_contract with the "
                "required fields to create the contract. IMPORTANT: Use colon "
                "prefix for linked fields - contract_type, company_name, and "
                "internal_contract_owner values MUST start with ':' "
                f"(e.g. contract_type=':{contract_type_name}')."
            )

        return _workflow_response(
            "preflight_create_contract", data,
            next_steps=next_steps, warnings=warnings,
        )

    except Exception as e:
        return _workflow_error("preflight_create_contract", str(e))


# ---------------------------------------------------------------------------
# Handler: create_contract_with_company
# ---------------------------------------------------------------------------

async def handle_create_contract_with_company(
    arguments: Dict[str, Any], client: AgiloftClient
) -> List[TextContent]:
    """Create a contract with automatic company resolution."""
    contract_data = arguments.get("contract_data", {})
    company_name = arguments.get("company_name", "")
    create_if_missing = arguments.get("create_company_if_missing", False)
    company_data = arguments.get("company_data", {})

    data: Dict[str, Any] = {}
    warnings: List[str] = []
    next_steps: List[str] = []

    try:
        # Step 1: Find or create company
        company_query = f"company_name='{company_name}'"
        company_results = await client.search_records(
            "/company", company_query,
            ["id", "company_name", "type_of_company", "status"],
        )

        if company_results:
            data["company"] = company_results[0]
            data["company_action"] = "found_existing"
        elif create_if_missing:
            # Create the company
            create_data = {**company_data, "company_name": company_name}
            # Strip empty values
            create_data = {k: v for k, v in create_data.items() if v is not None and v != ""}
            company_result = await client.create_record("/company", create_data)
            data["company"] = company_result
            data["company_action"] = "created_new"
        else:
            return _workflow_error(
                "create_contract_with_company",
                f"Company '{company_name}' not found. Set create_company_if_missing=true "
                "and provide company_data to create it, or create it separately first.",
            )

        # Step 2: Create the contract with company linked
        contract_data["company_name"] = f":{company_name}"
        # Auto-prefix linked fields (contract_type, internal_contract_owner, etc.)
        contract_data = _ensure_linked_prefix(contract_data, CONTRACT_LINKED_FIELDS)
        # Strip empty values
        contract_data = {k: v for k, v in contract_data.items() if v is not None and v != ""}
        contract_result = await client.create_record("/contract", contract_data)
        data["contract"] = contract_result

        next_steps.append(
            "Contract created successfully. You can now:\n"
            "- Upload attachments with agiloft_attach_file_to_contract (NOT agiloft_attach_file_contract)\n"
            "- Review the full contract with agiloft_get_contract_summary"
        )

        return _workflow_response(
            "create_contract_with_company", data,
            next_steps=next_steps, warnings=warnings,
        )

    except Exception as e:
        return _workflow_error(
            "create_contract_with_company", str(e),
            partial_data=data if data else None,
        )


# ---------------------------------------------------------------------------
# Handler: get_contract_summary
# ---------------------------------------------------------------------------

async def handle_get_contract_summary(
    arguments: Dict[str, Any], client: AgiloftClient
) -> List[TextContent]:
    """Get comprehensive contract summary with related data."""
    contract_id = arguments.get("contract_id")

    data: Dict[str, Any] = {}
    warnings: List[str] = []
    next_steps: List[str] = []

    try:
        # Step 1: Get contract details
        contract = await client.get_record(
            "/contract", contract_id,
            [
                "id", "record_type", "contract_title1", "company_name",
                "contract_type", "contract_amount", "contract_start_date",
                "contract_end_date", "contract_term_in_months", "wfstate",
                "internal_contract_owner", "date_signed", "confidential",
                "auto_renewal_term_in_months", "evaluation_frequency",
                "contract_description", "cost_center",
            ],
        )
        data["contract"] = contract

        # Step 2: Get company details if company_name present
        company_name = contract.get("company_name", "")
        if company_name:
            # Remove colon prefix if present
            clean_name = company_name.lstrip(":")
            try:
                company_results = await client.search_records(
                    "/company", f"company_name='{clean_name}'",
                    ["id", "company_name", "type_of_company", "status",
                     "industry", "main_city", "country",
                     "number_of_active_contracts"],
                )
                if company_results:
                    data["company"] = company_results[0]
            except Exception as e:
                warnings.append(f"Could not fetch company details: {e}")

        # Step 3: Check attachments
        try:
            attach_info = await client.get_attachment_info(
                "/contract", contract_id, "attached_file"
            )
            data["attachments"] = attach_info
        except Exception:
            data["attachments"] = {"count": 0, "note": "No attachments or field not available"}

        # Step 4: Health checks
        health_issues: List[str] = []

        # Check end date
        end_date_str = contract.get("contract_end_date", "")
        if end_date_str:
            try:
                end_date = datetime.strptime(str(end_date_str)[:10], "%Y-%m-%d")
                days_remaining = (end_date - datetime.now()).days
                if days_remaining < 0:
                    health_issues.append(
                        f"Contract EXPIRED {abs(days_remaining)} days ago"
                    )
                elif days_remaining <= 30:
                    health_issues.append(
                        f"Contract expires in {days_remaining} days - URGENT"
                    )
                elif days_remaining <= 90:
                    health_issues.append(
                        f"Contract expires in {days_remaining} days - review soon"
                    )
                data["days_remaining"] = days_remaining
            except (ValueError, TypeError):
                pass

        # Check missing fields
        if not contract.get("contract_amount"):
            health_issues.append("Missing contract amount")
        if not contract.get("internal_contract_owner"):
            health_issues.append("No contract owner assigned")
        if not contract.get("date_signed"):
            health_issues.append("Contract not yet signed")

        # Check status
        status = contract.get("wfstate", "")
        if status in ("Draft", "Cancelled", "Expired"):
            health_issues.append(f"Contract status is '{status}'")

        if health_issues:
            data["health_issues"] = health_issues

        next_steps.append(
            "Available actions:\n"
            "- Update fields: agiloft_update_contract\n"
            "- Upload attachment: agiloft_attach_file_to_contract (NOT agiloft_attach_file_contract)\n"
            "- Download attachment: agiloft_retrieve_attachment_attachment (on the attachment record)\n"
            "- Trigger action: agiloft_action_button_contract\n"
            "- View company: agiloft_get_company"
        )

        return _workflow_response(
            "get_contract_summary", data,
            next_steps=next_steps, warnings=warnings,
        )

    except Exception as e:
        return _workflow_error(
            "get_contract_summary", str(e),
            partial_data=data if data else None,
        )


# ---------------------------------------------------------------------------
# Handler: find_expiring_contracts
# ---------------------------------------------------------------------------

async def handle_find_expiring_contracts(
    arguments: Dict[str, Any], client: AgiloftClient
) -> List[TextContent]:
    """Find contracts expiring within a date range with urgency categories."""
    days_from_now = arguments.get("days_from_now", 90)
    include_expired = arguments.get("include_expired", False)
    status_filter = arguments.get("status_filter", "")

    data: Dict[str, Any] = {}
    warnings: List[str] = []
    next_steps: List[str] = []

    try:
        now = datetime.now()
        future_date = now + timedelta(days=days_from_now)

        # Build query
        if include_expired:
            query = f"contract_end_date<='{future_date.strftime('%Y-%m-%d')}'"
        else:
            query = (
                f"contract_end_date>='{now.strftime('%Y-%m-%d')}' "
                f"AND contract_end_date<='{future_date.strftime('%Y-%m-%d')}'"
            )

        if status_filter:
            query += f" AND wfstate='{status_filter}'"

        results = await client.search_records(
            "/contract", query,
            [
                "id", "contract_title1", "company_name", "contract_type",
                "contract_end_date", "contract_amount", "wfstate",
                "auto_renewal_term_in_months", "internal_contract_owner",
            ],
            limit=200,
        )

        # Categorize by urgency
        urgent = []      # <= 30 days
        upcoming = []    # 31-60 days
        planning = []    # 61+ days
        already_expired = []

        for contract in results:
            end_date_str = contract.get("contract_end_date", "")
            if not end_date_str:
                continue
            try:
                end_date = datetime.strptime(str(end_date_str)[:10], "%Y-%m-%d")
                days_remaining = (end_date - now).days
                contract["days_remaining"] = days_remaining

                if days_remaining < 0:
                    contract["urgency"] = "EXPIRED"
                    already_expired.append(contract)
                elif days_remaining <= 30:
                    contract["urgency"] = "URGENT"
                    urgent.append(contract)
                elif days_remaining <= 60:
                    contract["urgency"] = "UPCOMING"
                    upcoming.append(contract)
                else:
                    contract["urgency"] = "PLANNING"
                    planning.append(contract)
            except (ValueError, TypeError):
                warnings.append(
                    f"Contract {contract.get('id')}: could not parse end_date '{end_date_str}'"
                )

        data["summary"] = {
            "total_found": len(results),
            "urgent_count": len(urgent),
            "upcoming_count": len(upcoming),
            "planning_count": len(planning),
            "expired_count": len(already_expired),
            "search_range_days": days_from_now,
        }
        data["urgent"] = urgent
        data["upcoming"] = upcoming
        data["planning"] = planning
        if include_expired:
            data["expired"] = already_expired

        if urgent:
            next_steps.append(
                f"{len(urgent)} URGENT contract(s) expiring within 30 days - "
                "review immediately with agiloft_get_contract_summary."
            )
        if upcoming:
            next_steps.append(
                f"{len(upcoming)} contract(s) expiring in 31-60 days - "
                "schedule renewal discussions."
            )
        if not results:
            next_steps.append(
                f"No contracts expiring within {days_from_now} days. "
                "Try increasing the days_from_now value."
            )

        return _workflow_response(
            "find_expiring_contracts", data,
            next_steps=next_steps, warnings=warnings,
        )

    except Exception as e:
        return _workflow_error("find_expiring_contracts", str(e))


# ---------------------------------------------------------------------------
# Handler: onboard_company_with_contact
# ---------------------------------------------------------------------------

async def handle_onboard_company_with_contact(
    arguments: Dict[str, Any], client: AgiloftClient
) -> List[TextContent]:
    """Onboard a company with an optional primary contact."""
    company_data = arguments.get("company_data", {})
    contact_data = arguments.get("contact_data")
    skip_if_exists = arguments.get("skip_if_exists", False)

    company_name = company_data.get("company_name", "")
    data: Dict[str, Any] = {}
    warnings: List[str] = []
    next_steps: List[str] = []

    if not company_name:
        return _workflow_error(
            "onboard_company_with_contact",
            "company_data.company_name is required.",
        )

    try:
        # Step 1: Check if company exists
        existing = await client.search_records(
            "/company", f"company_name='{company_name}'",
            ["id", "company_name", "type_of_company", "status"],
        )

        if existing:
            if skip_if_exists:
                data["company"] = existing[0]
                data["company_action"] = "already_exists"
                warnings.append(
                    f"Company '{company_name}' already exists (ID: {existing[0].get('id')}). "
                    "Skipped creation."
                )
            else:
                return _workflow_error(
                    "onboard_company_with_contact",
                    f"Company '{company_name}' already exists (ID: {existing[0].get('id')}). "
                    "Set skip_if_exists=true to use the existing company, "
                    "or use agiloft_update_company to modify it.",
                    partial_data={"existing_company": existing[0]},
                )
        else:
            # Create company
            create_data = {k: v for k, v in company_data.items() if v is not None and v != ""}
            company_result = await client.create_record("/company", create_data)
            data["company"] = company_result
            data["company_action"] = "created"

        # Step 2: Create contact if provided
        if contact_data:
            contact_create = {k: v for k, v in contact_data.items() if v is not None and v != ""}
            # Link contact to company
            contact_create["company_name"] = f":{company_name}"
            contact_result = await client.create_record("/contacts", contact_create)
            data["contact"] = contact_result
            data["contact_action"] = "created"
        else:
            next_steps.append(
                "No contact was created. Use agiloft_create_contact to add "
                "a contact linked to this company."
            )

        next_steps.append(
            "Company onboarded. You can now:\n"
            "- Create a contract: agiloft_create_contract or agiloft_create_contract_with_company\n"
            "- Add more contacts: agiloft_create_contact"
        )

        return _workflow_response(
            "onboard_company_with_contact", data,
            next_steps=next_steps, warnings=warnings,
        )

    except Exception as e:
        return _workflow_error(
            "onboard_company_with_contact", str(e),
            partial_data=data if data else None,
        )


# ---------------------------------------------------------------------------
# Handler: attach_file_to_contract
# ---------------------------------------------------------------------------

async def handle_attach_file_to_contract(
    arguments: Dict[str, Any], client: AgiloftClient
) -> List[TextContent]:
    """Attach a file to a contract via the Attachment entity.

    Contracts in Agiloft don't have direct file fields. Files are attached by:
    1. Looking up the contract's title (needed for linking)
    2. Creating an Attachment record linked to the contract via contract_title
    3. Uploading the file to the Attachment record's attached_file field

    The file_path must be an absolute path on the local macOS filesystem.
    The server reads the file directly from disk.
    """
    import os

    contract_id = arguments.get("contract_id")
    file_path = arguments.get("file_path", "")
    file_name = arguments.get("file_name", "")
    attachment_title = arguments.get("attachment_title", "")

    data: Dict[str, Any] = {}
    next_steps: List[str] = []

    if not file_path:
        return _workflow_error(
            "attach_file_to_contract",
            "file_path is required. Provide the absolute path to the file on the "
            "local macOS filesystem (e.g. '/Users/hector/Downloads/contract.pdf'). "
            "Ask the user for the file path if you don't have it.",
        )

    # Detect sandbox paths and reject them with a helpful message
    _sandbox_prefixes = ("/mnt/", "/home/claude", "/tmp/sandbox", "/sandbox/")
    if any(file_path.startswith(p) for p in _sandbox_prefixes):
        return _workflow_error(
            "attach_file_to_contract",
            f"'{file_path}' is a sandbox path, not a real filesystem path. "
            "The MCP server runs on the local machine and needs the actual macOS "
            "file path (e.g. '/Users/hector/Downloads/contract.pdf'). "
            "Please ask the user for the real file location on their Mac.",
        )

    file_path = os.path.expanduser(file_path)
    if not os.path.isfile(file_path):
        return _workflow_error(
            "attach_file_to_contract",
            f"File not found: {file_path}. "
            "Make sure this is the correct absolute path on the local macOS filesystem. "
            "Ask the user to verify the file location.",
        )

    try:
        with open(file_path, "rb") as f:
            file_data = f.read()
    except Exception as e:
        return _workflow_error(
            "attach_file_to_contract",
            f"Could not read file {file_path}: {e}",
        )

    if not file_name:
        file_name = os.path.basename(file_path)
    if not attachment_title:
        attachment_title = file_name

    file_size = len(file_data)
    logger.info(
        f"attach_file_to_contract: contract_id={contract_id}, "
        f"file_name={file_name}, file_size={file_size} bytes, "
        f"file_path={file_path}"
    )

    if file_size == 0:
        return _workflow_error(
            "attach_file_to_contract",
            "File is empty (0 bytes).",
        )

    try:
        # Step 1: Get contract title for linking
        logger.info(f"Step 1: Getting contract {contract_id} title...")
        contract = await client.get_record(
            "/contract", contract_id, ["id", "contract_title1"]
        )
        contract_title = contract.get("contract_title1", "")
        data["contract"] = contract
        logger.info(f"Step 1 done: contract_title1='{contract_title}'")

        if not contract_title:
            return _workflow_error(
                "attach_file_to_contract",
                f"Contract {contract_id} has no title (contract_title1). Cannot link attachment.",
                partial_data=data,
            )

        # Step 2: Create Attachment record linked to contract
        attachment_record = {
            "title": attachment_title,
            "status": "Active",
            "expiration_date": "2099-12-31",
            "contract_title": f":{contract_title}",
        }
        logger.info(f"Step 2: Creating attachment record linked to '{contract_title}'...")
        create_result = await client.create_record("/attachment", attachment_record)
        data["attachment_record"] = create_result
        logger.info(f"Step 2 done: create_result={create_result}")

        attachment_id = None
        if isinstance(create_result.get("result"), (int, str)):
            attachment_id = int(create_result["result"])
        elif isinstance(create_result.get("result"), dict):
            attachment_id = create_result["result"].get("id")

        if not attachment_id:
            return _workflow_error(
                "attach_file_to_contract",
                "Created attachment record but could not determine its ID. "
                f"Response: {create_result}",
                partial_data=data,
            )

        data["attachment_id"] = attachment_id
        logger.info(f"Step 2: attachment_id={attachment_id}")

        # Step 3: Upload file to the Attachment record
        logger.info(
            f"Step 3: Uploading {file_size} bytes to attachment {attachment_id}..."
        )
        upload_result = await client.attach_file(
            "/attachment", attachment_id, "attached_file", file_name, file_data
        )
        data["upload_result"] = upload_result
        logger.info(f"Step 3 done: upload_result={upload_result}")

        # Step 4: Verify
        logger.info(f"Step 4: Verifying attachment {attachment_id}...")
        file_info = await client.get_attachment_info(
            "/attachment", attachment_id, "attached_file"
        )
        data["file_info"] = file_info
        logger.info(f"Step 4 done: file_info={file_info}")

        next_steps.append(
            f"File '{file_name}' attached to contract {contract_id} "
            f"via attachment record {attachment_id}. You can:\n"
            "- Download it: agiloft_retrieve_attachment_attachment\n"
            "- View info: agiloft_get_attachment_info_attachment\n"
            "- Remove it: agiloft_remove_attachment_attachment"
        )

        return _workflow_response(
            "attach_file_to_contract", data, next_steps=next_steps,
        )

    except Exception as e:
        logger.error(f"attach_file_to_contract failed: {e}", exc_info=True)
        return _workflow_error(
            "attach_file_to_contract", str(e),
            partial_data=data if data else None,
        )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

WORKFLOW_HANDLERS = {
    "preflight_create_contract": handle_preflight_create_contract,
    "create_contract_with_company": handle_create_contract_with_company,
    "get_contract_summary": handle_get_contract_summary,
    "find_expiring_contracts": handle_find_expiring_contracts,
    "onboard_company_with_contact": handle_onboard_company_with_contact,
    "attach_file_to_contract": handle_attach_file_to_contract,
}


async def dispatch_workflow_call(
    name: str, arguments: Dict[str, Any], client: AgiloftClient,
    workflow_dispatch: Dict[str, str],
) -> List[TextContent]:
    """Dispatch a workflow tool call to the appropriate handler.

    Args:
        name: Tool name (e.g., "agiloft_preflight_create_contract")
        arguments: Tool arguments from MCP
        client: AgiloftClient instance
        workflow_dispatch: Mapping of tool_name -> handler_name
    """
    handler_name = workflow_dispatch.get(name)
    if not handler_name:
        raise ValueError(f"Unknown workflow tool: {name}")

    handler = WORKFLOW_HANDLERS.get(handler_name)
    if not handler:
        raise ValueError(f"Unknown workflow handler: {handler_name}")

    return await handler(arguments, client)
