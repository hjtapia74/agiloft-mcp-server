"""
Unit tests for tool_generator.py
"""

import pytest
from mcp.types import Tool
from src.tool_generator import generate_tools


class TestToolGenerator:
    """Test MCP tool generation from entity registry."""

    def setup_method(self):
        """Generate tools once for all tests."""
        self.tools, self.dispatch = generate_tools()

    def test_tools_are_tool_objects(self):
        """All generated items should be mcp.types.Tool instances."""
        for tool in self.tools:
            assert isinstance(tool, Tool)

    def test_expected_contract_tools(self):
        """All 12 contract tools should be generated."""
        tool_names = [t.name for t in self.tools]
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
        for name in expected:
            assert name in tool_names, f"Missing tool: {name}"

    def test_expected_company_tools(self):
        """All 12 company tools should be generated."""
        tool_names = [t.name for t in self.tools]
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
        for name in expected:
            assert name in tool_names, f"Missing tool: {name}"

    def test_expected_attachment_tools(self):
        """All 12 attachment tools should be generated."""
        tool_names = [t.name for t in self.tools]
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
        for name in expected:
            assert name in tool_names, f"Missing tool: {name}"

    def test_expected_contact_tools(self):
        """All 12 contact tools should be generated."""
        tool_names = [t.name for t in self.tools]
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
        for name in expected:
            assert name in tool_names, f"Missing tool: {name}"

    def test_expected_employee_tools(self):
        """All 12 employee tools should be generated."""
        tool_names = [t.name for t in self.tools]
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
        for name in expected:
            assert name in tool_names, f"Missing tool: {name}"

    def test_expected_customer_tools(self):
        """All 12 customer tools should be generated."""
        tool_names = [t.name for t in self.tools]
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
        for name in expected:
            assert name in tool_names, f"Missing tool: {name}"

    def test_dispatch_matches_tools(self):
        """Dispatch map should have an entry for every generated tool."""
        tool_names = {t.name for t in self.tools}
        dispatch_names = set(self.dispatch.keys())
        assert tool_names == dispatch_names

    def test_dispatch_values_are_tuples(self):
        """Each dispatch value should be (entity_key, action) tuple."""
        for tool_name, value in self.dispatch.items():
            assert isinstance(value, tuple)
            assert len(value) == 2
            entity_key, action = value
            assert isinstance(entity_key, str)
            assert isinstance(action, str)

    def test_search_tool_has_query_required(self):
        """Search tool should require the 'query' field."""
        search_tool = next(t for t in self.tools if t.name == "agiloft_search_contracts")
        assert "query" in search_tool.inputSchema["required"]

    def test_get_tool_has_record_id_required(self):
        """Get tool should require 'record_id'."""
        get_tool = next(t for t in self.tools if t.name == "agiloft_get_contract")
        assert "record_id" in get_tool.inputSchema["required"]

    def test_create_tool_has_data_required(self):
        """Create tool should require 'data'."""
        create_tool = next(t for t in self.tools if t.name == "agiloft_create_contract")
        assert "data" in create_tool.inputSchema["required"]

    def test_create_tool_data_has_additional_properties(self):
        """Create tool's data schema should allow additional properties."""
        create_tool = next(t for t in self.tools if t.name == "agiloft_create_contract")
        data_schema = create_tool.inputSchema["properties"]["data"]
        assert data_schema.get("additionalProperties") is True

    def test_delete_tool_has_enum_delete_rules(self):
        """Delete tool should have delete_rule enum."""
        delete_tool = next(t for t in self.tools if t.name == "agiloft_delete_contract")
        delete_rule = delete_tool.inputSchema["properties"]["delete_rule"]
        assert "enum" in delete_rule
        assert "ERROR_IF_DEPENDANTS" in delete_rule["enum"]

    def test_upsert_tool_requires_query_and_data(self):
        """Upsert tool should require both query and data."""
        upsert_tool = next(t for t in self.tools if t.name == "agiloft_upsert_contract")
        assert "query" in upsert_tool.inputSchema["required"]
        assert "data" in upsert_tool.inputSchema["required"]

    def test_attach_file_tool_requires_all_fields(self):
        """Attach file tool should require record_id, field, file_name, file_content_base64."""
        attach_tool = next(t for t in self.tools if t.name == "agiloft_attach_file_contract")
        required = attach_tool.inputSchema["required"]
        assert "record_id" in required
        assert "field" in required
        assert "file_name" in required
        assert "file_content_base64" in required

    def test_all_tools_have_descriptions(self):
        """Every tool should have a non-empty description."""
        for tool in self.tools:
            assert tool.description, f"Tool {tool.name} has no description"
            assert len(tool.description) > 20, f"Tool {tool.name} description too short"

    def test_all_tools_have_valid_input_schema(self):
        """Every tool should have a valid JSON schema."""
        for tool in self.tools:
            schema = tool.inputSchema
            assert schema["type"] == "object"
            assert "properties" in schema
            assert "required" in schema

    def test_action_button_tool_requires_record_id_and_button_name(self):
        """Action button tool should require record_id and button_name."""
        action_button_tool = next(t for t in self.tools if t.name == "agiloft_action_button_contract")
        required = action_button_tool.inputSchema["required"]
        assert "record_id" in required
        assert "button_name" in required

    def test_evaluate_format_tool_requires_record_id_and_formula(self):
        """Evaluate format tool should require record_id and formula."""
        evaluate_format_tool = next(t for t in self.tools if t.name == "agiloft_evaluate_format_contract")
        required = evaluate_format_tool.inputSchema["required"]
        assert "record_id" in required
        assert "formula" in required

    def test_action_button_tools_generated_for_all_entities(self):
        """Action button tools should be generated for all 6 entities."""
        tool_names = [t.name for t in self.tools]
        expected = [
            "agiloft_action_button_contract",
            "agiloft_action_button_company",
            "agiloft_action_button_attachment",
            "agiloft_action_button_contact",
            "agiloft_action_button_employee",
            "agiloft_action_button_customer",
        ]
        for name in expected:
            assert name in tool_names, f"Missing action button tool: {name}"

    def test_evaluate_format_tools_generated_for_all_entities(self):
        """Evaluate format tools should be generated for all 6 entities."""
        tool_names = [t.name for t in self.tools]
        expected = [
            "agiloft_evaluate_format_contract",
            "agiloft_evaluate_format_company",
            "agiloft_evaluate_format_attachment",
            "agiloft_evaluate_format_contact",
            "agiloft_evaluate_format_employee",
            "agiloft_evaluate_format_customer",
        ]
        for name in expected:
            assert name in tool_names, f"Missing evaluate format tool: {name}"

    def test_tool_count(self):
        """Verify total tool count is 72 (12 per entity × 6 entities)."""
        assert len(self.tools) == 72
