#!/usr/bin/env python3
"""
Test script for Agiloft MCP Server

This script helps test the Agiloft client functionality independently
before integrating with the MCP server.
"""

import asyncio
import json
import logging
from src.config import Config
from src.agiloft_client import AgiloftClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_authentication():
    """Test basic authentication."""
    print("\n=== Testing Authentication ===")
    
    config = Config()
    
    # Validate configuration
    if not config.validate():
        print("❌ Configuration validation failed. Please check your config.json or environment variables.")
        return False
        
    client = AgiloftClient(config)
    
    try:
        await client.ensure_authenticated()
        print("✅ Authentication successful")
        print(f"Token expires at: {client.token_expires_at}")
        return True
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        return False
    finally:
        await client.close()

async def test_search():
    """Test contract search functionality."""
    print("\n=== Testing Contract Search ===")
    
    config = Config()
    client = AgiloftClient(config)
    
    try:
        # Test basic search
        results = await client.search_contracts()
        print(f"✅ Found {len(results)} contracts")
        
        # Show first few results
        for i, contract in enumerate(results[:3]):
            print(f"Contract {i+1}: {contract.get('contract_title1', 'No title')} (ID: {contract.get('id')})")
            
        # Test filtered search
        print("\n--- Testing Filtered Search ---")
        filtered_results = await client.search_contracts(
            query="record_type='Contract'",
            fields=["id", "contract_title1", "company_name"]
        )
        print(f"✅ Filtered search found {len(filtered_results)} contracts")
        
        return True
    except Exception as e:
        print(f"❌ Search failed: {e}")
        return False
    finally:
        await client.close()

async def test_get_contract():
    """Test getting a specific contract."""
    print("\n=== Testing Get Contract ===")
    
    config = Config()
    client = AgiloftClient(config)
    
    try:
        # First, get a contract ID from search
        results = await client.search_contracts(fields=["id"], query="record_type='Contract'")
        if not results:
            print("❌ No contracts found to test with")
            return False
            
        contract_id = results[0]['id']
        print(f"Testing with contract ID: {contract_id}")
        
        # Get the full contract
        contract = await client.get_contract(contract_id)
        print(f"✅ Retrieved contract: {contract.get('contract_title1', 'No title')}")
        
        # Test with field filtering
        filtered_contract = await client.get_contract(
            contract_id, 
            fields=["id", "contract_title1", "company_name", "contract_amount"]
        )
        print(f"✅ Filtered contract data: {json.dumps(filtered_contract, indent=2, default=str)}")
        
        return True
    except Exception as e:
        print(f"❌ Get contract failed: {e}")
        return False
    finally:
        await client.close()

