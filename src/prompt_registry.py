"""
Agiloft MCP Prompt Registry

Defines MCP Prompt templates that appear in Claude Desktop's slash-command menu.
Each prompt pre-loads step-by-step instructions to guide the conversation through
a business workflow using the underlying CRUD tools.
"""

from typing import Dict, List, Optional

from mcp.types import (
    Prompt,
    PromptArgument,
    PromptMessage,
    GetPromptResult,
    TextContent,
)


def _user_msg(text: str) -> PromptMessage:
    """Helper to create a user-role prompt message."""
    return PromptMessage(role="user", content=TextContent(type="text", text=text))


# ---------------------------------------------------------------------------
# Prompt renderers
# ---------------------------------------------------------------------------

def _render_create_contract(arguments: Dict[str, str]) -> GetPromptResult:
    contract_type = arguments.get("contract_type", "")
    company_name = arguments.get("company_name", "")

    steps = []
    steps.append(
        "I want to create a new contract in Agiloft. "
        "Please guide me through the process step by step."
    )

    if contract_type:
        steps.append(
            f"\nI'd like to use contract type: {contract_type}"
        )
    else:
        steps.append(
            "\nFirst, search for available contract types using "
            "agiloft_search_contract_types with query \"status=Active\" "
            "and present them so I can choose one."
        )

    if company_name:
        steps.append(
            f"\nThe company is: {company_name}. "
            "Please verify it exists using agiloft_search_companies and "
            "check that its type_of_company is compatible with the contract type's party_type."
        )
    else:
        steps.append(
            "\nAfter I select a contract type, ask me for the company name. "
            "Then search for it with agiloft_search_companies to verify it exists "
            "and check type compatibility with the contract type's party_type."
        )

    steps.append(
        "\nOnce the contract type and company are confirmed, collect these "
        "required fields from me:\n"
        "- record_type (Contract, Child Contract, or Amendment)\n"
        "- contract_title1\n"
        "- auto_renewal_term_in_months\n"
        "- confidential\n"
        "- evaluation_frequency\n"
        "And any optional fields I want to provide (dates, amount, owner, etc.)."
    )

    steps.append(
        "\nCRITICAL - LINKED FIELD COLON PREFIX RULE:\n"
        "Several contract fields are 'linked fields' in Agiloft. When setting "
        "their values in create or update calls, the value MUST start with a "
        "colon (:) prefix. Without it, the API will reject the value.\n"
        "Linked fields that require colon prefix:\n"
        "- contract_type → ':Services Agreement' (not 'Services Agreement')\n"
        "- company_name → ':Acme Corp' (not 'Acme Corp')\n"
        "- internal_contract_owner → ':Robert Barash' (not 'Robert Barash')\n"
        "Always add the colon prefix to these fields when calling "
        "agiloft_create_contract or agiloft_update_contract."
    )

    steps.append(
        "\nAfter gathering all fields, use agiloft_preflight_create_contract "
        "to validate everything before creating. Then use agiloft_create_contract "
        "to create the contract. Remember to use colon prefixes for linked fields."
    )

    steps.append(
        "\nAfter creation, ask if I want to upload any attachments to the new contract. "
        "IMPORTANT: To attach files to a contract, use agiloft_attach_file_to_contract "
        "(NOT agiloft_attach_file_contract, which tries to attach directly to the "
        "contract table and will fail). The workflow tool creates an Attachment record "
        "linked to the contract and uploads the file to it. "
        "ALWAYS use the file_path parameter with the full path to the file on disk. "
        "Do NOT use file_content_base64 (encoding large files to base64 will hang)."
    )

    return GetPromptResult(
        description="Step-by-step contract creation workflow",
        messages=[_user_msg("\n".join(steps))],
    )


