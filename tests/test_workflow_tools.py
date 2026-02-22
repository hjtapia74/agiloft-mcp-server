"""
Unit tests for workflow_tools.py
"""

import pytest
from mcp.types import Tool

from src.workflow_tools import generate_workflow_tools
from src.tool_generator import generate_tools


class TestWorkflowToolGenerator:
    """Test composite workflow tool generation."""

    def setup_method(self):
        """Generate workflow tools once for all tests."""
        self.tools, self.dispatch = generate_workflow_tools()

    def test_generates_6_tools(self):
        """Should generate exactly 6 workflow tools."""
        assert len(self.tools) == 6

    def test_tools_are_tool_objects(self):
        """All generated items should be mcp.types.Tool instances."""
        for tool in self.tools:
            assert isinstance(tool, Tool)

    def test_expected_tool_names(self):
        """All expected workflow tools should be generated."""
        tool_names = [t.name for t in self.tools]
        expected = [
            "agiloft_preflight_create_contract",
            "agiloft_create_contract_with_company",
            "agiloft_get_contract_summary",
            "agiloft_find_expiring_contracts",
            "agiloft_onboard_company_with_contact",
            "agiloft_attach_file_to_contract",
        ]
        for name in expected:
            assert name in tool_names, f"Missing workflow tool: {name}"

    def test_dispatch_matches_tools(self):
        """Dispatch map should have an entry for every generated tool."""
        tool_names = {t.name for t in self.tools}
        dispatch_names = set(self.dispatch.keys())
        assert tool_names == dispatch_names

    def test_dispatch_values_are_strings(self):
        """Each dispatch value should be a handler name string."""
        for tool_name, handler_name in self.dispatch.items():
            assert isinstance(handler_name, str)
            assert len(handler_name) > 0

    def test_all_tools_have_descriptions(self):
        """Every tool should have a non-empty description."""
        for tool in self.tools:
            assert tool.description, f"Tool {tool.name} has no description"
            assert len(tool.description) > 20

    def test_all_tools_have_valid_input_schema(self):
        """Every tool should have a valid JSON schema."""
        for tool in self.tools:
            schema = tool.inputSchema
            assert schema["type"] == "object"
            assert "properties" in schema


class TestNoNameCollisions:
    """Verify workflow tools don't collide with entity tools."""

    def test_no_name_overlap(self):
        """Workflow tool names should not collide with entity tool names."""
        entity_tools, _ = generate_tools()
        workflow_tools, _ = generate_workflow_tools()

        entity_names = {t.name for t in entity_tools}
        workflow_names = {t.name for t in workflow_tools}

        overlap = entity_names & workflow_names
        assert not overlap, f"Name collisions found: {overlap}"


class TestPreflightCreateContractSchema:
    """Test the preflight_create_contract tool schema."""

    def setup_method(self):
        tools, _ = generate_workflow_tools()
        self.tool = next(t for t in tools if t.name == "agiloft_preflight_create_contract")

    def test_has_optional_contract_type(self):
        """contract_type should be in properties but not required."""
        schema = self.tool.inputSchema
        assert "contract_type" in schema["properties"]
        assert "contract_type" not in schema.get("required", [])

    def test_has_optional_company_name(self):
        """company_name should be in properties but not required."""
        schema = self.tool.inputSchema
        assert "company_name" in schema["properties"]
        assert "company_name" not in schema.get("required", [])

    def test_no_required_fields(self):
        """Should have no required fields (all optional)."""
        schema = self.tool.inputSchema
        assert schema.get("required", []) == []


class TestCreateContractWithCompanySchema:
    """Test the create_contract_with_company tool schema."""

    def setup_method(self):
        tools, _ = generate_workflow_tools()
        self.tool = next(t for t in tools if t.name == "agiloft_create_contract_with_company")

    def test_requires_contract_data_and_company_name(self):
        """Should require contract_data and company_name."""
        required = self.tool.inputSchema["required"]
        assert "contract_data" in required
        assert "company_name" in required

    def test_has_optional_create_company_if_missing(self):
        """create_company_if_missing should be optional with default false."""
        props = self.tool.inputSchema["properties"]
        assert "create_company_if_missing" in props
        assert props["create_company_if_missing"]["default"] is False


class TestGetContractSummarySchema:
    """Test the get_contract_summary tool schema."""

    def setup_method(self):
        tools, _ = generate_workflow_tools()
        self.tool = next(t for t in tools if t.name == "agiloft_get_contract_summary")

    def test_requires_contract_id(self):
        """Should require contract_id."""
        required = self.tool.inputSchema["required"]
        assert "contract_id" in required

    def test_contract_id_is_integer(self):
        """contract_id should be an integer."""
        props = self.tool.inputSchema["properties"]
        assert props["contract_id"]["type"] == "integer"


class TestFindExpiringContractsSchema:
    """Test the find_expiring_contracts tool schema."""

    def setup_method(self):
        tools, _ = generate_workflow_tools()
        self.tool = next(t for t in tools if t.name == "agiloft_find_expiring_contracts")

    def test_no_required_fields(self):
        """All fields should be optional."""
        assert self.tool.inputSchema.get("required", []) == []

    def test_has_days_from_now(self):
        """days_from_now should have default 90."""
        props = self.tool.inputSchema["properties"]
        assert "days_from_now" in props
        assert props["days_from_now"]["default"] == 90

    def test_has_include_expired(self):
        """include_expired should default to false."""
        props = self.tool.inputSchema["properties"]
        assert "include_expired" in props
        assert props["include_expired"]["default"] is False


class TestOnboardCompanyWithContactSchema:
    """Test the onboard_company_with_contact tool schema."""

    def setup_method(self):
        tools, _ = generate_workflow_tools()
        self.tool = next(t for t in tools if t.name == "agiloft_onboard_company_with_contact")

    def test_requires_company_data(self):
        """Should require company_data."""
        required = self.tool.inputSchema["required"]
        assert "company_data" in required

    def test_contact_data_optional(self):
        """contact_data should be optional."""
        required = self.tool.inputSchema["required"]
        assert "contact_data" not in required

    def test_skip_if_exists_default_false(self):
        """skip_if_exists should default to false."""
        props = self.tool.inputSchema["properties"]
        assert props["skip_if_exists"]["default"] is False


class TestAttachFileToContractSchema:
    """Test the attach_file_to_contract tool schema."""

    def setup_method(self):
        tools, _ = generate_workflow_tools()
        self.tool = next(t for t in tools if t.name == "agiloft_attach_file_to_contract")

    def test_requires_contract_id_and_file_path(self):
        """contract_id and file_path should be required."""
        required = self.tool.inputSchema["required"]
        assert "contract_id" in required
        assert "file_path" in required

    def test_has_file_path_property(self):
        """Should have file_path property."""
        props = self.tool.inputSchema["properties"]
        assert "file_path" in props

    def test_no_file_content_base64_property(self):
        """Should NOT have file_content_base64 (removed to prevent hangs)."""
        props = self.tool.inputSchema["properties"]
        assert "file_content_base64" not in props

    def test_description_warns_about_sandbox_paths(self):
        """Description should warn about sandbox paths."""
        assert "sandbox" in self.tool.description.lower()
