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
    """Create a mock configuration for legacy auth."""
    config = MagicMock(spec=Config)
    config.get.side_effect = lambda key, default=None: {
        'agiloft.base_url': 'https://test.agiloft.com/api',
        'agiloft.username': 'testuser',
        'agiloft.password': 'testpass',
        'agiloft.kb': 'TestKB',
        'agiloft.language': 'en',
        'agiloft.auth_method': 'legacy',
        'agiloft.oauth2.client_id': '',
        'agiloft.oauth2.client_secret': '',
        'agiloft.oauth2.token_endpoint': '',
        'agiloft.oauth2.authorization_endpoint': '',
        'agiloft.oauth2.redirect_uri': 'http://localhost:8080/callback',
        'agiloft.oauth2.scope': '',
    }.get(key, default)
    return config


@pytest.fixture
def mock_oauth2_config():
    """Create a mock configuration for OAuth2 client credentials."""
    config = MagicMock(spec=Config)
    config.get.side_effect = lambda key, default=None: {
        'agiloft.base_url': 'https://test.agiloft.com/api',
        'agiloft.username': '',
        'agiloft.password': '',
        'agiloft.kb': 'TestKB',
        'agiloft.language': 'en',
        'agiloft.auth_method': 'oauth2_client_credentials',
        'agiloft.oauth2.client_id': 'test-client-id',
        'agiloft.oauth2.client_secret': 'test-client-secret',
        'agiloft.oauth2.token_endpoint': 'https://test.agiloft.com/oauth/token',
        'agiloft.oauth2.authorization_endpoint': '',
        'agiloft.oauth2.redirect_uri': 'http://localhost:8080/callback',
        'agiloft.oauth2.scope': '',
    }.get(key, default)
    return config


@pytest.fixture
def client(mock_config):
    """Create an AgiloftClient instance with legacy auth."""
    return AgiloftClient(mock_config)


@pytest.fixture
def oauth2_client(mock_oauth2_config):
    """Create an AgiloftClient instance with OAuth2 auth."""
    return AgiloftClient(mock_oauth2_config)


