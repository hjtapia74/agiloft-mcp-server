"""
Unit tests for workflow_handlers.py
"""

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from src.workflow_handlers import (
    handle_preflight_create_contract,
    handle_create_contract_with_company,
    handle_get_contract_summary,
    handle_find_expiring_contracts,
    handle_onboard_company_with_contact,
    handle_attach_file_to_contract,
    dispatch_workflow_call,
    WORKFLOW_HANDLERS,
)


@pytest.fixture
def mock_client():
    """Create a mock AgiloftClient."""
    return AsyncMock()


def _parse(result):
    """Parse TextContent result to dict."""
    return json.loads(result[0].text)


# ---------------------------------------------------------------------------
# Tests: preflight_create_contract
# ---------------------------------------------------------------------------

class TestPreflightCreateContract:

    @pytest.mark.asyncio
    async def test_no_args_returns_active_types(self, mock_client):
        """No args should return available active contract types."""
        mock_client.search_records.return_value = [
            {"id": 1, "contract_type": "NDA", "party_type": "Customer"},
            {"id": 2, "contract_type": "MSA", "party_type": "Vendor"},
        ]

        result = await handle_preflight_create_contract({}, mock_client)
        data = _parse(result)

        assert data["success"] is True
        assert len(data["data"]["available_contract_types"]) == 2
        assert data["data"]["ready_to_create"] is False
        assert len(data["next_steps"]) > 0

    @pytest.mark.asyncio
    async def test_valid_type_and_company(self, mock_client):
        """Valid contract type + company should return ready_to_create=True."""
        # First call: contract type search
        # Second call: company search
        mock_client.search_records.side_effect = [
            [{"id": 1, "contract_type": "NDA", "party_type": "Customer"}],
            [{"id": 10, "company_name": "Acme", "type_of_company": "Customer", "status": "Active"}],
        ]

        result = await handle_preflight_create_contract(
            {"contract_type": "NDA", "company_name": "Acme"}, mock_client
        )
        data = _parse(result)

        assert data["success"] is True
        assert data["data"]["ready_to_create"] is True
        assert data["data"]["contract_type"]["contract_type"] == "NDA"
        assert data["data"]["company"]["company_name"] == "Acme"
        assert "required_fields" in data["data"]

    @pytest.mark.asyncio
    async def test_invalid_contract_type(self, mock_client):
        """Invalid contract type should return not ready with alternatives."""
        mock_client.search_records.side_effect = [
            [],  # type not found
            [{"id": 1, "contract_type": "NDA", "party_type": "Customer"}],  # fallback
        ]

        result = await handle_preflight_create_contract(
            {"contract_type": "InvalidType"}, mock_client
        )
        data = _parse(result)

        assert data["success"] is True
        assert data["data"]["ready_to_create"] is False
        assert any("not found" in w for w in data["warnings"])

    @pytest.mark.asyncio
    async def test_company_not_found(self, mock_client):
        """Company not found should warn and not be ready."""
        mock_client.search_records.side_effect = [
            [{"id": 1, "contract_type": "NDA", "party_type": "Customer"}],
            [],  # company not found
        ]

        result = await handle_preflight_create_contract(
            {"contract_type": "NDA", "company_name": "Ghost Corp"}, mock_client
        )
        data = _parse(result)

        assert data["success"] is True
        assert data["data"]["ready_to_create"] is False
        assert any("not found" in w.lower() for w in data["warnings"])

    @pytest.mark.asyncio
    async def test_type_mismatch_warning(self, mock_client):
        """Party type mismatch should generate a warning."""
        mock_client.search_records.side_effect = [
            [{"id": 1, "contract_type": "NDA", "party_type": "Vendor"}],
            [{"id": 10, "company_name": "Acme", "type_of_company": "Customer", "status": "Active"}],
        ]

        result = await handle_preflight_create_contract(
            {"contract_type": "NDA", "company_name": "Acme"}, mock_client
        )
        data = _parse(result)

        assert any("mismatch" in w.lower() for w in data["warnings"])

    @pytest.mark.asyncio
    async def test_api_error(self, mock_client):
        """API error should return workflow error."""
        mock_client.search_records.side_effect = Exception("API down")

        result = await handle_preflight_create_contract(
            {"contract_type": "NDA"}, mock_client
        )
        data = _parse(result)

        assert data["success"] is False
        assert "API down" in data["error"]


# ---------------------------------------------------------------------------
# Tests: create_contract_with_company
# ---------------------------------------------------------------------------

