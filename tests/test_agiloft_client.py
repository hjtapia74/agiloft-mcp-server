"""
Unit tests for agiloft_client.py
"""

import asyncio
import json
import os
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

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response_data)

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.post.return_value = mock_cm
        client.session = mock_session

        with patch.object(client, 'ensure_session'):
            await client._authenticate()

        assert client.access_token == 'test_token'
        assert client.refresh_token == 'test_refresh'
        assert client.token_expires_at is not None
    
    @pytest.mark.asyncio
    async def test_authentication_failure_http_error(self, client):
        """Test authentication failure with HTTP error."""
        mock_resp = AsyncMock()
        mock_resp.status = 401
        mock_resp.text = AsyncMock(return_value='Unauthorized')

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.post.return_value = mock_cm
        client.session = mock_session

        with patch.object(client, 'ensure_session'):
            with pytest.raises(AgiloftAuthError, match="Authentication failed: 401"):
                await client._authenticate()
    
    @pytest.mark.asyncio
    async def test_authentication_failure_api_error(self, client):
        """Test authentication failure with API error response."""
        mock_response_data = {
            'success': False,
            'message': 'Invalid credentials'
        }

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response_data)

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.post.return_value = mock_cm
        client.session = mock_session

        with patch.object(client, 'ensure_session'):
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

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.text = AsyncMock(return_value='{"result": "success"}')

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.request.return_value = mock_cm
        client.session = mock_session

        with patch.object(client, 'ensure_session'), \
             patch.object(client, 'ensure_authenticated'):
            result = await client._make_request('GET', '/test')

        assert result == {"result": "success"}
    
    @pytest.mark.asyncio
    async def test_make_request_401_retry(self, client):
        """Test 401 error handling with retry."""
        client.access_token = 'test_token'
        client.token_expires_at = datetime.now() + timedelta(minutes=10)

        # First response: 401
        mock_resp_401 = AsyncMock()
        mock_resp_401.status = 401
        mock_resp_401.text = AsyncMock(return_value='Unauthorized')

        mock_cm_401 = MagicMock()
        mock_cm_401.__aenter__ = AsyncMock(return_value=mock_resp_401)
        mock_cm_401.__aexit__ = AsyncMock(return_value=None)

        # Second response: 200 (after re-auth)
        mock_resp_200 = AsyncMock()
        mock_resp_200.status = 200
        mock_resp_200.text = AsyncMock(return_value='{"result": "success"}')

        mock_cm_200 = MagicMock()
        mock_cm_200.__aenter__ = AsyncMock(return_value=mock_resp_200)
        mock_cm_200.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.request.side_effect = [mock_cm_401, mock_cm_200]
        client.session = mock_session

        with patch.object(client, 'ensure_session'), \
             patch.object(client, 'ensure_authenticated'), \
             patch.object(client, '_authenticate') as mock_auth:
            result = await client._make_request('GET', '/test')

            assert result == {"result": "success"}
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
            with pytest.raises(AgiloftAPIError, match="Record 999 not found in response"):
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

        mock_session = MagicMock()
        mock_session.request.side_effect = aiohttp.ClientError("Connection failed")
        client.session = mock_session

        with patch.object(client, 'ensure_session'), \
             patch.object(client, 'ensure_authenticated'):
            with pytest.raises(AgiloftAPIError, match="HTTP client error for"):
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

    @pytest.mark.asyncio
    async def test_trigger_action_button_success(self, client):
        """Test successful action button trigger."""
        mock_response_data = {
            'success': True,
            'message': 'Action button executed successfully'
        }

        with patch.object(client, '_make_request', return_value=mock_response_data):
            result = await client.trigger_action_button('/contract', 123, 'approve')

            assert result == mock_response_data
            client._make_request.assert_called_once_with(
                'POST', '/contract/actionButton/123', params={'name': 'approve'}
            )

    @pytest.mark.asyncio
    async def test_evaluate_format_success(self, client):
        """Test successful formula evaluation."""
        mock_response_data = {
            'success': True,
            'result': 'Calculated Value: 1100'
        }

        with patch.object(client, '_make_request', return_value=mock_response_data):
            result = await client.evaluate_format('/contract', 123, '$contract_amount * 1.1')

            assert result == mock_response_data
            client._make_request.assert_called_once_with(
                'POST', '/contract/evaluateFormat/123',
                json={'formula': '$contract_amount * 1.1'}
            )


