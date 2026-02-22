"""
Unit tests for prompt_registry.py
"""

import pytest
from mcp.types import Prompt, PromptArgument, PromptMessage, GetPromptResult, TextContent

from src.prompt_registry import (
    PROMPT_REGISTRY,
    list_prompts,
    get_prompt,
)


class TestPromptRegistry:
    """Test the prompt registry structure."""

    def test_registry_has_5_prompts(self):
        """Registry should contain exactly 5 prompts."""
        assert len(PROMPT_REGISTRY) == 5

    def test_expected_prompt_names(self):
        """All expected prompts should be registered."""
        expected = [
            "create-contract",
            "contract-review",
            "company-onboarding",
            "contract-search-and-report",
            "contract-renewal-check",
        ]
        for name in expected:
            assert name in PROMPT_REGISTRY, f"Missing prompt: {name}"

    def test_each_entry_has_prompt_and_renderer(self):
        """Each registry entry should have 'prompt' and 'renderer' keys."""
        for name, entry in PROMPT_REGISTRY.items():
            assert "prompt" in entry, f"{name} missing 'prompt'"
            assert "renderer" in entry, f"{name} missing 'renderer'"
            assert isinstance(entry["prompt"], Prompt)
            assert callable(entry["renderer"])

    def test_all_prompts_have_descriptions(self):
        """Every prompt should have a non-empty description."""
        for name, entry in PROMPT_REGISTRY.items():
            prompt = entry["prompt"]
            assert prompt.description, f"Prompt {name} has no description"
            assert len(prompt.description) > 10

    def test_prompt_names_match_registry_keys(self):
        """Prompt.name should match the registry key."""
        for key, entry in PROMPT_REGISTRY.items():
            assert entry["prompt"].name == key


class TestListPrompts:
    """Test the list_prompts function."""

    def test_returns_list_of_prompts(self):
        """list_prompts should return a list of Prompt objects."""
        prompts = list_prompts()
        assert isinstance(prompts, list)
        assert len(prompts) == 5
        for p in prompts:
            assert isinstance(p, Prompt)

    def test_prompt_names_are_unique(self):
        """All prompt names should be unique."""
        prompts = list_prompts()
        names = [p.name for p in prompts]
        assert len(names) == len(set(names))


class TestGetPrompt:
    """Test the get_prompt function."""

    def test_unknown_prompt_raises(self):
        """Unknown prompt name should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown prompt"):
            get_prompt("nonexistent-prompt")

    def test_create_contract_no_args(self):
        """create-contract with no args should mention contract types."""
        result = get_prompt("create-contract")
        assert isinstance(result, GetPromptResult)
        assert result.messages
        msg = result.messages[0]
        assert isinstance(msg, PromptMessage)
        assert msg.role == "user"
        text = msg.content.text
        assert "contract type" in text.lower()
        assert "agiloft_search_contract_types" in text

    def test_create_contract_with_type(self):
        """create-contract with contract_type should include it."""
        result = get_prompt("create-contract", {"contract_type": "NDA"})
        text = result.messages[0].content.text
        assert "NDA" in text

    def test_create_contract_with_company(self):
        """create-contract with company_name should include it."""
        result = get_prompt("create-contract", {"company_name": "Acme Corp"})
        text = result.messages[0].content.text
        assert "Acme Corp" in text
        assert "agiloft_search_companies" in text

    def test_contract_review_no_args(self):
        """contract-review with no args should ask for ID or search."""
        result = get_prompt("contract-review")
        text = result.messages[0].content.text
        assert "contract ID" in text.lower() or "search" in text.lower()

    def test_contract_review_with_id(self):
        """contract-review with contract_id should reference it."""
        result = get_prompt("contract-review", {"contract_id": "42"})
        text = result.messages[0].content.text
        assert "42" in text
        assert "agiloft_get_contract" in text

    def test_company_onboarding_no_args(self):
        """company-onboarding with no args should ask for name."""
        result = get_prompt("company-onboarding")
        text = result.messages[0].content.text
        assert "company name" in text.lower() or "company" in text.lower()

    def test_company_onboarding_with_name(self):
        """company-onboarding with company_name should check existence."""
        result = get_prompt("company-onboarding", {"company_name": "TestCo"})
        text = result.messages[0].content.text
        assert "TestCo" in text
        assert "agiloft_search_companies" in text

    def test_contract_search_report_no_args(self):
        """contract-search-and-report with no args should describe options."""
        result = get_prompt("contract-search-and-report")
        text = result.messages[0].content.text
        assert "search" in text.lower()

    def test_contract_search_report_with_criteria(self):
        """contract-search-and-report with criteria should include it."""
        result = get_prompt("contract-search-and-report", {"search_criteria": "Active NDAs"})
        text = result.messages[0].content.text
        assert "Active NDAs" in text

    def test_contract_renewal_check_default_days(self):
        """contract-renewal-check defaults to 90 days."""
        result = get_prompt("contract-renewal-check")
        text = result.messages[0].content.text
        assert "90" in text
        assert "agiloft_find_expiring_contracts" in text

    def test_contract_renewal_check_custom_days(self):
        """contract-renewal-check with custom days_ahead."""
        result = get_prompt("contract-renewal-check", {"days_ahead": "60"})
        text = result.messages[0].content.text
        assert "60" in text

    def test_all_prompts_return_valid_results(self):
        """Every prompt should return a valid GetPromptResult with empty args."""
        for name in PROMPT_REGISTRY:
            result = get_prompt(name)
            assert isinstance(result, GetPromptResult)
            assert len(result.messages) > 0
            assert result.description


class TestPromptArguments:
    """Test prompt argument definitions."""

    def test_create_contract_arguments(self):
        """create-contract should have 2 optional arguments."""
        prompt = PROMPT_REGISTRY["create-contract"]["prompt"]
        assert len(prompt.arguments) == 2
        names = {a.name for a in prompt.arguments}
        assert names == {"contract_type", "company_name"}
        for arg in prompt.arguments:
            assert arg.required is False or arg.required is None

    def test_contract_review_arguments(self):
        """contract-review should have 1 optional argument."""
        prompt = PROMPT_REGISTRY["contract-review"]["prompt"]
        assert len(prompt.arguments) == 1
        assert prompt.arguments[0].name == "contract_id"

    def test_contract_renewal_check_required_arg(self):
        """contract-renewal-check days_ahead should be required."""
        prompt = PROMPT_REGISTRY["contract-renewal-check"]["prompt"]
        days_arg = next(a for a in prompt.arguments if a.name == "days_ahead")
        assert days_arg.required is True