class TestCreateContractWithCompany:

    @pytest.mark.asyncio
    async def test_existing_company(self, mock_client):
        """Should find existing company and create contract."""
        mock_client.search_records.return_value = [
            {"id": 10, "company_name": "Acme", "type_of_company": "Customer", "status": "Active"}
        ]
        mock_client.create_record.return_value = {"success": True, "id": 100}

        result = await handle_create_contract_with_company(
            {
                "contract_data": {"record_type": "Contract", "contract_title1": "Test"},
                "company_name": "Acme",
            },
            mock_client,
        )
        data = _parse(result)

        assert data["success"] is True
        assert data["data"]["company_action"] == "found_existing"
        assert data["data"]["contract"] is not None
        # Verify contract was created with colon-prefixed company_name
        create_call = mock_client.create_record.call_args
        assert create_call[0][1]["company_name"] == ":Acme"

    @pytest.mark.asyncio
    async def test_create_missing_company(self, mock_client):
        """Should create company when missing and flag is set."""
        mock_client.search_records.return_value = []  # company not found
        mock_client.create_record.side_effect = [
            {"success": True, "id": 20},  # company creation
            {"success": True, "id": 100},  # contract creation
        ]

        result = await handle_create_contract_with_company(
            {
                "contract_data": {"record_type": "Contract"},
                "company_name": "NewCo",
                "create_company_if_missing": True,
                "company_data": {"type_of_company": "Customer", "status": "Active"},
            },
            mock_client,
        )
        data = _parse(result)

        assert data["success"] is True
        assert data["data"]["company_action"] == "created_new"

    @pytest.mark.asyncio
    async def test_company_missing_no_create(self, mock_client):
        """Should error when company missing and create flag is false."""
        mock_client.search_records.return_value = []

        result = await handle_create_contract_with_company(
            {
                "contract_data": {"record_type": "Contract"},
                "company_name": "Ghost Corp",
            },
            mock_client,
        )
        data = _parse(result)

        assert data["success"] is False
        assert "not found" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_api_error_returns_partial(self, mock_client):
        """API error during contract creation should return partial data."""
        mock_client.search_records.return_value = [
            {"id": 10, "company_name": "Acme"}
        ]
        mock_client.create_record.side_effect = Exception("Create failed")

        result = await handle_create_contract_with_company(
            {
                "contract_data": {"record_type": "Contract"},
                "company_name": "Acme",
            },
            mock_client,
        )
        data = _parse(result)

        assert data["success"] is False
        assert data["partial_data"]["company"] is not None


# ---------------------------------------------------------------------------
# Tests: get_contract_summary
# ---------------------------------------------------------------------------

class TestGetContractSummary:

    @pytest.mark.asyncio
    async def test_full_summary(self, mock_client):
        """Should return contract + company + attachments."""
        future_date = (datetime.now() + timedelta(days=15)).strftime("%Y-%m-%d")
        mock_client.get_record.return_value = {
            "id": 1, "contract_title1": "Test", "company_name": "Acme",
            "contract_end_date": future_date, "wfstate": "Active",
            "contract_amount": 50000, "internal_contract_owner": "John",
            "date_signed": "2024-01-01",
        }
        mock_client.search_records.return_value = [
            {"id": 10, "company_name": "Acme", "type_of_company": "Customer", "status": "Active"}
        ]
        mock_client.get_attachment_info.return_value = {"count": 2, "files": []}

        result = await handle_get_contract_summary(
            {"contract_id": 1}, mock_client,
        )
        data = _parse(result)

        assert data["success"] is True
        assert data["data"]["contract"]["id"] == 1
        assert "company" in data["data"]
        assert "attachments" in data["data"]
        # Should flag expiring soon
        assert any("expires" in issue.lower() or "urgent" in issue.lower()
                    for issue in data["data"].get("health_issues", []))

    @pytest.mark.asyncio
    async def test_missing_fields_flagged(self, mock_client):
        """Missing key fields should create health issues."""
        mock_client.get_record.return_value = {
            "id": 1, "contract_title1": "Test", "wfstate": "Draft",
        }
        mock_client.get_attachment_info.side_effect = Exception("No field")

        result = await handle_get_contract_summary(
            {"contract_id": 1}, mock_client,
        )
        data = _parse(result)

        assert data["success"] is True
        health = data["data"].get("health_issues", [])
        assert any("amount" in h.lower() for h in health)
        assert any("owner" in h.lower() for h in health)
        assert any("signed" in h.lower() for h in health)
        assert any("draft" in h.lower() for h in health)

    @pytest.mark.asyncio
    async def test_api_error(self, mock_client):
        """Should handle API error gracefully."""
        mock_client.get_record.side_effect = Exception("Not found")

        result = await handle_get_contract_summary(
            {"contract_id": 999}, mock_client,
        )
        data = _parse(result)

        assert data["success"] is False


