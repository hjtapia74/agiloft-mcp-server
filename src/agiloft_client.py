"""
Agiloft API Client

Handles authentication, session management, and API calls to Agiloft REST API.
Automatically manages token refresh for the 15-minute expiration window.
"""

import aiohttp
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
# Handle both direct execution and package imports
try:
    from .config import Config
    from .exceptions import AgiloftAuthError, AgiloftAPIError
except ImportError:
    from config import Config
    from exceptions import AgiloftAuthError, AgiloftAPIError

logger = logging.getLogger(__name__)

class AgiloftClient:
    """Agiloft REST API client with automatic authentication and token refresh."""
    
    def __init__(self, config: Config):
        self.config = config
        self.base_url = config.get('agiloft.base_url')
        self.username = config.get('agiloft.username')
        self.password = config.get('agiloft.password')
        self.kb = config.get('agiloft.kb')
        self.language = config.get('agiloft.language', 'en')
        
        # Session management
        self.session: Optional[aiohttp.ClientSession] = None
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
        self._auth_lock = asyncio.Lock()
        
    async def __aenter__(self):
        """Async context manager entry."""
        await self.ensure_session()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
        
    async def ensure_session(self):
        """Ensure HTTP session is created."""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
            
    async def close(self):
        """Close the HTTP session."""
        if self.session and not self.session.closed:
            await self.session.close()
            
    async def ensure_authenticated(self):
        """Ensure we have a valid authentication token."""
        async with self._auth_lock:
            # Check if we need to authenticate or refresh
            now = datetime.now()
            
            if (self.access_token is None or 
                self.token_expires_at is None or 
                now >= self.token_expires_at - timedelta(minutes=1)):  # Refresh 1 min early
                
                await self._authenticate()
                
    async def _authenticate(self):
        """Perform authentication with Agiloft API."""
        await self.ensure_session()
        
        login_url = f"{self.base_url}/login"
        login_data = {
            "password": self.password,
            "KB": self.kb,
            "login": self.username,
            "lang": self.language
        }
        
        logger.info("Authenticating with Agiloft...")
        
        try:
            async with self.session.post(login_url, json=login_data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    error_msg = f"Authentication failed: {response.status} - {error_text}"
                    logger.error(f"{error_msg} (URL: {login_url}, Username: {self.username}, KB: {self.kb})")
                    raise AgiloftAuthError(error_msg)
                    
                data = await response.json()
                
                if not data.get('success', False):
                    error_msg = f"Authentication failed: {data.get('message', 'Unknown error')}"
                    logger.error(f"{error_msg} (Username: {self.username}, KB: {self.kb}, Response: {data})")
                    raise AgiloftAuthError(error_msg)
                    
                result = data.get('result', {})
                self.access_token = result.get('access_token')
                self.refresh_token = result.get('refresh_token')
                expires_in = result.get('expires_in', 15)  # Default 15 minutes
                
                # Calculate expiration time
                self.token_expires_at = datetime.now() + timedelta(minutes=expires_in)
                
                logger.info(f"Authentication successful. Token expires at {self.token_expires_at}")
                
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            raise
            
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for API requests."""
        if not self.access_token:
            raise AgiloftAuthError("No access token available")
            
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make an authenticated request to the Agiloft API."""
        await self.ensure_authenticated()
        await self.ensure_session()
        
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = self._get_auth_headers()
        
        # Add language parameter if not already present
        params = kwargs.get('params', {})
        if 'lang' not in params:
            params['lang'] = self.language
            kwargs['params'] = params
            
        # Merge headers
        if 'headers' in kwargs:
            headers.update(kwargs['headers'])
        kwargs['headers'] = headers
        
        logger.debug(f"{method.upper()} {url}")
        
        try:
            async with self.session.request(method, url, **kwargs) as response:
                response_text = await response.text()
                response_headers = dict(response.headers)
                
                if response.status == 401:
                    # Token might be expired, try re-authenticating once
                    logger.warning(f"Received 401 for {method} {url}, attempting re-authentication...")
                    await self._authenticate()
                    
                    # Retry the request with new token
                    kwargs['headers'] = self._get_auth_headers()
                    async with self.session.request(method, url, **kwargs) as retry_response:
                        response_text = await retry_response.text()
                        response_headers = dict(retry_response.headers)
                        if retry_response.status != 200:
                            error_msg = f"API request failed after re-auth: {retry_response.status} - {response_text}"
                            logger.error(f"{error_msg} (URL: {url}, Headers: {response_headers})")
                            raise AgiloftAPIError(
                                error_msg,
                                status_code=retry_response.status,
                                response_text=response_text
                            )
                        return await retry_response.json()
                        
                elif response.status != 200:
                    error_msg = f"API request failed: {response.status} - {response_text}"
                    logger.error(f"{error_msg} (URL: {url}, Method: {method}, Headers: {response_headers})")
                    raise AgiloftAPIError(
                        error_msg,
                        status_code=response.status,
                        response_text=response_text
                    )
                    
                return await response.json()
                
        except aiohttp.ClientError as e:
            error_msg = f"HTTP client error for {method} {url}: {str(e)}"
            logger.error(error_msg)
            raise AgiloftAPIError(error_msg)
            
    # Contract API Methods
    
    async def search_contracts(self, query: str = "", fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Search for contracts."""
        search_data = {
            "search": "",
            "field": fields or [
                "id", "record_type", "contract_title1", "company_name", "date_created",
                "date_submitted", "date_signed", "contract_amount", "contract_end_date",
                "contract_term_in_months", "internal_contract_owner"
            ],
            "query": query
        }
        
        response = await self._make_request("POST", "/contract/search", json=search_data)
        
        if not response.get('success', False):
            raise AgiloftAPIError(f"Search failed: {response.get('message', 'Unknown error')}")
            
        return response.get('result', [])
        
    async def get_contract(self, contract_id: int, fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get a specific contract by ID."""
        params = {}
        if fields:
            # Note: The API doesn't seem to support field filtering on GET, but we'll include it for completeness
            params['fields'] = ','.join(fields)
        
        endpoint = f"/contract/{contract_id}"
        logger.debug(f"Getting contract with endpoint: {endpoint}")
        
        response = await self._make_request("GET", endpoint, params=params)
        
        logger.debug(f"Get contract response keys: {list(response.keys())}")
        logger.debug(f"Get contract response: {response}")
        
        # Check multiple possible response formats
        if 'result' in response:
            # Standard Agiloft API format with result key
            contract = response['result']
        elif 'contract' in response:
            # Alternative format with contract key
            contract = response['contract']
        elif isinstance(response, dict) and 'id' in response:
            # Sometimes the response is the contract directly
            contract = response
        elif isinstance(response, list) and len(response) > 0:
            # Sometimes the response is a list with one contract
            contract = response[0]
        else:
            logger.error(f"Unexpected response format for contract {contract_id}: {response}")
            raise AgiloftAPIError(f"Contract not found in response. Response keys: {list(response.keys()) if isinstance(response, dict) else type(response)}")
            
        # If specific fields requested, filter the response
        if fields:
            filtered_contract = {}
            for field in fields:
                if field in contract:
                    filtered_contract[field] = contract[field]
            return filtered_contract
            
        return contract
            
    async def create_contract(self, contract_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new contract."""
        response = await self._make_request("POST", "/contract", json=contract_data)
        
        if not response.get('success', True):  # Some endpoints may not have success field
            error_msg = response.get('message', 'Unknown error')
            errors = response.get('errors', [])
            if errors:
                error_details = "; ".join([error.get('message', str(error)) for error in errors])
                error_msg += f" - {error_details}"
            raise AgiloftAPIError(f"Create failed: {error_msg}")
            
        return response
        
    async def update_contract(self, contract_id: int, contract_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing contract."""
        response = await self._make_request("PUT", f"/contract/{contract_id}", json=contract_data)
        
        if not response.get('success', True):
            error_msg = response.get('message', 'Unknown error')
            errors = response.get('errors', [])
            if errors:
                error_details = "; ".join([error.get('message', str(error)) for error in errors])
                error_msg += f" - {error_details}"
            raise AgiloftAPIError(f"Update failed: {error_msg}")
            
        return response
        
    async def delete_contract(self, contract_id: int, delete_rule: str = "UNLINK_WHERE_POSSIBLE_OTHERWISE_DELETE") -> Dict[str, Any]:
        """Delete a contract."""
        params = {
            "deleteRule": delete_rule
        }
        
        response = await self._make_request("DELETE", f"/contract/{contract_id}", params=params)
        
        if not response.get('success', False):
            error_msg = response.get('message', 'Unknown error')
            errors = response.get('errors', [])
            if errors:
                error_details = "; ".join([error.get('message', str(error)) for error in errors])
                error_msg += f" - {error_details}"
            raise AgiloftAPIError(f"Delete failed: {error_msg}")
            
        return response
        
    # Utility methods
    
    async def logout(self):
        """Logout and invalidate tokens."""
        if self.access_token:
            try:
                await self._make_request("POST", "/logout")
                logger.info("Logged out successfully")
            except Exception as e:
                logger.warning(f"Logout failed: {str(e)}")
            finally:
                self.access_token = None
                self.refresh_token = None
                self.token_expires_at = None