class TestGuessExtension:
    """Test MIME type to file extension mapping."""

    def test_common_types(self):
        assert AgiloftClient._guess_extension("application/pdf") == ".pdf"
        assert AgiloftClient._guess_extension(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ) == ".docx"
        assert AgiloftClient._guess_extension("text/plain") == ".txt"
        assert AgiloftClient._guess_extension("image/png") == ".png"

    def test_with_charset_parameter(self):
        assert AgiloftClient._guess_extension("text/html; charset=utf-8") == ".html"

    def test_unknown_type(self):
        assert AgiloftClient._guess_extension("application/x-custom") == ".bin"

    def test_empty_or_none(self):
        assert AgiloftClient._guess_extension("") == ".bin"
        assert AgiloftClient._guess_extension(None) == ".bin"


class TestReadBinaryResponseHeaders:
    """Test Content-Disposition and Content-Type header parsing."""

    def test_quoted_filename(self):
        resp = MagicMock()
        resp.headers = {
            "Content-Disposition": 'attachment; filename="report.docx"',
            "Content-Type": "application/octet-stream",
        }
        filename, ct = AgiloftClient._read_binary_response_headers(resp)
        assert filename == "report.docx"
        assert ct == "application/octet-stream"

    def test_unquoted_filename(self):
        resp = MagicMock()
        resp.headers = {
            "Content-Disposition": "attachment; filename=data.csv",
            "Content-Type": "text/csv",
        }
        filename, ct = AgiloftClient._read_binary_response_headers(resp)
        assert filename == "data.csv"
        assert ct == "text/csv"

    def test_no_content_disposition(self):
        resp = MagicMock()
        resp.headers = {"Content-Type": "application/pdf"}
        filename, ct = AgiloftClient._read_binary_response_headers(resp)
        assert filename is None
        assert ct == "application/pdf"

    def test_no_headers(self):
        resp = MagicMock()
        resp.headers = {}
        filename, ct = AgiloftClient._read_binary_response_headers(resp)
        assert filename is None
        assert ct == "application/octet-stream"


class TestMakeBinaryRequest:
    """Test binary request method."""

    @pytest.mark.asyncio
    async def test_success(self, client):
        """Successful binary download."""
        client.access_token = 'test_token'
        client.token_expires_at = datetime.now() + timedelta(minutes=10)

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.read = AsyncMock(return_value=b"binary file data")
        mock_resp.headers = {
            "Content-Type": "application/pdf",
            "Content-Disposition": 'attachment; filename="test.pdf"',
        }

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.request.return_value = mock_cm
        client.session = mock_session

        with patch.object(client, 'ensure_session'), \
             patch.object(client, 'ensure_authenticated'):
            data, filename, ct = await client._make_binary_request('POST', '/test')

        assert data == b"binary file data"
        assert filename == "test.pdf"
        assert ct == "application/pdf"

    @pytest.mark.asyncio
    async def test_401_retry(self, client):
        """Should re-authenticate on 401 and retry."""
        client.access_token = 'test_token'
        client.token_expires_at = datetime.now() + timedelta(minutes=10)

        # First: 401
        mock_resp_401 = AsyncMock()
        mock_resp_401.status = 401
        mock_resp_401.headers = {"Content-Type": "text/html"}
        mock_resp_401.text = AsyncMock(return_value="Unauthorized")

        mock_cm_401 = MagicMock()
        mock_cm_401.__aenter__ = AsyncMock(return_value=mock_resp_401)
        mock_cm_401.__aexit__ = AsyncMock(return_value=None)

        # Second: 200
        mock_resp_200 = AsyncMock()
        mock_resp_200.status = 200
        mock_resp_200.read = AsyncMock(return_value=b"file data")
        mock_resp_200.headers = {
            "Content-Type": "application/pdf",
            "Content-Disposition": 'attachment; filename="doc.pdf"',
        }

        mock_cm_200 = MagicMock()
        mock_cm_200.__aenter__ = AsyncMock(return_value=mock_resp_200)
        mock_cm_200.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.request.side_effect = [mock_cm_401, mock_cm_200]
        client.session = mock_session

        with patch.object(client, 'ensure_session'), \
             patch.object(client, 'ensure_authenticated'), \
             patch.object(client, '_authenticate') as mock_auth:
            data, filename, ct = await client._make_binary_request('POST', '/test')

        assert data == b"file data"
        mock_auth.assert_called_once()

    @pytest.mark.asyncio
    async def test_api_error_json(self, client):
        """Should raise AgiloftAPIError if 200 response is a JSON error."""
        client.access_token = 'test_token'
        client.token_expires_at = datetime.now() + timedelta(minutes=10)

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.text = AsyncMock(return_value='{"success": false, "message": "No file found"}')

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.request.return_value = mock_cm
        client.session = mock_session

        with patch.object(client, 'ensure_session'), \
             patch.object(client, 'ensure_authenticated'):
            with pytest.raises(AgiloftAPIError, match="No file found"):
                await client._make_binary_request('POST', '/test')

    @pytest.mark.asyncio
    async def test_timeout(self, client):
        """Should raise AgiloftAPIError on timeout."""
        client.access_token = 'test_token'
        client.token_expires_at = datetime.now() + timedelta(minutes=10)

        mock_session = MagicMock()
        mock_session.request.side_effect = asyncio.TimeoutError()
        client.session = mock_session

        with patch.object(client, 'ensure_session'), \
             patch.object(client, 'ensure_authenticated'):
            with pytest.raises(AgiloftAPIError, match="timed out"):
                await client._make_binary_request('POST', '/test')