# ---------------------------------------------------------------------------
# Tests: find_expiring_contracts
# ---------------------------------------------------------------------------

class TestFindExpiringContracts:

    @pytest.mark.asyncio
    async def test_categorizes_by_urgency(self, mock_client):
        """Should categorize contracts into URGENT/UPCOMING/PLANNING."""
        now = datetime.now()
        contracts = [
            {"id": 1, "contract_title1": "Urgent",
             "contract_end_date": (now + timedelta(days=10)).strftime("%Y-%m-%d")},
            {"id": 2, "contract_title1": "Upcoming",
             "contract_end_date": (now + timedelta(days=45)).strftime("%Y-%m-%d")},
            {"id": 3, "contract_title1": "Planning",
             "contract_end_date": (now + timedelta(days=80)).strftime("%Y-%m-%d")},
        ]
        mock_client.search_records.return_value = contracts

        result = await handle_find_expiring_contracts(
            {"days_from_now": 90}, mock_client,
        )
        data = _parse(result)

        assert data["success"] is True
        assert data["data"]["summary"]["urgent_count"] == 1
        assert data["data"]["summary"]["upcoming_count"] == 1
        assert data["data"]["summary"]["planning_count"] == 1

    @pytest.mark.asyncio
    async def test_include_expired(self, mock_client):
        """include_expired should include past-due contracts."""
        now = datetime.now()
        contracts = [
            {"id": 1, "contract_end_date": (now - timedelta(days=5)).strftime("%Y-%m-%d")},
            {"id": 2, "contract_end_date": (now + timedelta(days=10)).strftime("%Y-%m-%d")},
        ]
        mock_client.search_records.return_value = contracts

        result = await handle_find_expiring_contracts(
            {"days_from_now": 30, "include_expired": True}, mock_client,
        )
        data = _parse(result)

        assert data["data"]["summary"]["expired_count"] == 1
        assert "expired" in data["data"]

    @pytest.mark.asyncio
    async def test_no_results(self, mock_client):
        """Empty results should suggest increasing range."""
        mock_client.search_records.return_value = []

        result = await handle_find_expiring_contracts(
            {"days_from_now": 30}, mock_client,
        )
        data = _parse(result)

        assert data["success"] is True
        assert data["data"]["summary"]["total_found"] == 0
        assert any("no contracts" in s.lower() for s in data["next_steps"])

    @pytest.mark.asyncio
    async def test_status_filter(self, mock_client):
        """status_filter should be included in query."""
        mock_client.search_records.return_value = []

        await handle_find_expiring_contracts(
            {"days_from_now": 90, "status_filter": "Active"}, mock_client,
        )

        query = mock_client.search_records.call_args[0][1]
        assert "wfstate='Active'" in query

    @pytest.mark.asyncio
    async def test_default_days(self, mock_client):
        """Default days_from_now should be 90."""
        mock_client.search_records.return_value = []

        await handle_find_expiring_contracts({}, mock_client)

        # Verify the query spans ~90 days
        query = mock_client.search_records.call_args[0][1]
        future = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
        assert future in query


# ---------------------------------------------------------------------------
# Tests: onboard_company_with_contact
# ---------------------------------------------------------------------------