def _render_contract_review(arguments: Dict[str, str]) -> GetPromptResult:
    contract_id = arguments.get("contract_id", "")

    steps = []
    steps.append("I want to review a contract in detail.")

    if contract_id:
        steps.append(
            f"\nRetrieve contract ID {contract_id} using agiloft_get_contract "
            "with all default fields."
        )
    else:
        steps.append(
            "\nAsk me for a contract ID or search criteria. If I give search "
            "criteria, use agiloft_search_contracts to find matching contracts "
            "and let me pick one."
        )

    steps.append(
        "\nOnce you have the contract, present a summary including:\n"
        "- Title, type, status (wfstate)\n"
        "- Company name\n"
        "- Amount, dates (start, end, signed)\n"
        "- Owner\n"
        "- Term and auto-renewal details"
    )

    steps.append(
        "\nThen check for attachments using agiloft_get_attachment_info_contract "
        "on the 'attached_file' field and report how many files are attached."
    )

    steps.append(
        "\nFlag any potential issues:\n"
        "- Contract end date is in the past or within 30 days\n"
        "- Missing key fields (amount, dates, owner)\n"
        "- Status is Draft or Cancelled"
    )

    steps.append(
        "\nFinally, offer available actions:\n"
        "- Update contract fields (remember: linked fields like contract_type, "
        "company_name, internal_contract_owner need colon prefix, e.g. ':value')\n"
        "- Upload attachment: use agiloft_attach_file_to_contract with file_path parameter (NOT agiloft_attach_file_contract)\n"
        "- Download attachment: use agiloft_retrieve_attachment_attachment on the attachment record\n"
        "- Trigger an action button\n"
        "- View the associated company details"
    )

    return GetPromptResult(
        description="Contract review and health check",
        messages=[_user_msg("\n".join(steps))],
    )


def _render_company_onboarding(arguments: Dict[str, str]) -> GetPromptResult:
    company_name = arguments.get("company_name", "")

    steps = []
    steps.append("I want to onboard a new company in Agiloft.")

    if company_name:
        steps.append(
            f"\nFirst, check if \"{company_name}\" already exists by searching "
            "with agiloft_search_companies. If it exists, show me the existing "
            "record and ask if I want to update it or proceed with a new one."
        )
    else:
        steps.append(
            "\nAsk me for the company name, then search agiloft_search_companies "
            "to check if it already exists."
        )

    steps.append(
        "\nIf the company doesn't exist (or I want a new one), collect:\n"
        "- company_name (required)\n"
        "- type_of_company (required - e.g. Customer, Vendor, Partner)\n"
        "- status (required - e.g. Active)\n"
        "- Optional: industry, country, main_city, account_rep"
    )

    steps.append(
        "\nCreate the company using agiloft_create_company with the gathered data."
    )

    steps.append(
        "\nAfter creating the company, ask if I want to create a primary contact. "
        "If yes, collect contact details (first_name, last_name, email, title) "
        "and create using agiloft_create_contact with the company_name linked."
    )

    return GetPromptResult(
        description="Company onboarding workflow with optional contact creation",
        messages=[_user_msg("\n".join(steps))],
    )


def _render_contract_search_report(arguments: Dict[str, str]) -> GetPromptResult:
    search_criteria = arguments.get("search_criteria", "")

    steps = []
    steps.append("I want to search for contracts and get a summary report.")

    if search_criteria:
        steps.append(
            f"\nSearch criteria: {search_criteria}\n"
            "Use agiloft_search_contracts with an appropriate structured query. "
            "If the criteria is a company name, use company_name~='value'. "
            "If it's a status, use wfstate='value'."
        )
    else:
        steps.append(
            "\nAsk me what I'm looking for. I can search by:\n"
            "- Company name\n"
            "- Contract status (wfstate)\n"
            "- Contract type\n"
            "- Date ranges (contract_end_date)\n"
            "- Amount ranges\n"
            "- Or any combination using AND/OR"
        )

    steps.append(
        "\nPresent the results as a formatted summary table/report with:\n"
        "- Total count of matching contracts\n"
        "- For each contract: ID, title, company, type, status, amount, end date\n"
        "- Summary statistics: total amount, count by status, count by type"
    )

    steps.append(
        "\nAfter showing results, offer to:\n"
        "- Drill into any specific contract (contract-review)\n"
        "- Narrow or broaden the search\n"
        "- Export the data (list the records)"
    )

    return GetPromptResult(
        description="Contract search with summary reporting",
        messages=[_user_msg("\n".join(steps))],
    )


