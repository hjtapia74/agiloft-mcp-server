"""
Unit tests for agiloft_client.py
"""

import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import aiohttp
from src.agiloft_client import AgiloftClient
from src.config import Config
from src.exceptions import AgiloftAuthError, AgiloftAPIError


@pytest.fixture
def mock_config():
    """Create a mock configuration."""
    config = MagicMock(spec=Config)
    config.get.side_effect = lambda key, default=None: {
        'agiloft.base_url': 'https://test.agiloft.com/api',
        'agiloft.username': 'testuser',
        'agiloft.password': 'testpass',
        'agiloft.kb': 'TestKB',
        'agiloft.language': 'en'
    }.get(key, default)
    return config


@pytest.fixture
def client(mock_config):
    """Create an AgiloftClient instance."""
    return AgiloftClient(mock_config)


class TestAgiloftClient:
    """Test cases for AgiloftClient class."""
    
    @pytest.mark.asyncio
    async def test_init(self, mock_config):
        """Test client initialization."""
        client = AgiloftClient(mock_config)
        
        assert client.base_url == 'https://test.agiloft.com/api'
        assert client.username == 'testuser'
        assert client.password == 'testpass'
        assert client.kb == 'TestKB'
        assert client.language == 'en'
        assert client.session is None
        assert client.access_token is None
    
    @pytest.mark.asyncio
    async def test_ensure_session(self, client):
        """Test session creation."""
        await client.ensure_session()
        
        assert client.session is not None
        assert isinstance(client.session, aiohttp.ClientSession)
        
        await client.close()
    
    @pytest.mark.asyncio 
    async def test_context_manager(self, mock_config):
        """Test async context manager."""
        async with AgiloftClient(mock_config) as client:
            assert client.session is not None
    
    @pytest.mark.asyncio
    async def test_authentication_success(self, client):
        """Test successful authentication."""
        mock_response_data = {
            'success': True,
            'result': {
                'access_token': 'test_token',
                'refresh_token': 'test_refresh',
                'expires_in': 15
            }
        }
        
        with patch.object(client, 'ensure_session'), \
             patch.object(client.session, 'post') as mock_post:
            
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.json = AsyncMock(return_value=mock_response_data)
            mock_post.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_post.return_value.__aexit__ = AsyncMock(return_value=None)
            
            await client._authenticate()
            
            assert client.access_token == 'test_token'
            assert client.refresh_token == 'test_refresh'
            assert client.token_expires_at is not None
    
    @pytest.mark.asyncio
    async def test_authentication_failure_http_error(self, client):
        """Test authentication failure with HTTP error."""
        with patch.object(client, 'ensure_session'), \
             patch.object(client.session, 'post') as mock_post:
            
            mock_resp = AsyncMock()
            mock_resp.status = 401
            mock_resp.text = AsyncMock(return_value='Unauthorized')
            mock_post.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_post.return_value.__aexit__ = AsyncMock(return_value=None)
            
            with pytest.raises(AgiloftAuthError, match="Authentication failed: 401"):
                await client._authenticate()
    
    @pytest.mark.asyncio
    async def test_authentication_failure_api_error(self, client):
        """Test authentication failure with API error response."""
        mock_response_data = {
            'success': False,
            'message': 'Invalid credentials'
        }
        
        with patch.object(client, 'ensure_session'), \
             patch.object(client.session, 'post') as mock_post:
            
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.json = AsyncMock(return_value=mock_response_data)
            mock_post.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_post.return_value.__aexit__ = AsyncMock(return_value=None)
            
            with pytest.raises(AgiloftAuthError, match="Authentication failed: Invalid credentials"):
                await client._authenticate()
    
    @pytest.mark.asyncio
    async def test_get_auth_headers_no_token(self, client):
        """Test auth headers when no token is available."""
        with pytest.raises(AgiloftAuthError, match="No access token available"):
            client._get_auth_headers()
    
    @pytest.mark.asyncio
    async def test_get_auth_headers_with_token(self, client):
        """Test auth headers with valid token."""
        client.access_token = 'test_token'
        
        headers = client._get_auth_headers()
        
        assert headers['Authorization'] == 'Bearer test_token'
        assert headers['Content-Type'] == 'application/json'
        assert headers['Accept'] == 'application/json'
    
    @pytest.mark.asyncio
    async def test_make_request_success(self, client):
        """Test successful API request."""
        client.access_token = 'test_token'
        client.token_expires_at = datetime.now() + timedelta(minutes=10)
        
        mock_response_data = {'result': 'success'}
        
        with patch.object(client, 'ensure_session'), \
             patch.object(client.session, 'request') as mock_request:
            
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.text = AsyncMock(return_value='{"result": "success"}')
            mock_resp.json = AsyncMock(return_value=mock_response_data)
            mock_request.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_request.return_value.__aexit__ = AsyncMock(return_value=None)
            
            result = await client._make_request('GET', '/test')
            
            assert result == mock_response_data
    
    @pytest.mark.asyncio
    async def test_make_request_401_retry(self, client):
        """Test 401 error handling with retry."""
        client.access_token = 'test_token'
        client.token_expires_at = datetime.now() + timedelta(minutes=10)
        
        mock_response_data = {'result': 'success'}
        
        with patch.object(client, 'ensure_session'), \
             patch.object(client, '_authenticate') as mock_auth, \
             patch.object(client.session, 'request') as mock_request:
            
            # First response: 401
            mock_resp_401 = AsyncMock()
            mock_resp_401.status = 401
            mock_resp_401.text = AsyncMock(return_value='Unauthorized')
            
            # Second response: 200
            mock_resp_200 = AsyncMock()
            mock_resp_200.status = 200
            mock_resp_200.json = AsyncMock(return_value=mock_response_data)
            
            mock_request.return_value.__aenter__ = AsyncMock(
                side_effect=[mock_resp_401, mock_resp_200]
            )
            mock_request.return_value.__aexit__ = AsyncMock(return_value=None)
            
            result = await client._make_request('GET', '/test')
            
            assert result == mock_response_data
            mock_auth.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_search_contracts_success(self, client):
        """Test successful contract search."""
        mock_response_data = {
            'success': True,
            'result': [
                {'id': 1, 'contract_title1': 'Test Contract 1'},
                {'id': 2, 'contract_title1': 'Test Contract 2'}
            ]
        }
        
        with patch.object(client, '_make_request', return_value=mock_response_data):
            results = await client.search_contracts('test query')
            
            assert len(results) == 2
            assert results[0]['contract_title1'] == 'Test Contract 1'
    
    @pytest.mark.asyncio
    async def test_search_contracts_failure(self, client):
        """Test failed contract search."""
        mock_response_data = {
            'success': False,
            'message': 'Search failed'
        }
        
        with patch.object(client, '_make_request', return_value=mock_response_data):
            with pytest.raises(AgiloftAPIError, match="Search failed: Search failed"):
                await client.search_contracts('test query')
    
    @pytest.mark.asyncio
    async def test_get_contract_success(self, client):
        """Test successful get contract."""
        mock_response_data = {
            'contract': {
                'id': 1,
                'contract_title1': 'Test Contract',
                'company_name': 'Test Company'
            }
        }
        
        with patch.object(client, '_make_request', return_value=mock_response_data):
            result = await client.get_contract(1)
            
            assert result['id'] == 1
            assert result['contract_title1'] == 'Test Contract'
    
    @pytest.mark.asyncio
    async def test_get_contract_with_fields(self, client):
        """Test get contract with field filtering."""
        mock_response_data = {
            'contract': {
                'id': 1,
                'contract_title1': 'Test Contract',
                'company_name': 'Test Company',
                'extra_field': 'extra_value'
            }
        }
        
        with patch.object(client, '_make_request', return_value=mock_response_data):
            result = await client.get_contract(1, fields=['id', 'contract_title1'])
            
            assert result['id'] == 1
            assert result['contract_title1'] == 'Test Contract'
            assert 'extra_field' not in result
    
    @pytest.mark.asyncio
    async def test_get_contract_not_found(self, client):
        """Test get contract when not found."""
        mock_response_data = {}
        
        with patch.object(client, '_make_request', return_value=mock_response_data):
            with pytest.raises(AgiloftAPIError, match="Contract not found in response"):
                await client.get_contract(999)
    
    @pytest.mark.asyncio
    async def test_create_contract_success(self, client):
        """Test successful contract creation."""
        mock_response_data = {
            'success': True,
            'contract': {'id': 123, 'contract_title1': 'New Contract'}
        }
        
        contract_data = {'contract_title1': 'New Contract'}
        
        with patch.object(client, '_make_request', return_value=mock_response_data):
            result = await client.create_contract(contract_data)
            
            assert result == mock_response_data
    
    @pytest.mark.asyncio
    async def test_create_contract_failure(self, client):
        """Test failed contract creation."""
        mock_response_data = {
            'success': False,
            'message': 'Validation failed',
            'errors': [{'message': 'Title is required'}]
        }
        
        contract_data = {}
        
        with patch.object(client, '_make_request', return_value=mock_response_data):
            with pytest.raises(AgiloftAPIError, match="Create failed: Validation failed - Title is required"):
                await client.create_contract(contract_data)
    
    @pytest.mark.asyncio
    async def test_update_contract_success(self, client):
        """Test successful contract update."""
        mock_response_data = {
            'success': True,
            'contract': {'id': 123, 'contract_title1': 'Updated Contract'}
        }
        
        update_data = {'contract_title1': 'Updated Contract'}
        
        with patch.object(client, '_make_request', return_value=mock_response_data):
            result = await client.update_contract(123, update_data)
            
            assert result == mock_response_data
    
    @pytest.mark.asyncio
    async def test_delete_contract_success(self, client):
        """Test successful contract deletion."""
        mock_response_data = {
            'success': True,
            'message': 'Contract deleted'
        }
        
        with patch.object(client, '_make_request', return_value=mock_response_data):
            result = await client.delete_contract(123)
            
            assert result == mock_response_data
    
    @pytest.mark.asyncio
    async def test_delete_contract_failure(self, client):
        """Test failed contract deletion."""
        mock_response_data = {
            'success': False,
            'message': 'Cannot delete - has dependencies'
        }
        
        with patch.object(client, '_make_request', return_value=mock_response_data):
            with pytest.raises(AgiloftAPIError, match="Delete failed: Cannot delete - has dependencies"):
                await client.delete_contract(123)
    
    @pytest.mark.asyncio
    async def test_http_client_error(self, client):
        """Test handling of HTTP client errors."""
        client.access_token = 'test_token'
        client.token_expires_at = datetime.now() + timedelta(minutes=10)
        
        with patch.object(client, 'ensure_session'), \
             patch.object(client.session, 'request', side_effect=aiohttp.ClientError("Connection failed")):
            
            with pytest.raises(AgiloftAPIError, match="HTTP error: Connection failed"):
                await client._make_request('GET', '/test')
    
    @pytest.mark.asyncio
    async def test_logout(self, client):
        """Test logout functionality."""
        client.access_token = 'test_token'
        
        with patch.object(client, '_make_request') as mock_request:
            await client.logout()
            
            mock_request.assert_called_once_with('POST', '/logout')
            assert client.access_token is None
            assert client.refresh_token is None
            assert client.token_expires_at is None