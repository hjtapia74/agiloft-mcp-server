"""
Unit tests for server.py
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from mcp.types import TextContent
from src.server import (
    handle_search_contracts,
    handle_get_contract, 
    handle_create_contract,
    handle_update_contract,
    handle_delete_contract
)


@pytest.fixture
def mock_agiloft_client():
    """Create a mock AgiloftClient."""
    client = AsyncMock()
    return client


class TestServerHandlers:
    """Test cases for MCP server handlers."""
    
    @pytest.mark.asyncio
    async def test_handle_search_contracts_natural_language(self, mock_agiloft_client):
        """Test search contracts with natural language query."""
        mock_contracts = [
            {'id': 1, 'contract_title1': 'Test Contract', 'company_name': 'Test Co'}
        ]
        mock_agiloft_client.search_contracts.return_value = mock_contracts
        
        arguments = {
            'query': 'test contracts',
            'fields': ['id', 'contract_title1', 'company_name'],
            'limit': 10
        }
        
        with patch('src.server.agiloft_client', mock_agiloft_client):
            result = await handle_search_contracts(arguments)
        
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert 'Found 1 contracts' in result[0].text
        assert 'Test Contract' in result[0].text
        
        # Verify natural language was converted to structured query
        mock_agiloft_client.search_contracts.assert_called_once()
        call_args = mock_agiloft_client.search_contracts.call_args
        assert "LIKE '%test contracts%'" in call_args.kwargs['query']
    
    @pytest.mark.asyncio
    async def test_handle_search_contracts_structured_query(self, mock_agiloft_client):
        """Test search contracts with structured query."""
        mock_contracts = [
            {'id': 1, 'contract_title1': 'Active Contract', 'status': 'Active'}
        ]
        mock_agiloft_client.search_contracts.return_value = mock_contracts
        
        arguments = {
            'query': 'status=Active AND amount>1000',
            'limit': 50
        }
        
        with patch('src.server.agiloft_client', mock_agiloft_client):
            result = await handle_search_contracts(arguments)
        
        assert len(result) == 1
        
        # Verify structured query was used as-is
        mock_agiloft_client.search_contracts.assert_called_once()
        call_args = mock_agiloft_client.search_contracts.call_args
        assert call_args.kwargs['query'] == 'status=Active AND amount>1000'
    
    @pytest.mark.asyncio
    async def test_handle_search_contracts_limit(self, mock_agiloft_client):
        """Test search contracts with result limiting."""
        mock_contracts = [{'id': i, 'title': f'Contract {i}'} for i in range(100)]
        mock_agiloft_client.search_contracts.return_value = mock_contracts
        
        arguments = {
            'query': 'test',
            'limit': 5
        }
        
        with patch('src.server.agiloft_client', mock_agiloft_client):
            result = await handle_search_contracts(arguments)
        
        assert 'Found 5 contracts' in result[0].text
        # Verify only 5 contracts in JSON output
        json_start = result[0].text.find('[')
        contracts_json = result[0].text[json_start:]
        contracts = json.loads(contracts_json)
        assert len(contracts) == 5
    
    @pytest.mark.asyncio
    async def test_handle_search_contracts_error(self, mock_agiloft_client):
        """Test search contracts error handling."""
        mock_agiloft_client.search_contracts.side_effect = Exception('Search failed')
        
        arguments = {'query': 'test'}
        
        with patch('src.server.agiloft_client', mock_agiloft_client):
            result = await handle_search_contracts(arguments)
        
        assert len(result) == 1
        assert 'Search failed: Search failed' in result[0].text
    
    @pytest.mark.asyncio
    async def test_handle_get_contract_success(self, mock_agiloft_client):
        """Test successful get contract."""
        mock_contract = {
            'id': 123,
            'contract_title1': 'Test Contract',
            'company_name': 'Test Company'
        }
        mock_agiloft_client.get_contract.return_value = mock_contract
        
        arguments = {
            'contract_id': 123,
            'fields': ['id', 'contract_title1', 'company_name']
        }
        
        with patch('src.server.agiloft_client', mock_agiloft_client):
            result = await handle_get_contract(arguments)
        
        assert len(result) == 1
        assert 'Contract 123:' in result[0].text
        assert 'Test Contract' in result[0].text
        
        mock_agiloft_client.get_contract.assert_called_once_with(
            123, ['id', 'contract_title1', 'company_name']
        )
    
    @pytest.mark.asyncio
    async def test_handle_get_contract_error(self, mock_agiloft_client):
        """Test get contract error handling."""
        mock_agiloft_client.get_contract.side_effect = Exception('Contract not found')
        
        arguments = {'contract_id': 999}
        
        with patch('src.server.agiloft_client', mock_agiloft_client):
            result = await handle_get_contract(arguments)
        
        assert len(result) == 1
        assert 'Failed to get contract 999: Contract not found' in result[0].text
    
    @pytest.mark.asyncio
    async def test_handle_create_contract_success(self, mock_agiloft_client):
        """Test successful contract creation."""
        mock_result = {
            'success': True,
            'contract': {'id': 456, 'contract_title1': 'New Contract'}
        }
        mock_agiloft_client.create_contract.return_value = mock_result
        
        arguments = {
            'contract_data': {
                'contract_title1': 'New Contract',
                'company_name': 'New Company'
            }
        }
        
        with patch('src.server.agiloft_client', mock_agiloft_client):
            result = await handle_create_contract(arguments)
        
        assert len(result) == 1
        assert 'Contract created successfully:' in result[0].text
        assert 'New Contract' in result[0].text
        
        mock_agiloft_client.create_contract.assert_called_once_with({
            'contract_title1': 'New Contract',
            'company_name': 'New Company'
        })
    
    @pytest.mark.asyncio
    async def test_handle_create_contract_error(self, mock_agiloft_client):
        """Test create contract error handling."""
        mock_agiloft_client.create_contract.side_effect = Exception('Validation failed')
        
        arguments = {
            'contract_data': {'contract_title1': 'Invalid Contract'}
        }
        
        with patch('src.server.agiloft_client', mock_agiloft_client):
            result = await handle_create_contract(arguments)
        
        assert len(result) == 1
        assert 'Failed to create contract: Validation failed' in result[0].text
    
    @pytest.mark.asyncio
    async def test_handle_update_contract_success(self, mock_agiloft_client):
        """Test successful contract update."""
        mock_result = {
            'success': True,
            'contract': {'id': 123, 'contract_title1': 'Updated Contract'}
        }
        mock_agiloft_client.update_contract.return_value = mock_result
        
        arguments = {
            'contract_id': 123,
            'contract_data': {'contract_title1': 'Updated Contract'}
        }
        
        with patch('src.server.agiloft_client', mock_agiloft_client):
            result = await handle_update_contract(arguments)
        
        assert len(result) == 1
        assert 'Contract 123 updated successfully:' in result[0].text
        assert 'Updated Contract' in result[0].text
        
        mock_agiloft_client.update_contract.assert_called_once_with(
            123, {'contract_title1': 'Updated Contract'}
        )
    
    @pytest.mark.asyncio
    async def test_handle_update_contract_error(self, mock_agiloft_client):
        """Test update contract error handling."""
        mock_agiloft_client.update_contract.side_effect = Exception('Update failed')
        
        arguments = {
            'contract_id': 123,
            'contract_data': {'contract_title1': 'Updated Contract'}
        }
        
        with patch('src.server.agiloft_client', mock_agiloft_client):
            result = await handle_update_contract(arguments)
        
        assert len(result) == 1
        assert 'Failed to update contract 123: Update failed' in result[0].text
    
    @pytest.mark.asyncio
    async def test_handle_delete_contract_success(self, mock_agiloft_client):
        """Test successful contract deletion."""
        mock_result = {
            'success': True,
            'message': 'Contract deleted successfully'
        }
        mock_agiloft_client.delete_contract.return_value = mock_result
        
        arguments = {
            'contract_id': 123,
            'delete_rule': 'DELETE_WHERE_POSSIBLE_OTHERWISE_UNLINK'
        }
        
        with patch('src.server.agiloft_client', mock_agiloft_client):
            result = await handle_delete_contract(arguments)
        
        assert len(result) == 1
        assert 'Contract 123 deletion result:' in result[0].text
        assert 'Contract deleted successfully' in result[0].text
        
        mock_agiloft_client.delete_contract.assert_called_once_with(
            123, 'DELETE_WHERE_POSSIBLE_OTHERWISE_UNLINK'
        )
    
    @pytest.mark.asyncio
    async def test_handle_delete_contract_default_rule(self, mock_agiloft_client):
        """Test delete contract with default delete rule."""
        mock_result = {'success': True}
        mock_agiloft_client.delete_contract.return_value = mock_result
        
        arguments = {'contract_id': 123}
        
        with patch('src.server.agiloft_client', mock_agiloft_client):
            await handle_delete_contract(arguments)
        
        mock_agiloft_client.delete_contract.assert_called_once_with(
            123, 'ERROR_IF_DEPENDANTS'
        )
    
    @pytest.mark.asyncio
    async def test_handle_delete_contract_error(self, mock_agiloft_client):
        """Test delete contract error handling."""
        mock_agiloft_client.delete_contract.side_effect = Exception('Cannot delete - has dependencies')
        
        arguments = {'contract_id': 123}
        
        with patch('src.server.agiloft_client', mock_agiloft_client):
            result = await handle_delete_contract(arguments)
        
        assert len(result) == 1
        assert 'Failed to delete contract 123: Cannot delete - has dependencies' in result[0].text