class TestOnboardCompanyWithContact:

    @pytest.mark.asyncio
    async def test_create_new_company(self, mock_client):
        """Should create company when it doesn't exist."""
        mock_client.search_records.return_value = []  # no existing company
        mock_client.create_record.return_value = {"success": True, "id": 20}

        result = await handle_onboard_company_with_contact(
            {
                "company_data": {
                    "company_name": "NewCo",
                    "type_of_company": "Customer",
                    "status": "Active",
                },
            },
            mock_client,
        )
        data = _parse(result)

        assert data["success"] is True
        assert data["data"]["company_action"] == "created"

    @pytest.mark.asyncio
    async def test_company_exists_skip(self, mock_client):
        """Should skip creation when company exists and skip_if_exists=True."""
        mock_client.search_records.return_value = [
            {"id": 10, "company_name": "ExistCo"}
        ]

        result = await handle_onboard_company_with_contact(
            {
                "company_data": {"company_name": "ExistCo", "type_of_company": "Customer", "status": "Active"},
                "skip_if_exists": True,
            },
            mock_client,
        )
        data = _parse(result)

        assert data["success"] is True
        assert data["data"]["company_action"] == "already_exists"

    @pytest.mark.asyncio
    async def test_company_exists_error(self, mock_client):
        """Should error when company exists and skip_if_exists=False."""
        mock_client.search_records.return_value = [
            {"id": 10, "company_name": "ExistCo"}
        ]

        result = await handle_onboard_company_with_contact(
            {
                "company_data": {"company_name": "ExistCo", "type_of_company": "Customer", "status": "Active"},
            },
            mock_client,
        )
        data = _parse(result)

        assert data["success"] is False
        assert "already exists" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_create_with_contact(self, mock_client):
        """Should create both company and contact."""
        mock_client.search_records.return_value = []
        mock_client.create_record.side_effect = [
            {"success": True, "id": 20},  # company
            {"success": True, "id": 30},  # contact
        ]

        result = await handle_onboard_company_with_contact(
            {
                "company_data": {
                    "company_name": "NewCo",
                    "type_of_company": "Customer",
                    "status": "Active",
                },
                "contact_data": {
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "email": "jane@newco.com",
                },
            },
            mock_client,
        )
        data = _parse(result)

        assert data["success"] is True
        assert data["data"]["company_action"] == "created"
        assert data["data"]["contact_action"] == "created"
        # Verify contact was created with colon-prefixed company_name
        contact_call = mock_client.create_record.call_args_list[1]
        assert contact_call[0][1]["company_name"] == ":NewCo"

    @pytest.mark.asyncio
    async def test_missing_company_name(self, mock_client):
        """Should error when company_name is missing."""
        result = await handle_onboard_company_with_contact(
            {"company_data": {"type_of_company": "Customer"}},
            mock_client,
        )
        data = _parse(result)

        assert data["success"] is False
        assert "company_name" in data["error"].lower()


# ---------------------------------------------------------------------------
# Tests: dispatch_workflow_call
# ---------------------------------------------------------------------------

class TestDispatchWorkflowCall:

    @pytest.mark.asyncio
    async def test_dispatches_correctly(self, mock_client):
        """Should dispatch to the correct handler."""
        mock_client.search_records.return_value = [
            {"id": 1, "contract_type": "NDA", "party_type": "Customer"},
        ]

        dispatch = {"agiloft_preflight_create_contract": "preflight_create_contract"}
        result = await dispatch_workflow_call(
            "agiloft_preflight_create_contract", {}, mock_client, dispatch,
        )
        data = _parse(result)

        assert data["success"] is True
        assert data["operation"] == "preflight_create_contract"

    @pytest.mark.asyncio
    async def test_unknown_tool_raises(self, mock_client):
        """Unknown workflow tool should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown workflow tool"):
            await dispatch_workflow_call(
                "agiloft_nonexistent", {}, mock_client, {},
            )

    @pytest.mark.asyncio
    async def test_unknown_handler_raises(self, mock_client):
        """Unknown handler name should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown workflow handler"):
            await dispatch_workflow_call(
                "agiloft_test", {}, mock_client,
                {"agiloft_test": "nonexistent_handler"},
            )

    def test_all_handlers_registered(self):
        """All handler names in dispatch should be in WORKFLOW_HANDLERS."""
        expected = [
            "preflight_create_contract",
            "create_contract_with_company",
            "get_contract_summary",
            "find_expiring_contracts",
            "onboard_company_with_contact",
            "attach_file_to_contract",
        ]
        for name in expected:
            assert name in WORKFLOW_HANDLERS, f"Missing handler: {name}"


# ---------------------------------------------------------------------------
# Tests: attach_file_to_contract
# ---------------------------------------------------------------------------