def _render_contract_renewal_check(arguments: Dict[str, str]) -> GetPromptResult:
    days_ahead = arguments.get("days_ahead", "90")

    steps = []
    steps.append(
        f"I want to check for contracts expiring within the next {days_ahead} days."
    )

    steps.append(
        f"\nUse agiloft_find_expiring_contracts with days_from_now={days_ahead} "
        "to find contracts approaching their end date."
    )

    steps.append(
        "\nPresent the results organized by urgency:\n"
        "- URGENT: Expiring within 30 days\n"
        "- UPCOMING: Expiring within 31-60 days\n"
        "- PLANNING: Expiring within 61+ days"
    )

    steps.append(
        "\nFor each contract, show:\n"
        "- Title, company, end date, days remaining\n"
        "- Current status (wfstate)\n"
        "- Auto-renewal term\n"
        "- Contract amount"
    )

    steps.append(
        "\nSuggest actions for each category:\n"
        "- URGENT: Immediate review and renewal decision needed\n"
        "- UPCOMING: Schedule renewal discussions\n"
        "- PLANNING: Add to renewal pipeline"
    )

    steps.append(
        "\nOffer to drill into any specific contract for a full review."
    )

    return GetPromptResult(
        description=f"Contract renewal check - next {days_ahead} days",
        messages=[_user_msg("\n".join(steps))],
    )


# ---------------------------------------------------------------------------
# Prompt Registry
# ---------------------------------------------------------------------------

PROMPT_REGISTRY: Dict[str, dict] = {
    "create-contract": {
        "prompt": Prompt(
            name="create-contract",
            description=(
                "Step-by-step guided contract creation. Validates contract type, "
                "company compatibility, and required fields before creating."
            ),
            arguments=[
                PromptArgument(
                    name="contract_type",
                    description="Contract type to use (optional - will show available types if omitted)",
                    required=False,
                ),
                PromptArgument(
                    name="company_name",
                    description="Company name for the contract (optional - will ask if omitted)",
                    required=False,
                ),
            ],
        ),
        "renderer": _render_create_contract,
    },
    "contract-review": {
        "prompt": Prompt(
            name="contract-review",
            description=(
                "Load a contract, present a summary, check attachments, "
                "flag health issues, and offer actions."
            ),
            arguments=[
                PromptArgument(
                    name="contract_id",
                    description="Contract ID to review (optional - will ask or search if omitted)",
                    required=False,
                ),
            ],
        ),
        "renderer": _render_contract_review,
    },
    "company-onboarding": {
        "prompt": Prompt(
            name="company-onboarding",
            description=(
                "Onboard a new company: check existence, create company record, "
                "and optionally create a primary contact."
            ),
            arguments=[
                PromptArgument(
                    name="company_name",
                    description="Company name to onboard (optional - will ask if omitted)",
                    required=False,
                ),
            ],
        ),
        "renderer": _render_company_onboarding,
    },
    "contract-search-and-report": {
        "prompt": Prompt(
            name="contract-search-and-report",
            description=(
                "Search contracts by various criteria and format results "
                "as a summary report with statistics."
            ),
            arguments=[
                PromptArgument(
                    name="search_criteria",
                    description="Search criteria (optional - will ask if omitted)",
                    required=False,
                ),
            ],
        ),
        "renderer": _render_contract_search_report,
    },
    "contract-renewal-check": {
        "prompt": Prompt(
            name="contract-renewal-check",
            description=(
                "Find contracts expiring within N days, assess renewal status, "
                "and suggest actions organized by urgency."
            ),
            arguments=[
                PromptArgument(
                    name="days_ahead",
                    description="Number of days ahead to check for expiring contracts",
                    required=True,
                ),
            ],
        ),
        "renderer": _render_contract_renewal_check,
    },
}


def list_prompts() -> List[Prompt]:
    """Return all registered prompts."""
    return [entry["prompt"] for entry in PROMPT_REGISTRY.values()]


def get_prompt(name: str, arguments: Optional[Dict[str, str]] = None) -> GetPromptResult:
    """Render a prompt by name with the given arguments.

    Raises ValueError if the prompt name is not found.
    """
    if name not in PROMPT_REGISTRY:
        valid = ", ".join(PROMPT_REGISTRY.keys())
        raise ValueError(f"Unknown prompt: '{name}'. Valid prompts: {valid}")

    renderer = PROMPT_REGISTRY[name]["renderer"]
    return renderer(arguments or {})
