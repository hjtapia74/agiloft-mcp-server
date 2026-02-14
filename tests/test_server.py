"""
Unit tests for server.py (refactored to generic architecture)

Tests the tool dispatch mechanism through dispatch_tool_call,
which is how server.py routes all tool calls.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from mcp.types import TextContent
from src.tool_handlers import dispatch_tool_call
from src.tool_generator import generate_tools
from src.entity_registry import ENTITY_REGISTRY


@pytest.fixture
def mock_agiloft_client():
    """Create a mock AgiloftClient."""
    return AsyncMock()


@pytest.fixture
def tool_dispatch():
    """Get the tool dispatch mapping."""
    _, dispatch = generate_tools()
    return dispatch


class TestToolDispatch:
    """Test that tool names are generated correctly and dispatch works."""

    def test_contract_tools_registered(self, tool_dispatch):
        """Verify all 12 contract tools are registered."""
        expected = [
            "agiloft_search_contracts",
            "agiloft_get_contract",
            "agiloft_create_contract",
            "agiloft_update_contract",
            "agiloft_delete_contract",
            "agiloft_upsert_contract",
            "agiloft_attach_file_contract",
            "agiloft_retrieve_attachment_contract",
            "agiloft_remove_attachment_contract",
            "agiloft_get_attachment_info_contract",
            "agiloft_action_button_contract",
            "agiloft_evaluate_format_contract",
        ]
        for tool_name in expected:
            assert tool_name in tool_dispatch, f"Missing tool: {tool_name}"

    def test_company_tools_registered(self, tool_dispatch):
        """Verify all 12 company tools are registered."""
        expected = [
            "agiloft_search_companies",
            "agiloft_get_company",
            "agiloft_create_company",
            "agiloft_update_company",
            "agiloft_delete_company",
            "agiloft_upsert_company",
            "agiloft_attach_file_company",
            "agiloft_retrieve_attachment_company",
            "agiloft_remove_attachment_company",
            "agiloft_get_attachment_info_company",
            "agiloft_action_button_company",
            "agiloft_evaluate_format_company",
        ]
        for tool_name in expected:
            assert tool_name in tool_dispatch, f"Missing tool: {tool_name}"

    def test_attachment_tools_registered(self, tool_dispatch):
        """Verify all 12 attachment tools are registered."""
        expected = [
            "agiloft_search_attachments",
            "agiloft_get_attachment",
            "agiloft_create_attachment",
            "agiloft_update_attachment",
            "agiloft_delete_attachment",
            "agiloft_upsert_attachment",
            "agiloft_attach_file_attachment",
            "agiloft_retrieve_attachment_attachment",
            "agiloft_remove_attachment_attachment",
            "agiloft_get_attachment_info_attachment",
            "agiloft_action_button_attachment",
            "agiloft_evaluate_format_attachment",
        ]
        for tool_name in expected:
            assert tool_name in tool_dispatch, f"Missing tool: {tool_name}"

    def test_contact_tools_registered(self, tool_dispatch):
        """Verify all 12 contact tools are registered."""
        expected = [
            "agiloft_search_contacts",
            "agiloft_get_contact",
            "agiloft_create_contact",
            "agiloft_update_contact",
            "agiloft_delete_contact",
            "agiloft_upsert_contact",
            "agiloft_attach_file_contact",
            "agiloft_retrieve_attachment_contact",
            "agiloft_remove_attachment_contact",
            "agiloft_get_attachment_info_contact",
            "agiloft_action_button_contact",
            "agiloft_evaluate_format_contact",
        ]
        for tool_name in expected:
            assert tool_name in tool_dispatch, f"Missing tool: {tool_name}"

    def test_employee_tools_registered(self, tool_dispatch):
        """Verify all 12 employee tools are registered."""
        expected = [
            "agiloft_search_employees",
            "agiloft_get_employee",
            "agiloft_create_employee",
            "agiloft_update_employee",
            "agiloft_delete_employee",
            "agiloft_upsert_employee",
            "agiloft_attach_file_employee",
            "agiloft_retrieve_attachment_employee",
            "agiloft_remove_attachment_employee",
            "agiloft_get_attachment_info_employee",
            "agiloft_action_button_employee",
            "agiloft_evaluate_format_employee",
        ]
        for tool_name in expected:
            assert tool_name in tool_dispatch, f"Missing tool: {tool_name}"

    def test_customer_tools_registered(self, tool_dispatch):
        """Verify all 12 customer tools are registered."""
        expected = [
            "agiloft_search_customers",
            "agiloft_get_customer",
            "agiloft_create_customer",
            "agiloft_update_customer",
            "agiloft_delete_customer",
            "agiloft_upsert_customer",
            "agiloft_attach_file_customer",
            "agiloft_retrieve_attachment_customer",
            "agiloft_remove_attachment_customer",
            "agiloft_get_attachment_info_customer",
            "agiloft_action_button_customer",
            "agiloft_evaluate_format_customer",
        ]
        for tool_name in expected:
            assert tool_name in tool_dispatch, f"Missing tool: {tool_name}"

    def test_dispatch_maps_to_correct_entity(self, tool_dispatch):
        """Verify dispatch maps each tool to the correct entity."""
        entity_tool_prefixes = {
            "contract": ["_contracts", "_contract"],
            "company": ["_companies", "_company"],
            "attachment": ["_attachments", "_attachment"],
            "contact": ["_contacts", "_contact"],
            "employee": ["_employees", "_employee"],
            "customer": ["_customers", "_customer"],
        }
        for tool_name, (entity_key, action) in tool_dispatch.items():
            # Verify entity_key is a valid entity
            assert entity_key in entity_tool_prefixes, \
                f"Tool {tool_name} maps to unknown entity '{entity_key}'"
            # Verify the tool name is consistent with its entity mapping
            suffixes = entity_tool_prefixes[entity_key]
            assert any(tool_name.endswith(s) for s in suffixes), \
                f"Tool {tool_name} mapped to '{entity_key}' but name doesn't match expected suffixes {suffixes}"

    def test_tool_count(self, tool_dispatch):
        """Verify total tool count matches expected."""
        tools, _ = generate_tools()
        assert len(tools) == 72  # 12 per entity × 6 entities (contract, company, attachment, contact, employee, customer)


class TestSearchHandler:
    """Test search tool dispatch."""

    @pytest.mark.asyncio
    async def test_search_natural_language(self, mock_agiloft_client, tool_dispatch):
        """Test search with natural language query (sanitized)."""
        mock_agiloft_client.search_records.return_value = [
            {"id": 1, "contract_title1": "Test Contract"}
        ]

        arguments = {"query": "test contracts", "limit": 10}

        result = await dispatch_tool_call(
            "agiloft_search_contracts", arguments,
            mock_agiloft_client, tool_dispatch
        )

        assert len(result) == 1
        response = json.loads(result[0].text)
        assert response["success"] is True
        assert response["operation"] == "search"
        assert response["entity"] == "contract"
        assert response["count"] == 1

        # Verify text search called once per text_search_field with ~=
        assert mock_agiloft_client.search_records.call_count == 2  # contract has 2 text fields
        calls = mock_agiloft_client.search_records.call_args_list
        queries_sent = [c[0][1] for c in calls]
        assert "contract_title1~='test contracts'" in queries_sent
        assert "company_name~='test contracts'" in queries_sent

    @pytest.mark.asyncio
    async def test_search_structured_query(self, mock_agiloft_client, tool_dispatch):
        """Test search with structured query passed through as-is."""
        mock_agiloft_client.search_records.return_value = [
            {"id": 1, "status": "Active"}
        ]

        arguments = {"query": "status=Active AND contract_amount>1000"}

        result = await dispatch_tool_call(
            "agiloft_search_contracts", arguments,
            mock_agiloft_client, tool_dispatch
        )

        # Verify structured query was passed through
        call_args = mock_agiloft_client.search_records.call_args
        assert call_args[0][1] == "status=Active AND contract_amount>1000"

    @pytest.mark.asyncio
    async def test_search_sql_injection_sanitized(self, mock_agiloft_client, tool_dispatch):
        """Test that SQL injection attempts are sanitized."""
        mock_agiloft_client.search_records.return_value = []

        # Attempt injection via natural language path
        arguments = {"query": "'; DROP TABLE contract; --"}

        result = await dispatch_tool_call(
            "agiloft_search_contracts", arguments,
            mock_agiloft_client, tool_dispatch
        )

        call_args = mock_agiloft_client.search_records.call_args
        query = call_args[0][1]
        # Single quotes doubled, -- removed, ; removed
        assert "DROP TABLE" not in query or "''" in query
        assert "--" not in query
        assert ";" not in query

    @pytest.mark.asyncio
    async def test_search_limit_applied(self, mock_agiloft_client, tool_dispatch):
        """Test that result limiting works."""
        mock_agiloft_client.search_records.return_value = [
            {"id": i} for i in range(100)
        ]

        arguments = {"query": "test", "limit": 5}

        result = await dispatch_tool_call(
            "agiloft_search_contracts", arguments,
            mock_agiloft_client, tool_dispatch
        )

        response = json.loads(result[0].text)
        assert response["count"] == 5
        assert len(response["data"]) == 5

    @pytest.mark.asyncio
    async def test_search_error(self, mock_agiloft_client, tool_dispatch):
        """Test search error handling."""
        mock_agiloft_client.search_records.side_effect = Exception("Search failed")

        arguments = {"query": "test"}

        result = await dispatch_tool_call(
            "agiloft_search_contracts", arguments,
            mock_agiloft_client, tool_dispatch
        )

        response = json.loads(result[0].text)
        assert response["success"] is False
        assert "Search failed" in response["error"]


class TestGetHandler:
    """Test get tool dispatch."""

    @pytest.mark.asyncio
    async def test_get_success(self, mock_agiloft_client, tool_dispatch):
        """Test successful get by ID."""
        mock_agiloft_client.get_record.return_value = {
            "id": 123, "contract_title1": "Test Contract"
        }

        arguments = {"record_id": 123}

        result = await dispatch_tool_call(
            "agiloft_get_contract", arguments,
            mock_agiloft_client, tool_dispatch
        )

        response = json.loads(result[0].text)
        assert response["success"] is True
        assert response["record_id"] == 123
        assert response["data"]["contract_title1"] == "Test Contract"

    @pytest.mark.asyncio
    async def test_get_with_fields(self, mock_agiloft_client, tool_dispatch):
        """Test get with field filtering."""
        mock_agiloft_client.get_record.return_value = {
            "id": 123, "contract_title1": "Test Contract"
        }

        arguments = {"record_id": 123, "fields": ["id", "contract_title1"]}

        result = await dispatch_tool_call(
            "agiloft_get_contract", arguments,
            mock_agiloft_client, tool_dispatch
        )

        mock_agiloft_client.get_record.assert_called_once_with(
            "/contract", 123, ["id", "contract_title1"]
        )

    @pytest.mark.asyncio
    async def test_get_error(self, mock_agiloft_client, tool_dispatch):
        """Test get error handling."""
        mock_agiloft_client.get_record.side_effect = Exception("Not found")

        arguments = {"record_id": 999}

        result = await dispatch_tool_call(
            "agiloft_get_contract", arguments,
            mock_agiloft_client, tool_dispatch
        )

        response = json.loads(result[0].text)
        assert response["success"] is False
        assert response["record_id"] == 999


class TestCreateHandler:
    """Test create tool dispatch."""

    @pytest.mark.asyncio
    async def test_create_success(self, mock_agiloft_client, tool_dispatch):
        """Test successful create."""
        mock_agiloft_client.create_record.return_value = {
            "success": True, "contract": {"id": 456}
        }

        arguments = {"data": {"contract_title1": "New Contract"}}

        result = await dispatch_tool_call(
            "agiloft_create_contract", arguments,
            mock_agiloft_client, tool_dispatch
        )

        response = json.loads(result[0].text)
        assert response["success"] is True
        mock_agiloft_client.create_record.assert_called_once_with(
            "/contract", {"contract_title1": "New Contract"}
        )

    @pytest.mark.asyncio
    async def test_create_error(self, mock_agiloft_client, tool_dispatch):
        """Test create error handling."""
        mock_agiloft_client.create_record.side_effect = Exception("Validation failed")

        arguments = {"data": {}}

        result = await dispatch_tool_call(
            "agiloft_create_contract", arguments,
            mock_agiloft_client, tool_dispatch
        )

        response = json.loads(result[0].text)
        assert response["success"] is False


class TestUpdateHandler:
    """Test update tool dispatch."""

    @pytest.mark.asyncio
    async def test_update_success(self, mock_agiloft_client, tool_dispatch):
        """Test successful update."""
        mock_agiloft_client.update_record.return_value = {"success": True}

        arguments = {"record_id": 123, "data": {"contract_title1": "Updated"}}

        result = await dispatch_tool_call(
            "agiloft_update_contract", arguments,
            mock_agiloft_client, tool_dispatch
        )

        response = json.loads(result[0].text)
        assert response["success"] is True
        assert response["record_id"] == 123
        mock_agiloft_client.update_record.assert_called_once_with(
            "/contract", 123, {"contract_title1": "Updated"}
        )


class TestDeleteHandler:
    """Test delete tool dispatch."""

    @pytest.mark.asyncio
    async def test_delete_success(self, mock_agiloft_client, tool_dispatch):
        """Test successful delete."""
        mock_agiloft_client.delete_record.return_value = {"success": True}

        arguments = {"record_id": 123, "delete_rule": "ERROR_IF_DEPENDANTS"}

        result = await dispatch_tool_call(
            "agiloft_delete_contract", arguments,
            mock_agiloft_client, tool_dispatch
        )

        response = json.loads(result[0].text)
        assert response["success"] is True
        mock_agiloft_client.delete_record.assert_called_once_with(
            "/contract", 123, "ERROR_IF_DEPENDANTS"
        )

    @pytest.mark.asyncio
    async def test_delete_default_rule(self, mock_agiloft_client, tool_dispatch):
        """Test delete with default delete rule."""
        mock_agiloft_client.delete_record.return_value = {"success": True}

        arguments = {"record_id": 123}

        await dispatch_tool_call(
            "agiloft_delete_contract", arguments,
            mock_agiloft_client, tool_dispatch
        )

        mock_agiloft_client.delete_record.assert_called_once_with(
            "/contract", 123, "UNLINK_WHERE_POSSIBLE_OTHERWISE_DELETE"
        )


class TestUpsertHandler:
    """Test upsert tool dispatch."""

    @pytest.mark.asyncio
    async def test_upsert_success(self, mock_agiloft_client, tool_dispatch):
        """Test successful upsert."""
        mock_agiloft_client.upsert_record.return_value = {"success": True}

        arguments = {
            "query": "salesforce_contract_id~='SF-123'",
            "data": {"contract_title1": "Upserted Contract"},
        }

        result = await dispatch_tool_call(
            "agiloft_upsert_contract", arguments,
            mock_agiloft_client, tool_dispatch
        )

        response = json.loads(result[0].text)
        assert response["success"] is True
        mock_agiloft_client.upsert_record.assert_called_once_with(
            "/contract",
            "salesforce_contract_id~='SF-123'",
            {"contract_title1": "Upserted Contract"},
        )


class TestActionButtonHandler:
    """Test action button tool dispatch."""

    @pytest.mark.asyncio
    async def test_action_button_success(self, mock_agiloft_client, tool_dispatch):
        """Test successful action button trigger."""
        mock_agiloft_client.trigger_action_button.return_value = {
            "success": True, "message": "Action button executed"
        }

        arguments = {"record_id": 123, "button_name": "approve"}

        result = await dispatch_tool_call(
            "agiloft_action_button_contract", arguments,
            mock_agiloft_client, tool_dispatch
        )

        response = json.loads(result[0].text)
        assert response["success"] is True
        assert response["operation"] == "action_button"
        assert response["record_id"] == 123
        mock_agiloft_client.trigger_action_button.assert_called_once_with(
            "/contract", 123, "approve"
        )

    @pytest.mark.asyncio
    async def test_action_button_error(self, mock_agiloft_client, tool_dispatch):
        """Test action button error handling."""
        mock_agiloft_client.trigger_action_button.side_effect = Exception("Button not found")

        arguments = {"record_id": 123, "button_name": "invalid_button"}

        result = await dispatch_tool_call(
            "agiloft_action_button_contract", arguments,
            mock_agiloft_client, tool_dispatch
        )

        response = json.loads(result[0].text)
        assert response["success"] is False
        assert "Button not found" in response["error"]


class TestEvaluateFormatHandler:
    """Test evaluate format tool dispatch."""

    @pytest.mark.asyncio
    async def test_evaluate_format_success(self, mock_agiloft_client, tool_dispatch):
        """Test successful formula evaluation."""
        mock_agiloft_client.evaluate_format.return_value = {
            "success": True, "result": "Calculated Value"
        }

        arguments = {"record_id": 123, "formula": "$contract_amount * 1.1"}

        result = await dispatch_tool_call(
            "agiloft_evaluate_format_contract", arguments,
            mock_agiloft_client, tool_dispatch
        )

        response = json.loads(result[0].text)
        assert response["success"] is True
        assert response["operation"] == "evaluate_format"
        assert response["record_id"] == 123
        mock_agiloft_client.evaluate_format.assert_called_once_with(
            "/contract", 123, "$contract_amount * 1.1"
        )

    @pytest.mark.asyncio
    async def test_evaluate_format_error(self, mock_agiloft_client, tool_dispatch):
        """Test evaluate format error handling."""
        mock_agiloft_client.evaluate_format.side_effect = Exception("Invalid formula")

        arguments = {"record_id": 123, "formula": "invalid syntax"}

        result = await dispatch_tool_call(
            "agiloft_evaluate_format_contract", arguments,
            mock_agiloft_client, tool_dispatch
        )

        response = json.loads(result[0].text)
        assert response["success"] is False
        assert "Invalid formula" in response["error"]


class TestUnknownTool:
    """Test error handling for unknown tools."""

    @pytest.mark.asyncio
    async def test_unknown_tool_raises(self, mock_agiloft_client, tool_dispatch):
        """Test that unknown tools raise ValueError."""
        with pytest.raises(ValueError, match="Unknown tool"):
            await dispatch_tool_call(
                "agiloft_nonexistent_tool", {},
                mock_agiloft_client, tool_dispatch
            )