class TestAttachFileToContract:

    @pytest.mark.asyncio
    async def test_successful_upload(self, mock_client, tmp_path):
        """Should create attachment record and upload file."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"PDF content here")

        mock_client.get_record.return_value = {
            "id": 100, "contract_title1": "Test Contract"
        }
        mock_client.create_record.return_value = {
            "success": True, "result": 501
        }
        mock_client.attach_file.return_value = {"success": True}
        mock_client.get_attachment_info.return_value = {
            "count": 1, "files": [{"name": "test.pdf"}]
        }

        result = await handle_attach_file_to_contract(
            {
                "contract_id": 100,
                "file_path": str(test_file),
            },
            mock_client,
        )
        data = _parse(result)

        assert data["success"] is True
        assert data["data"]["attachment_id"] == 501
        assert data["data"]["file_info"]["count"] == 1
        # Verify attachment record was created with colon-prefixed contract_title
        create_call = mock_client.create_record.call_args
        assert create_call[0][1]["contract_title"] == ":Test Contract"
        # Verify file_name was derived from path
        attach_call = mock_client.attach_file.call_args
        assert attach_call[0][3] == "test.pdf"
        assert attach_call[0][4] == b"PDF content here"

    @pytest.mark.asyncio
    async def test_missing_file_path(self, mock_client):
        """Should error when file_path is not provided."""
        result = await handle_attach_file_to_contract(
            {"contract_id": 100},
            mock_client,
        )
        data = _parse(result)

        assert data["success"] is False
        assert "file_path" in data["error"]

    @pytest.mark.asyncio
    async def test_sandbox_path_rejected(self, mock_client):
        """Should reject sandbox paths with a helpful message."""
        result = await handle_attach_file_to_contract(
            {
                "contract_id": 100,
                "file_path": "/mnt/user-data/uploads/contract.pdf",
            },
            mock_client,
        )
        data = _parse(result)

        assert data["success"] is False
        assert "sandbox" in data["error"].lower()
        assert "ask the user" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_home_claude_path_rejected(self, mock_client):
        """Should reject /home/claude/ paths."""
        result = await handle_attach_file_to_contract(
            {
                "contract_id": 100,
                "file_path": "/home/claude/contract.docx",
            },
            mock_client,
        )
        data = _parse(result)

        assert data["success"] is False
        assert "sandbox" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_file_path_not_found(self, mock_client):
        """Should error when file_path doesn't exist."""
        result = await handle_attach_file_to_contract(
            {
                "contract_id": 100,
                "file_path": "/Users/someone/nonexistent/file.pdf",
            },
            mock_client,
        )
        data = _parse(result)

        assert data["success"] is False
        assert "not found" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_contract_not_found(self, mock_client, tmp_path):
        """Should error when contract doesn't exist."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"hello")
        mock_client.get_record.side_effect = Exception("Record not found")

        result = await handle_attach_file_to_contract(
            {
                "contract_id": 999,
                "file_path": str(test_file),
            },
            mock_client,
        )
        data = _parse(result)

        assert data["success"] is False
        assert "not found" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_contract_missing_title(self, mock_client, tmp_path):
        """Should error when contract has no title."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"hello")
        mock_client.get_record.return_value = {"id": 100}

        result = await handle_attach_file_to_contract(
            {
                "contract_id": 100,
                "file_path": str(test_file),
            },
            mock_client,
        )
        data = _parse(result)

        assert data["success"] is False
        assert "title" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_attachment_creation_failure(self, mock_client, tmp_path):
        """Should return partial data when attachment creation fails."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"hello")

        mock_client.get_record.return_value = {
            "id": 100, "contract_title1": "Test Contract"
        }
        mock_client.create_record.side_effect = Exception("Create failed")

        result = await handle_attach_file_to_contract(
            {
                "contract_id": 100,
                "file_path": str(test_file),
            },
            mock_client,
        )
        data = _parse(result)

        assert data["success"] is False
        assert data["partial_data"]["contract"]["id"] == 100

    @pytest.mark.asyncio
    async def test_custom_attachment_title(self, mock_client, tmp_path):
        """Should use custom attachment_title when provided."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"hello")

        mock_client.get_record.return_value = {
            "id": 100, "contract_title1": "Test Contract"
        }
        mock_client.create_record.return_value = {
            "success": True, "result": 501
        }
        mock_client.attach_file.return_value = {"success": True}
        mock_client.get_attachment_info.return_value = {"count": 1, "files": []}

        await handle_attach_file_to_contract(
            {
                "contract_id": 100,
                "file_path": str(test_file),
                "attachment_title": "Custom Title",
            },
            mock_client,
        )

        create_call = mock_client.create_record.call_args
        assert create_call[0][1]["title"] == "Custom Title"

    @pytest.mark.asyncio
    async def test_file_name_derived_from_path(self, mock_client, tmp_path):
        """Should derive file_name from file_path when not provided."""
        test_file = tmp_path / "my_document.docx"
        test_file.write_bytes(b"docx content")

        mock_client.get_record.return_value = {
            "id": 100, "contract_title1": "Test"
        }
        mock_client.create_record.return_value = {
            "success": True, "result": 501
        }
        mock_client.attach_file.return_value = {"success": True}
        mock_client.get_attachment_info.return_value = {"count": 1, "files": []}

        result = await handle_attach_file_to_contract(
            {"contract_id": 100, "file_path": str(test_file)},
            mock_client,
        )
        data = _parse(result)

        assert data["success"] is True
        attach_call = mock_client.attach_file.call_args
        assert attach_call[0][3] == "my_document.docx"
