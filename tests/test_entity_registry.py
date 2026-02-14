"""
Unit tests for entity_registry.py
"""

import pytest
from src.entity_registry import (
    ENTITY_REGISTRY,
    EntityConfig,
    get_entity,
    list_entities,
)


class TestEntityRegistry:
    """Test the entity registry configuration."""

    def test_contract_registered(self):
        """Contract entity should be in the registry."""
        assert "contract" in ENTITY_REGISTRY

    def test_contract_config_fields(self):
        """Contract config should have all required fields."""
        contract = ENTITY_REGISTRY["contract"]
        assert contract.key == "contract"
        assert contract.key_plural == "contracts"
        assert contract.api_path == "/contract"
        assert contract.display_name == "Contract"
        assert contract.display_name_plural == "Contracts"
        assert len(contract.key_fields) > 0
        assert len(contract.default_search_fields) > 0
        assert len(contract.required_fields) > 0
        assert len(contract.text_search_fields) > 0

    def test_contract_key_fields_have_type_and_description(self):
        """Each key field should have type and description."""
        contract = ENTITY_REGISTRY["contract"]
        for field_name, field_info in contract.key_fields.items():
            assert "type" in field_info, f"Missing type for {field_name}"
            assert "description" in field_info, f"Missing description for {field_name}"

    def test_contract_required_fields_in_key_fields(self):
        """Required fields should be documented in key_fields."""
        contract = ENTITY_REGISTRY["contract"]
        for required in contract.required_fields:
            assert required in contract.key_fields, \
                f"Required field '{required}' not in key_fields"

    def test_contract_default_search_fields_include_id(self):
        """Default search fields should include 'id'."""
        contract = ENTITY_REGISTRY["contract"]
        assert "id" in contract.default_search_fields

    # --- Company entity tests ---

    def test_company_registered(self):
        """Company entity should be in the registry."""
        assert "company" in ENTITY_REGISTRY

    def test_company_config_fields(self):
        """Company config should have all required fields."""
        company = ENTITY_REGISTRY["company"]
        assert company.key == "company"
        assert company.key_plural == "companies"
        assert company.api_path == "/company"
        assert company.display_name == "Company"
        assert company.display_name_plural == "Companies"
        assert len(company.key_fields) > 0
        assert len(company.default_search_fields) > 0
        assert len(company.required_fields) > 0
        assert len(company.text_search_fields) > 0

    def test_company_key_fields_have_type_and_description(self):
        """Each company key field should have type and description."""
        company = ENTITY_REGISTRY["company"]
        for field_name, field_info in company.key_fields.items():
            assert "type" in field_info, f"Missing type for {field_name}"
            assert "description" in field_info, f"Missing description for {field_name}"

    def test_company_required_fields_in_key_fields(self):
        """Company required fields should be documented in key_fields."""
        company = ENTITY_REGISTRY["company"]
        for required in company.required_fields:
            assert required in company.key_fields, \
                f"Required field '{required}' not in key_fields"

    # --- Attachment entity tests ---

    def test_attachment_registered(self):
        """Attachment entity should be in the registry."""
        assert "attachment" in ENTITY_REGISTRY

    def test_attachment_config_fields(self):
        """Attachment config should have all required fields."""
        attachment = ENTITY_REGISTRY["attachment"]
        assert attachment.key == "attachment"
        assert attachment.key_plural == "attachments"
        assert attachment.api_path == "/attachment"
        assert attachment.display_name == "Attachment"
        assert attachment.display_name_plural == "Attachments"
        assert len(attachment.key_fields) > 0
        assert len(attachment.default_search_fields) > 0
        assert len(attachment.required_fields) > 0
        assert len(attachment.text_search_fields) > 0

    def test_attachment_key_fields_have_type_and_description(self):
        """Each attachment key field should have type and description."""
        attachment = ENTITY_REGISTRY["attachment"]
        for field_name, field_info in attachment.key_fields.items():
            assert "type" in field_info, f"Missing type for {field_name}"
            assert "description" in field_info, f"Missing description for {field_name}"

    def test_attachment_required_fields_in_key_fields(self):
        """Attachment required fields should be documented in key_fields."""
        attachment = ENTITY_REGISTRY["attachment"]
        for required in attachment.required_fields:
            assert required in attachment.key_fields, \
                f"Required field '{required}' not in key_fields"

    # --- Contact entity tests ---

    def test_contact_registered(self):
        """Contact entity should be in the registry."""
        assert "contact" in ENTITY_REGISTRY

    def test_contact_config_fields(self):
        """Contact config should have all required fields."""
        contact = ENTITY_REGISTRY["contact"]
        assert contact.key == "contact"
        assert contact.key_plural == "contacts"
        assert contact.api_path == "/contacts"
        assert contact.display_name == "Contact"
        assert contact.display_name_plural == "Contacts"
        assert len(contact.key_fields) > 0
        assert len(contact.default_search_fields) > 0
        assert len(contact.required_fields) > 0
        assert len(contact.text_search_fields) > 0

    def test_contact_key_fields_have_type_and_description(self):
        """Each contact key field should have type and description."""
        contact = ENTITY_REGISTRY["contact"]
        for field_name, field_info in contact.key_fields.items():
            assert "type" in field_info, f"Missing type for {field_name}"
            assert "description" in field_info, f"Missing description for {field_name}"

    def test_contact_required_fields_in_key_fields(self):
        """Contact required fields should be documented in key_fields."""
        contact = ENTITY_REGISTRY["contact"]
        for required in contact.required_fields:
            assert required in contact.key_fields, \
                f"Required field '{required}' not in key_fields"

    # --- Employee entity tests ---

    def test_employee_registered(self):
        """Employee entity should be in the registry."""
        assert "employee" in ENTITY_REGISTRY

    def test_employee_config_fields(self):
        """Employee config should have all required fields."""
        employee = ENTITY_REGISTRY["employee"]
        assert employee.key == "employee"
        assert employee.key_plural == "employees"
        assert employee.api_path == "/contacts.employees"
        assert employee.display_name == "Employee"
        assert employee.display_name_plural == "Employees"
        assert len(employee.key_fields) > 0
        assert len(employee.default_search_fields) > 0
        assert len(employee.required_fields) > 0
        assert len(employee.text_search_fields) > 0

    def test_employee_key_fields_have_type_and_description(self):
        """Each employee key field should have type and description."""
        employee = ENTITY_REGISTRY["employee"]
        for field_name, field_info in employee.key_fields.items():
            assert "type" in field_info, f"Missing type for {field_name}"
            assert "description" in field_info, f"Missing description for {field_name}"

    def test_employee_required_fields_in_key_fields(self):
        """Employee required fields should be documented in key_fields."""
        employee = ENTITY_REGISTRY["employee"]
        for required in employee.required_fields:
            assert required in employee.key_fields, \
                f"Required field '{required}' not in key_fields"

    # --- Customer entity tests ---

    def test_customer_registered(self):
        """Customer entity should be in the registry."""
        assert "customer" in ENTITY_REGISTRY

    def test_customer_config_fields(self):
        """Customer config should have all required fields."""
        customer = ENTITY_REGISTRY["customer"]
        assert customer.key == "customer"
        assert customer.key_plural == "customers"
        assert customer.api_path == "/contacts.customer"
        assert customer.display_name == "Customer Contact"
        assert customer.display_name_plural == "Customer Contacts"
        assert len(customer.key_fields) > 0
        assert len(customer.default_search_fields) > 0
        assert len(customer.required_fields) > 0
        assert len(customer.text_search_fields) > 0

    def test_customer_key_fields_have_type_and_description(self):
        """Each customer key field should have type and description."""
        customer = ENTITY_REGISTRY["customer"]
        for field_name, field_info in customer.key_fields.items():
            assert "type" in field_info, f"Missing type for {field_name}"
            assert "description" in field_info, f"Missing description for {field_name}"

    def test_customer_required_fields_in_key_fields(self):
        """Customer required fields should be documented in key_fields."""
        customer = ENTITY_REGISTRY["customer"]
        for required in customer.required_fields:
            assert required in customer.key_fields, \
                f"Required field '{required}' not in key_fields"

    # --- Utility function tests ---

    def test_get_entity_success(self):
        """get_entity should return the correct config."""
        entity = get_entity("contract")
        assert isinstance(entity, EntityConfig)
        assert entity.key == "contract"

    def test_get_entity_unknown(self):
        """get_entity should raise ValueError for unknown entities."""
        with pytest.raises(ValueError, match="Unknown entity"):
            get_entity("nonexistent")

    def test_list_entities(self):
        """list_entities should return all registered keys."""
        entities = list_entities()
        assert "contract" in entities
        assert "company" in entities
        assert "attachment" in entities
        assert "contact" in entities
        assert "employee" in entities
        assert "customer" in entities
        assert isinstance(entities, list)