class TestRetrieveAttachment:
    """Test retrieve_attachment save-to-disk behavior."""

    @pytest.mark.asyncio
    async def test_success_save(self, client, tmp_path):
        """Should save downloaded bytes to disk and return metadata."""
        binary_data = b"DOCX binary content"
        with patch.object(
            client, '_make_binary_request',
            return_value=(binary_data, "contract.docx", "application/octet-stream"),
        ):
            result = await client.retrieve_attachment(
                '/attachment', 612, 'attached_file', save_dir=str(tmp_path),
            )

        assert result["file_name"] == "contract.docx"
        assert result["file_size_bytes"] == len(binary_data)
        assert result["record_id"] == 612
        assert result["field"] == "attached_file"
        assert os.path.isfile(result["file_path"])
        with open(result["file_path"], "rb") as f:
            assert f.read() == binary_data

    @pytest.mark.asyncio
    async def test_filename_collision(self, client, tmp_path):
        """Should append _1 suffix when file already exists."""
        # Pre-create existing file
        existing = tmp_path / "contract.docx"
        existing.write_bytes(b"old")

        with patch.object(
            client, '_make_binary_request',
            return_value=(b"new data", "contract.docx", "application/octet-stream"),
        ):
            result = await client.retrieve_attachment(
                '/attachment', 612, 'attached_file', save_dir=str(tmp_path),
            )

        assert result["file_name"] == "contract_1.docx"
        assert os.path.isfile(result["file_path"])

    @pytest.mark.asyncio
    async def test_no_filename_fallback(self, client, tmp_path):
        """Should generate filename from field and record_id when server provides none."""
        with patch.object(
            client, '_make_binary_request',
            return_value=(b"data", None, "application/pdf"),
        ):
            result = await client.retrieve_attachment(
                '/attachment', 612, 'attached_file', save_dir=str(tmp_path),
            )

        assert result["file_name"] == "attached_file_612.pdf"

    @pytest.mark.asyncio
    async def test_empty_response_error(self, client, tmp_path):
        """Should raise error on empty binary response."""
        with patch.object(
            client, '_make_binary_request',
            return_value=(b"", "test.pdf", "application/pdf"),
        ):
            with pytest.raises(AgiloftAPIError, match="Empty response"):
                await client.retrieve_attachment(
                    '/attachment', 612, 'attached_file', save_dir=str(tmp_path),
                )

    @pytest.mark.asyncio
    async def test_default_directory(self, client):
        """Should default to ~/Downloads/agiloft/ when no save_dir given."""
        default_dir = os.path.expanduser("~/Downloads/agiloft")

        with patch.object(
            client, '_make_binary_request',
            return_value=(b"data", "test.pdf", "application/pdf"),
        ), patch('src.agiloft_client.os.makedirs') as mock_makedirs, \
           patch('builtins.open', MagicMock()), \
           patch('src.agiloft_client.os.path.exists', return_value=False):
            result = await client.retrieve_attachment('/attachment', 1, 'field')

        mock_makedirs.assert_called_once_with(default_dir, exist_ok=True)
        assert result["file_path"].startswith(default_dir)