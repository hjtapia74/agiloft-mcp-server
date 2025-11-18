#!/usr/bin/env python3
"""
Example script showing different contract creation payloads
"""

import asyncio
import json
import logging
from src.config import Config
from src.agiloft_client import AgiloftClient

logging.basicConfig(level=logging.INFO)

# Simple contract (as used in test_script.py)
simple_contract = {
    "contract_title1": "MCP Test Contract",
    "company_name": "Test Company Ltd.", 
    "contract_amount": 1000.00,
    "contract_term_in_months": 12,
    "internal_contract_owner": "Test User"
}

# More comprehensive contract with additional fields
comprehensive_contract = {
    "contract_title1": "Professional Services Agreement with ABC Corp",
    "company_name": "ABC Corporation",
    "contract_amount": "$50000.00",
    "contract_term_in_months": 24,
    "internal_contract_owner": "Robert Barash",
    "contract_start_date": "2025-01-01",
    "contract_end_date": "2026-12-31",
    "contract_description": "Professional services for software development",
    "contract_type": "Professional Services Agreement",
    "for_department": "IT Department",
    "requester_name": "John Doe",
    "requester_email": "john.doe@example.com",
    "cost_type": "Payable",
    "wfstate": "Draft"
}

# Minimal required fields (you'll need to check what's actually required)
minimal_contract = {
    "contract_title1": "Minimal Test Contract",
    "company_name": "Minimal Corp"
}

async def test_contract_creation(contract_data, description):
    """Test creating a contract with specific data."""
    print(f"\n=== {description} ===")
    print("POST Request Body:")
    print(json.dumps(contract_data, indent=2))
    
    config = Config()
    async with AgiloftClient(config) as client:
        try:
            result = await client.create_contract(contract_data)
            print("✅ Contract created successfully!")
            print("Response:")
            print(json.dumps(result, indent=2, default=str))
            return result
        except Exception as e:
            print(f"❌ Failed to create contract: {e}")
            return None

async def main():
    """Test different contract creation scenarios."""
    print("Contract Creation Examples")
    print("=" * 50)
    
    # Test simple contract (same as test_script.py)
    await test_contract_creation(simple_contract, "Simple Contract (from test_script.py)")
    
    # Test comprehensive contract
    await test_contract_creation(comprehensive_contract, "Comprehensive Contract")
    
    # Test minimal contract
    await test_contract_creation(minimal_contract, "Minimal Contract")

if __name__ == "__main__":
    asyncio.run(main())