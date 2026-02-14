"""
Agiloft API Client

Handles authentication, session management, and API calls to Agiloft REST API.
Provides generic entity-agnostic methods for CRUD, search, upsert, and
attachment operations. Also maintains backward-compatible contract-specific
wrapper methods.

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
            now = datetime.now()
            if (self.access_token is None or
                self.token_expires_at is None or
                    now >= self.token_expires_at - timedelta(minutes=1)):
                await self._authenticate()

    async def _authenticate(self):
        """Perform authentication with Agiloft API."""
        await self.ensure_session()

        login_url = f"{self.base_url}/login"
        login_data = {
            "password": self.password,
            "KB": self.kb,
            "login": self.username,
            "lang": self.language,
        }

        logger.info("Authenticating with Agiloft...")

        try:
            async with self.session.post(login_url, json=login_data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    error_msg = f"Authentication failed: {response.status} - {error_text}"
                    logger.error(f"{error_msg} (KB: {self.kb})")
                    raise AgiloftAuthError(error_msg)

                data = await response.json()

                if not data.get('success', False):
                    error_msg = f"Authentication failed: {data.get('message', 'Unknown error')}"
                    logger.error(f"{error_msg} (KB: {self.kb})")
                    raise AgiloftAuthError(error_msg)

                result = data.get('result', {})
                self.access_token = result.get('access_token')
                self.refresh_token = result.get('refresh_token')
                expires_in = result.get('expires_in', 15)

                self.token_expires_at = datetime.now() + timedelta(minutes=expires_in)
                logger.info(f"Authentication successful. Token expires at {self.token_expires_at}")

        except AgiloftAuthError:
            raise
        except Exception as e:
            logger.error(f"Authentication error: {type(e).__name__}")
            raise

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for API requests."""
        if not self.access_token:
            raise AgiloftAuthError("No access token available")

        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
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

        # Merge headers, allowing None values to remove defaults
        if 'headers' in kwargs:
            for k, v in kwargs.pop('headers').items():
                if v is None:
                    headers.pop(k, None)
                else:
                    headers[k] = v
        kwargs['headers'] = headers

        logger.debug(f"{method.upper()} {url}")

        try:
            async with self.session.request(method, url, **kwargs) as response:
                response_text = await response.text()

                if response.status == 401:
                    logger.warning(f"Received 401 for {method} {url}, attempting re-authentication...")
                    await self._authenticate()

                    kwargs['headers'] = self._get_auth_headers()
                    async with self.session.request(method, url, **kwargs) as retry_response:
                        response_text = await retry_response.text()
                        if retry_response.status != 200:
                            error_msg = f"API request failed after re-auth: {retry_response.status}"
                            logger.error(f"{error_msg} (URL: {url})")
                            raise AgiloftAPIError(
                                error_msg,
                                status_code=retry_response.status,
                                response_text=response_text,
                            )
                        return json.loads(response_text)

                elif response.status != 200:
                    error_msg = f"API request failed: {response.status} - {response_text}"
                    logger.error(f"API request failed: {response.status} (URL: {url}, Method: {method})")
                    raise AgiloftAPIError(
                        error_msg,
                        status_code=response.status,
                        response_text=response_text,
                    )

                return json.loads(response_text)

        except aiohttp.ClientError as e:
            error_msg = f"HTTP client error for {method} {url}: {str(e)}"
            logger.error(error_msg)
            raise AgiloftAPIError(error_msg)

    # --- Helper methods ---

    def _extract_record(self, response: Any, record_id: int) -> Dict[str, Any]:
        """Extract a single record from various Agiloft response formats."""
        if isinstance(response, dict):
            if 'result' in response:
                return response['result']
            # Check for entity-specific key (e.g., 'contract', 'company')
            non_meta_keys = [
                k for k in response.keys()
                if k not in ('success', 'message', 'errors')
            ]
            if len(non_meta_keys) == 1 and isinstance(response[non_meta_keys[0]], dict):
                return response[non_meta_keys[0]]
            if 'id' in response:
                return response
        if isinstance(response, list) and len(response) > 0:
            return response[0]

        keys_info = list(response.keys()) if isinstance(response, dict) else type(response).__name__
        raise AgiloftAPIError(
            f"Record {record_id} not found in response. Keys: {keys_info}"
        )

    def _check_response(self, response: Dict[str, Any], operation: str) -> None:
        """Check API response for errors. Raises AgiloftAPIError on failure."""
        if not response.get('success', True):
            error_msg = response.get('message', 'Unknown error')
            errors = response.get('errors', [])
            if errors:
                error_details = "; ".join(
                    error.get('message', str(error)) for error in errors
                )
                error_msg += f" - {error_details}"
            raise AgiloftAPIError(f"{operation} failed: {error_msg}")

    # --- Generic Entity Methods ---

    async def search_records(self, entity_path: str, query: str = "",
                             fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Search records for any entity."""
        search_data = {
            "search": "",
            "field": fields or [],
            "query": query,
        }
        response = await self._make_request("POST", f"{entity_path}/search", json=search_data)
        if not response.get('success', False):
            raise AgiloftAPIError(f"Search failed: {response.get('message', 'Unknown error')}")
        return response.get('result', [])

    async def get_record(self, entity_path: str, record_id: int,
                         fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get a specific record by ID for any entity."""
        params = {}
        if fields:
            params['fields'] = ','.join(fields)

        response = await self._make_request("GET", f"{entity_path}/{record_id}", params=params)
        record = self._extract_record(response, record_id)

        # Client-side field filtering
        if fields:
            return {k: v for k, v in record.items() if k in fields}
        return record

    async def create_record(self, entity_path: str,
                            data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a record for any entity."""
        response = await self._make_request("POST", entity_path, json=data)
        self._check_response(response, "Create")
        return response

    async def update_record(self, entity_path: str, record_id: int,
                            data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a record for any entity."""
        response = await self._make_request("PUT", f"{entity_path}/{record_id}", json=data)
        self._check_response(response, "Update")
        return response

    async def delete_record(self, entity_path: str, record_id: int,
                            delete_rule: str = "UNLINK_WHERE_POSSIBLE_OTHERWISE_DELETE") -> Dict[str, Any]:
        """Delete a record for any entity."""
        params = {"deleteRule": delete_rule}
        response = await self._make_request("DELETE", f"{entity_path}/{record_id}", params=params)
        if not response.get('success', False):
            self._check_response(response, "Delete")
        return response

    async def upsert_record(self, entity_path: str, query: str,
                            data: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert (insert or update) a record for any entity.

        Args:
            entity_path: API path for the entity
            query: Match query in format fieldName~='value'
            data: Record data to insert/update
        """
        response = await self._make_request(
            "POST", f"{entity_path}/upsert",
            params={"query": query},
            json=data,
        )
        self._check_response(response, "Upsert")
        return response

    async def attach_file(self, entity_path: str, record_id: int,
                          field: str, file_name: str,
                          file_data: bytes) -> Dict[str, Any]:
        """Attach a file to a record."""
        form_data = aiohttp.FormData()
        form_data.add_field('uploadFile', file_data, filename=file_name)
        params = {"field": field, "fileName": file_name}
        # Remove Content-Type to let aiohttp set multipart boundary
        response = await self._make_request(
            "POST", f"{entity_path}/attach/{record_id}",
            params=params,
            data=form_data,
            headers={"Content-Type": None},
        )
        return response

    async def retrieve_attachment(self, entity_path: str, record_id: int,
                                  field: str, file_position: int = 0) -> Dict[str, Any]:
        """Retrieve an attachment from a record."""
        params = {"field": field, "filePosition": file_position}
        response = await self._make_request(
            "POST", f"{entity_path}/retrieveAttach/{record_id}", params=params
        )
        return response

    async def remove_attachment(self, entity_path: str, record_id: int,
                                field: str, file_position: int = 0) -> Dict[str, Any]:
        """Remove an attachment from a record."""
        params = {"field": field, "filePosition": file_position}
        response = await self._make_request(
            "POST", f"{entity_path}/removeAttach/{record_id}", params=params
        )
        return response

    async def get_attachment_info(self, entity_path: str, record_id: int,
                                  field: str) -> Dict[str, Any]:
        """Get attachment metadata for a record."""
        params = {"field": field}
        response = await self._make_request(
            "POST", f"{entity_path}/attachInfo/{record_id}", params=params
        )
        return response

    # --- Backward-compatible Contract Wrappers ---

    async def search_contracts(self, query: str = "",
                               fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Search for contracts. Wraps search_records for backward compatibility."""
        default_fields = [
            "id", "record_type", "contract_title1", "company_name", "date_created",
            "date_submitted", "date_signed", "contract_amount", "contract_end_date",
            "contract_term_in_months", "internal_contract_owner",
        ]
        return await self.search_records("/contract", query, fields or default_fields)

    async def get_contract(self, contract_id: int,
                           fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get a specific contract by ID. Wraps get_record for backward compatibility."""
        return await self.get_record("/contract", contract_id, fields)

    async def create_contract(self, contract_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new contract. Wraps create_record for backward compatibility."""
        return await self.create_record("/contract", contract_data)

    async def update_contract(self, contract_id: int,
                              contract_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing contract. Wraps update_record for backward compatibility."""
        return await self.update_record("/contract", contract_id, contract_data)

    async def delete_contract(self, contract_id: int,
                              delete_rule: str = "UNLINK_WHERE_POSSIBLE_OTHERWISE_DELETE") -> Dict[str, Any]:
        """Delete a contract. Wraps delete_record for backward compatibility."""
        return await self.delete_record("/contract", contract_id, delete_rule)

    # --- Utility methods ---

    async def logout(self):
        """Logout and invalidate tokens."""
        if self.access_token:
            try:
                await self._make_request("POST", "/logout")
                logger.info("Logged out successfully")
            except Exception as e:
                logger.warning(f"Logout failed: {type(e).__name__}")
            finally:
                self.access_token = None
                self.refresh_token = None
                self.token_expires_at = None