async def test_create_update_delete():
    """Test contract creation, update, and deletion."""
    print("\n=== Testing Create/Update/Delete ===")
    print("⚠️  This test will create and delete a test contract")
    
    response = input("Continue? (y/N): ")
    if response.lower() != 'y':
        print("Skipping create/update/delete test")
        return True
        
    config = Config()
    client = AgiloftClient(config)
    
    try:
        # First, get some real data from existing contracts to use in our test
        print("Fetching existing contract data for realistic test values...")
        existing_contracts = await client.search_contracts(
            query="record_type='Contract'",
            fields=["company_name", "internal_contract_owner", "contract_amount", "contract_term_in_months"]
        )
        
        # Use data from first existing contract, with fallbacks
        sample_company = ": Test Company Ltd."
        sample_owner = ": Test User"
        sample_amount = 1000.00
        sample_term = 12
        
        if existing_contracts and len(existing_contracts) > 0:
            first_contract = existing_contracts[0]
            # Add colon prefix to company name and owner
            raw_company = first_contract.get("company_name", sample_company.replace(": ", ""))
            raw_owner = first_contract.get("internal_contract_owner", sample_owner.replace(": ", ""))
            sample_company = f": {raw_company}" if not raw_company.startswith(":") else raw_company
            sample_owner = f": {raw_owner}" if not raw_owner.startswith(":") else raw_owner
            # Use a smaller amount for testing
            if first_contract.get("contract_amount"):
                try:
                    # Handle both string "$1000.00" and numeric 1000.00 formats
                    amount_str = str(first_contract["contract_amount"]).replace("$", "").replace(",", "")
                    original_amount = float(amount_str)
                    sample_amount = min(1000.00, original_amount * 0.1)  # Use 10% of original or $1000 max
                except (ValueError, TypeError):
                    pass  # Keep default
            if first_contract.get("contract_term_in_months"):
                try:
                    sample_term = int(first_contract["contract_term_in_months"])
                except (ValueError, TypeError):
                    pass  # Keep default
        
        # Create a test contract using real data
        test_contract = {
            "contract_title1": "MCP Test Contract (Automated Test)",
            "company_name": sample_company,
            "contract_amount": sample_amount,
            "contract_term_in_months": sample_term,
            "internal_contract_owner": sample_owner,
            "contract_description": "Test contract created by MCP automated test script"
        }
        
        print(f"Using sample data from existing contracts:")
        print(f"  Company: {sample_company}")
        print(f"  Owner: {sample_owner}")
        print(f"  Amount: ${sample_amount:,.2f}")
        print(f"  Term: {sample_term} months")
        print(f"  Note: Adding ':' prefix to company_name and internal_contract_owner per requirements")
        print(f"  Note: Based on example_create_contract.json, no fields are mandatory")
        print("\nPOST Request Body:")
        print(json.dumps(test_contract, indent=2))
        
        print("\nCreating test contract...")
        create_result = await client.create_contract(test_contract)
        print(f"✅ Contract created: {json.dumps(create_result, indent=2, default=str)}")
        
        # Extract contract ID from response
        contract_id = None
        if 'result' in create_result:
            # Handle both cases: result as direct ID number or result as object with id
            if isinstance(create_result['result'], (int, str)):
                # Direct ID in result (e.g., "result": 629)
                contract_id = int(create_result['result'])
            elif isinstance(create_result['result'], dict):
                # Object with id property (e.g., "result": {"id": 629, ...})
                contract_id = create_result['result'].get('id')
        elif 'contract' in create_result:
            contract_id = create_result['contract'].get('id')
        elif 'id' in create_result:
            contract_id = create_result['id']
            
        if not contract_id:
            print("❌ Could not determine created contract ID")
            return False
            
        print(f"Created contract ID: {contract_id}")
        
        # Update the contract
        print("Updating contract...")
        update_data = {
            "contract_title1": "MCP Test Contract (Updated)",
            "contract_amount": 1500.00
        }
        
        update_result = await client.update_contract(contract_id, update_data)
        print(f"✅ Contract updated: {json.dumps(update_result, indent=2, default=str)}")
        
        # Delete the contract
        print("Deleting test contract...")
        delete_rule = "UNLINK_WHERE_POSSIBLE_OTHERWISE_DELETE"
        print(f"Using delete rule: {delete_rule}")
        delete_result = await client.delete_contract(contract_id, delete_rule)
        print(f"✅ Contract deleted: {json.dumps(delete_result, indent=2, default=str)}")
        
        return True
    except Exception as e:
        print(f"❌ Create/Update/Delete failed: {e}")
        return False
    finally:
        await client.close()

async def main():
    """Run all tests."""
    print("Agiloft MCP Server Test Suite")
    print("=" * 40)
    
    tests = [
        ("Authentication", test_authentication),
        ("Search", test_search),
        ("Get Contract", test_get_contract),
        ("Create/Update/Delete", test_create_update_delete)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 40)
    print("Test Results Summary:")
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
            
    print(f"\nPassed: {passed}/{len(results)} tests")
    
    if passed == len(results):
        print("🎉 All tests passed! Your Agiloft MCP server should work correctly.")
    else:
        print("⚠️  Some tests failed. Check configuration and connectivity.")

if __name__ == "__main__":
    asyncio.run(main())