class TestAgiloftClient:
    """Test cases for AgiloftClient class."""

    @pytest.mark.asyncio
    async def test_init_legacy(self, mock_config):
        """Test client initialization with legacy auth."""
        client = AgiloftClient(mock_config)

        assert client.base_url == 'https://test.agiloft.com/api'
        assert client.username == 'testuser'
        assert client._password == 'testpass'
        assert client.kb == 'TestKB'
        assert client.language == 'en'
        assert client.auth_method == 'legacy'
        assert client.session is None
        assert client.access_token is None

    @pytest.mark.asyncio
    async def test_init_oauth2(self, mock_oauth2_config):
        """Test client initialization with OAuth2 auth."""
        client = AgiloftClient(mock_oauth2_config)

        assert client.auth_method == 'oauth2_client_credentials'
        assert client.oauth2_client_id == 'test-client-id'
        assert client._oauth2_client_secret == 'test-client-secret'
        assert client.oauth2_token_endpoint == 'https://test.agiloft.com/oauth/token'

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
    async def test_legacy_authentication_success(self, client):
        """Test successful legacy authentication."""
        mock_response_data = {
            'success': True,
            'result': {
                'access_token': 'test_token',
                'refresh_token': 'test_refresh',
                'expires_in': 900
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
            await client._authenticate_legacy()

        assert client.access_token == 'test_token'
        assert client.refresh_token == 'test_refresh'
        assert client.token_expires_at is not None
        # Password should be cleared after successful auth
        assert client._password is None

    @pytest.mark.asyncio
    async def test_legacy_authentication_failure_http_error(self, client):
        """Test legacy authentication failure with HTTP error."""
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
                await client._authenticate_legacy()

    @pytest.mark.asyncio
    async def test_legacy_authentication_failure_api_error(self, client):
        """Test legacy authentication failure with API error response."""
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
                await client._authenticate_legacy()

    @pytest.mark.asyncio
    async def test_authenticate_routes_to_legacy(self, client):
        """Test _authenticate routes to legacy when auth_method is legacy."""
        with patch.object(client, '_authenticate_legacy') as mock_legacy:
            await client._authenticate()
            mock_legacy.assert_called_once()

    @pytest.mark.asyncio
    async def test_authenticate_routes_to_oauth2(self, oauth2_client):
        """Test _authenticate routes to OAuth2 client credentials."""
        with patch.object(oauth2_client, '_authenticate_oauth2_client_credentials') as mock_oauth:
            await oauth2_client._authenticate()
            mock_oauth.assert_called_once()

    @pytest.mark.asyncio
    async def test_authenticate_oauth2_auth_code_requires_browser(self):
        """Test that OAuth2 auth code flow raises error without browser auth."""
        config = MagicMock(spec=Config)
        config.get.side_effect = lambda key, default=None: {
            'agiloft.base_url': 'https://test.agiloft.com/api',
            'agiloft.kb': 'TestKB',
            'agiloft.language': 'en',
            'agiloft.auth_method': 'oauth2_authorization_code',
            'agiloft.username': '',
            'agiloft.password': '',
            'agiloft.oauth2.client_id': 'id',
            'agiloft.oauth2.client_secret': 'secret',
            'agiloft.oauth2.token_endpoint': 'https://test.com/token',
            'agiloft.oauth2.authorization_endpoint': 'https://test.com/auth',
            'agiloft.oauth2.redirect_uri': 'http://localhost:8080/callback',
            'agiloft.oauth2.scope': '',
        }.get(key, default)
        client = AgiloftClient(config)

        with pytest.raises(AgiloftAuthError, match="browser-based authentication"):
            await client._authenticate()


class TestOAuth2ClientCredentials:
    """Test OAuth2 Client Credentials authentication."""

    @pytest.mark.asyncio
    async def test_oauth2_success(self, oauth2_client):
        """Test successful OAuth2 client credentials authentication."""
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.headers = {'Content-Type': 'application/json'}
        mock_resp.json = AsyncMock(return_value={
            'access_token': 'oauth2_token',
            'expires_in': 900,
            'refresh_token': 'oauth2_refresh'
        })

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.post.return_value = mock_cm
        oauth2_client.session = mock_session

        with patch.object(oauth2_client, 'ensure_session'):
            await oauth2_client._authenticate_oauth2_client_credentials()

        assert oauth2_client.access_token == 'oauth2_token'
        assert oauth2_client.refresh_token == 'oauth2_refresh'
        assert oauth2_client.token_expires_at is not None
        # Client secret should be cleared after successful auth
        assert oauth2_client._oauth2_client_secret is None

    @pytest.mark.asyncio
    async def test_oauth2_sends_correct_request(self, oauth2_client):
        """Test that OAuth2 sends correct form-encoded request."""
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.headers = {'Content-Type': 'application/json'}
        mock_resp.json = AsyncMock(return_value={
            'access_token': 'token',
            'expires_in': 900
        })

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.post.return_value = mock_cm
        oauth2_client.session = mock_session

        with patch.object(oauth2_client, 'ensure_session'):
            await oauth2_client._authenticate_oauth2_client_credentials()

        # Verify the POST was made to the token endpoint
        call_args = mock_session.post.call_args
        assert call_args[0][0] == 'https://test.agiloft.com/oauth/token'
        # Verify form data
        sent_data = call_args[1]['data']
        assert sent_data['grant_type'] == 'client_credentials'
        assert sent_data['client_id'] == 'test-client-id'
        assert sent_data['client_secret'] == 'test-client-secret'
        assert sent_data['kb'] == 'TestKB'

    @pytest.mark.asyncio
    async def test_oauth2_http_error(self, oauth2_client):
        """Test OAuth2 authentication failure with HTTP error."""
        mock_resp = AsyncMock()
        mock_resp.status = 400
        mock_resp.text = AsyncMock(return_value='Bad Request')

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.post.return_value = mock_cm
        oauth2_client.session = mock_session

        with patch.object(oauth2_client, 'ensure_session'):
            with pytest.raises(AgiloftAuthError, match="OAuth2 authentication failed: 400"):
                await oauth2_client._authenticate_oauth2_client_credentials()

    @pytest.mark.asyncio
    async def test_oauth2_unexpected_content_type(self, oauth2_client):
        """Test OAuth2 failure when response is not JSON."""
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.headers = {'Content-Type': 'text/html'}

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.post.return_value = mock_cm
        oauth2_client.session = mock_session

        with patch.object(oauth2_client, 'ensure_session'):
            with pytest.raises(AgiloftAuthError, match="unexpected content type"):
                await oauth2_client._authenticate_oauth2_client_credentials()

    @pytest.mark.asyncio
    async def test_oauth2_missing_access_token(self, oauth2_client):
        """Test OAuth2 failure when response has no access_token."""
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.headers = {'Content-Type': 'application/json'}
        mock_resp.json = AsyncMock(return_value={'expires_in': 900})

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.post.return_value = mock_cm
        oauth2_client.session = mock_session

        with patch.object(oauth2_client, 'ensure_session'):
            with pytest.raises(AgiloftAuthError, match="No access_token"):
                await oauth2_client._authenticate_oauth2_client_credentials()

    @pytest.mark.asyncio
    async def test_oauth2_missing_credentials(self):
        """Test OAuth2 failure when client_id is missing."""
        config = MagicMock(spec=Config)
        config.get.side_effect = lambda key, default=None: {
            'agiloft.base_url': 'https://test.agiloft.com/api',
            'agiloft.kb': 'TestKB',
            'agiloft.language': 'en',
            'agiloft.auth_method': 'oauth2_client_credentials',
            'agiloft.username': '',
            'agiloft.password': '',
            'agiloft.oauth2.client_id': '',
            'agiloft.oauth2.client_secret': '',
            'agiloft.oauth2.token_endpoint': 'https://test.com/token',
            'agiloft.oauth2.authorization_endpoint': '',
            'agiloft.oauth2.redirect_uri': 'http://localhost:8080/callback',
            'agiloft.oauth2.scope': '',
        }.get(key, default)
        client = AgiloftClient(config)

        with pytest.raises(AgiloftAuthError, match="client_id and client_secret are required"):
            await client._authenticate_oauth2_client_credentials()


class TestTokenRefresh:
    """Test token refresh functionality."""

    @pytest.mark.asyncio
    async def test_refresh_success(self, oauth2_client):
        """Test successful token refresh."""
        oauth2_client.refresh_token = 'old_refresh'
        oauth2_client.access_token = 'old_token'

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.headers = {'Content-Type': 'application/json'}
        mock_resp.text = AsyncMock(return_value=json.dumps({
            'access_token': 'new_token',
            'expires_in': 900,
            'refresh_token': 'new_refresh'
        }))

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.post.return_value = mock_cm
        oauth2_client.session = mock_session

        with patch.object(oauth2_client, 'ensure_session'):
            await oauth2_client._refresh_access_token()

        assert oauth2_client.access_token == 'new_token'
        assert oauth2_client.refresh_token == 'new_refresh'

    @pytest.mark.asyncio
    async def test_refresh_no_token(self, oauth2_client):
        """Test refresh fails gracefully when no refresh token."""
        oauth2_client.refresh_token = None

        with pytest.raises(AgiloftAuthError, match="No refresh token"):
            await oauth2_client._refresh_access_token()

    @pytest.mark.asyncio
    async def test_refresh_token_rotation(self, oauth2_client):
        """Test that new refresh token replaces old one (rotation)."""
        oauth2_client.refresh_token = 'old_refresh'

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.headers = {'Content-Type': 'application/json'}
        mock_resp.text = AsyncMock(return_value=json.dumps({
            'access_token': 'new_token',
            'expires_in': 900,
            'refresh_token': 'rotated_refresh'
        }))

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.post.return_value = mock_cm
        oauth2_client.session = mock_session

        with patch.object(oauth2_client, 'ensure_session'):
            await oauth2_client._refresh_access_token()

        assert oauth2_client.refresh_token == 'rotated_refresh'

    @pytest.mark.asyncio
    async def test_ensure_authenticated_uses_refresh(self, oauth2_client):
        """Test that ensure_authenticated tries refresh before full auth."""
        oauth2_client.access_token = 'expired_token'
        oauth2_client.refresh_token = 'valid_refresh'
        oauth2_client.token_expires_at = datetime.now() - timedelta(minutes=5)

        with patch.object(oauth2_client, '_refresh_access_token') as mock_refresh:
            await oauth2_client.ensure_authenticated()
            mock_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_authenticated_falls_back_on_refresh_failure(self, oauth2_client):
        """Test fallback to full auth when refresh fails."""
        oauth2_client.access_token = 'expired_token'
        oauth2_client.refresh_token = 'bad_refresh'
        oauth2_client.token_expires_at = datetime.now() - timedelta(minutes=5)

        with patch.object(oauth2_client, '_refresh_access_token',
                          side_effect=AgiloftAuthError("Refresh failed")), \
             patch.object(oauth2_client, '_authenticate') as mock_auth:
            await oauth2_client.ensure_authenticated()
            mock_auth.assert_called_once()
            assert oauth2_client.refresh_token is None


class TestSanitizeError:
    """Test error message sanitization."""

    def test_truncates_long_messages(self):
        assert "truncated" in AgiloftClient._sanitize_error("x" * 300)

    def test_short_messages_pass_through(self):
        assert AgiloftClient._sanitize_error("short error") == "short error"

    def test_empty_message(self):
        assert AgiloftClient._sanitize_error("") == "(empty response)"

    def test_none_message(self):
        assert AgiloftClient._sanitize_error(None) == "(empty response)"


class TestAgiloftClientRequests:
    """Test API request methods."""

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
    async def test_make_request_401_tries_refresh_first(self, client):
        """Test that 401 retry tries refresh token before full re-auth."""
        client.access_token = 'test_token'
        client.refresh_token = 'valid_refresh'
        client.token_expires_at = datetime.now() + timedelta(minutes=10)

        # First response: 401
        mock_resp_401 = AsyncMock()
        mock_resp_401.status = 401
        mock_resp_401.text = AsyncMock(return_value='Unauthorized')

        mock_cm_401 = MagicMock()
        mock_cm_401.__aenter__ = AsyncMock(return_value=mock_resp_401)
        mock_cm_401.__aexit__ = AsyncMock(return_value=None)

        # Second response: 200
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
             patch.object(client, '_refresh_access_token') as mock_refresh:
            result = await client._make_request('GET', '/test')

            assert result == {"result": "success"}
            mock_refresh.assert_called_once()

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
            assert client.api_access_point is None

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

    def test_path_traversal_stripped(self):
        """Filename with path traversal components should be stripped."""
        resp = MagicMock()
        resp.headers = {
            "Content-Disposition": 'attachment; filename="../../etc/passwd"',
            "Content-Type": "application/octet-stream",
        }
        filename, ct = AgiloftClient._read_binary_response_headers(resp)
        assert filename == "passwd"
        assert "/" not in filename


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
           patch('src.agiloft_client.os.path.exists', return_value=False), \
           patch('src.agiloft_client.os.path.realpath', side_effect=lambda p: p):
            result = await client.retrieve_attachment('/attachment', 1, 'field')

        mock_makedirs.assert_called_once_with(default_dir, exist_ok=True)
        assert result["file_path"].startswith(default_dir)
