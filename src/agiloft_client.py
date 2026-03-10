"""
Agiloft API Client

Handles authentication, session management, and API calls to Agiloft REST API.
Provides generic entity-agnostic methods for CRUD, search, upsert, and
attachment operations. Also maintains backward-compatible contract-specific
wrapper methods.

Supports three authentication methods:
- Legacy username/password login
- OAuth2 Client Credentials (machine-to-machine)
- OAuth2 Authorization Code (browser-based, requires manual initiation)

Automatically manages token refresh for the 15-minute expiration window.
"""

import aiohttp
import asyncio
import json
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

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
        self.kb = config.get('agiloft.kb')
        self.language = config.get('agiloft.language', 'en')

        # Authentication method
        self.auth_method = config.get('agiloft.auth_method', 'legacy')

        # Legacy credentials (only used for legacy auth)
        self.username = config.get('agiloft.username')
        self._password = config.get('agiloft.password')

        # OAuth2 credentials
        self.oauth2_client_id = config.get('agiloft.oauth2.client_id')
        self._oauth2_client_secret = config.get('agiloft.oauth2.client_secret')
        self.oauth2_token_endpoint = config.get('agiloft.oauth2.token_endpoint')
        self.oauth2_authorization_endpoint = config.get('agiloft.oauth2.authorization_endpoint')
        self.oauth2_redirect_uri = config.get('agiloft.oauth2.redirect_uri', 'http://localhost:8080/callback')
        self.oauth2_scope = config.get('agiloft.oauth2.scope', '')

        # Session management
        self.session: Optional[aiohttp.ClientSession] = None
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
        self.api_access_point: Optional[str] = None
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
        """Ensure we have a valid authentication token.

        Tries token refresh first (if a refresh token is available),
        falling back to full authentication on failure.
        """
        async with self._auth_lock:
            now = datetime.now()
            if (self.access_token is None or
                self.token_expires_at is None or
                    now >= self.token_expires_at - timedelta(minutes=1)):

                # Try refresh first if available
                if self.refresh_token:
                    try:
                        await self._refresh_access_token()
                        return
                    except AgiloftAuthError as e:
                        logger.warning(f"Token refresh failed, falling back to authentication: {e}")
                        self.refresh_token = None

                await self._authenticate()

    async def _authenticate(self):
        """Route to the correct authentication method."""
        if self.auth_method == "oauth2_client_credentials":
            await self._authenticate_oauth2_client_credentials()
        elif self.auth_method == "oauth2_authorization_code":
            if self.refresh_token:
                try:
                    await self._refresh_access_token()
                    return
                except AgiloftAuthError:
                    self.refresh_token = None
            raise AgiloftAuthError(
                "OAuth2 Authorization Code flow requires browser-based authentication. "
                "Call authenticate_with_browser() before using the client."
            )
        else:
            await self._authenticate_legacy()

    async def _authenticate_legacy(self):
        """Perform legacy username/password authentication with Agiloft API."""
        await self.ensure_session()

        if not self._password:
            raise AgiloftAuthError("No password configured for legacy authentication")

        login_url = f"{self.base_url}/login"
        login_data = {
            "password": self._password,
            "KB": self.kb,
            "login": self.username,
            "lang": self.language,
        }

        logger.info("Authenticating with Agiloft (legacy)...")

        try:
            async with self.session.post(login_url, json=login_data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise AgiloftAuthError(
                        f"Authentication failed: {response.status} - "
                        f"{self._sanitize_error(error_text)}"
                    )

                data = await response.json()

                if not data.get('success', False):
                    raise AgiloftAuthError(
                        f"Authentication failed: {data.get('message', 'Unknown error')}"
                    )

                result = data.get('result', {})
                self.access_token = result.get('access_token')
                self.refresh_token = result.get('refresh_token')
                expires_in = result.get('expires_in', 900)

                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                logger.info(f"Legacy authentication successful. Token expires at {self.token_expires_at}")

                # Clear password from memory after successful auth
                self._password = None

        except AgiloftAuthError:
            raise
        except Exception as e:
            logger.error(f"Authentication error: {type(e).__name__}")
            raise AgiloftAuthError(f"Authentication failed: {type(e).__name__}")

    async def _authenticate_oauth2_client_credentials(self):
        """Perform OAuth2 client credentials authentication."""
        await self.ensure_session()

        if not self.oauth2_client_id or not self._oauth2_client_secret:
            raise AgiloftAuthError(
                "OAuth2 client_id and client_secret are required for client_credentials flow"
            )
        if not self.oauth2_token_endpoint:
            raise AgiloftAuthError("OAuth2 token_endpoint is required")

        logger.info("Authenticating with Agiloft (OAuth2 client credentials)...")

        token_data = {
            "grant_type": "client_credentials",
            "client_id": self.oauth2_client_id,
            "client_secret": self._oauth2_client_secret,
            "kb": self.kb
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json"
        }

        try:
            async with self.session.post(
                self.oauth2_token_endpoint,
                data=token_data,
                headers=headers
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise AgiloftAuthError(
                        f"OAuth2 authentication failed: {response.status} - "
                        f"{self._sanitize_error(error_text)}"
                    )

                content_type = response.headers.get('Content-Type', '')
                if 'application/json' not in content_type:
                    raise AgiloftAuthError(
                        f"OAuth2 token endpoint returned unexpected content type: {content_type}"
                    )

                data = await response.json()

                self.access_token = data.get('access_token')
                if not self.access_token:
                    raise AgiloftAuthError("No access_token in OAuth2 response")

                expires_in = data.get('expires_in', 900)
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                self.refresh_token = data.get('refresh_token')

                logger.info(f"OAuth2 authentication successful. Token expires at {self.token_expires_at}")

                # Clear client secret from memory after successful auth
                self._oauth2_client_secret = None

        except AgiloftAuthError:
            raise
        except Exception as e:
            logger.error(f"OAuth2 authentication error: {type(e).__name__}")
            raise AgiloftAuthError(f"OAuth2 authentication failed: {type(e).__name__}")

    async def _refresh_access_token(self):
        """Refresh the access token using the stored refresh token.

        Determines the correct token endpoint and sends a refresh_token
        grant request. Supports token rotation (new refresh token in response).
        """
        if not self.refresh_token:
            raise AgiloftAuthError("No refresh token available")

        await self.ensure_session()

        # Determine token endpoint (configured > api_access_point > derived)
        if self.oauth2_token_endpoint:
            token_url = self.oauth2_token_endpoint
        elif self.api_access_point:
            token_url = f"{self.api_access_point}/ewws/otoken"
        else:
            base_url = self.base_url.split('/ewws/alrest')[0]
            token_url = f"{base_url}/ewws/otoken"

        logger.info("Refreshing access token...")

        token_data = {
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token,
            'client_id': self.oauth2_client_id or '',
            'redirect_uri': self.oauth2_redirect_uri
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json"
        }

        try:
            async with self.session.post(
                token_url, data=token_data, headers=headers
            ) as response:
                response_text = await response.text()

                if response.status != 200:
                    raise AgiloftAuthError(
                        f"Token refresh failed: {response.status} - "
                        f"{self._sanitize_error(response_text)}"
                    )

                content_type = response.headers.get('Content-Type', '')
                if 'application/json' not in content_type:
                    raise AgiloftAuthError(
                        f"Token refresh returned unexpected content type: {content_type}"
                    )

                data = json.loads(response_text)

                new_token = data.get('access_token')
                if not new_token:
                    raise AgiloftAuthError("No access_token in refresh response")

                self.access_token = new_token
                expires_in = data.get('expires_in', 900)
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)

                # Support token rotation
                new_refresh = data.get('refresh_token')
                if new_refresh:
                    self.refresh_token = new_refresh

                logger.info(f"Token refresh successful. Expires at {self.token_expires_at}")

        except AgiloftAuthError:
            raise
        except Exception as e:
            logger.error(f"Token refresh error: {type(e).__name__}")
            raise AgiloftAuthError(f"Token refresh failed: {type(e).__name__}")

    @staticmethod
    def _sanitize_error(error_text: str, max_len: int = 200) -> str:
        """Truncate and sanitize error text to avoid leaking server internals."""
        if not error_text:
            return "(empty response)"
        sanitized = error_text[:max_len]
        if len(error_text) > max_len:
            sanitized += "... (truncated)"
        return sanitized

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for API requests."""
        if not self.access_token:
            raise AgiloftAuthError("No access token available")

        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @staticmethod
    def _guess_extension(content_type: str) -> str:
        """Map a MIME content type to a file extension."""
        mime_map = {
            "application/pdf": ".pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
            "application/msword": ".doc",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
            "application/vnd.ms-excel": ".xls",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
            "application/vnd.ms-powerpoint": ".ppt",
            "application/zip": ".zip",
            "application/xml": ".xml",
            "text/xml": ".xml",
            "text/plain": ".txt",
            "text/csv": ".csv",
            "text/html": ".html",
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/gif": ".gif",
            "application/json": ".json",
            "application/octet-stream": ".bin",
        }
        # Normalize: strip parameters like charset
        base = content_type.split(";")[0].strip().lower() if content_type else ""
        return mime_map.get(base, ".bin")

    @staticmethod
    def _read_binary_response_headers(response) -> Tuple[Optional[str], str]:
        """Extract filename and content type from response headers.

        Returns:
            (filename_or_None, content_type)
        """
        content_type = response.headers.get("Content-Type", "application/octet-stream")
        filename = None
        cd = response.headers.get("Content-Disposition", "")
        if cd:
            # Try quoted filename first, then unquoted
            match = re.search(r'filename="(.+?)"', cd)
            if not match:
                match = re.search(r"filename=([^\s;]+)", cd)
            if match:
                # Strip path components to prevent directory traversal
                filename = os.path.basename(match.group(1))
        return filename, content_type

    async def _make_binary_request(self, method: str, endpoint: str,
                                   **kwargs) -> Tuple[bytes, Optional[str], str]:
        """Make an authenticated request that returns binary data.

        Same auth/retry pattern as _make_request but reads bytes instead of
        text. Uses a 120s timeout for large downloads.

        Returns:
            (file_bytes, filename_or_None, content_type)
        """
        await self.ensure_authenticated()
        await self.ensure_session()

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = self._get_auth_headers()

        params = kwargs.get('params', {})
        if 'lang' not in params:
            params['lang'] = self.language
            kwargs['params'] = params

        if 'headers' in kwargs:
            for k, v in kwargs.pop('headers').items():
                if v is None:
                    headers.pop(k, None)
                else:
                    headers[k] = v
        kwargs['headers'] = headers

        # Use a longer timeout for file downloads
        download_timeout = aiohttp.ClientTimeout(total=120)
        kwargs['timeout'] = download_timeout

        logger.debug(f"{method.upper()} {url} (binary)")

        try:
            async with self.session.request(method, url, **kwargs) as response:
                # Check if response is a JSON error
                resp_ct = response.headers.get("Content-Type", "")
                if response.status == 401:
                    logger.warning(f"Received 401 for binary {method} {url}, re-authenticating...")
                    await self._authenticate()
                    kwargs['headers'] = self._get_auth_headers()
                    async with self.session.request(method, url, **kwargs) as retry_response:
                        retry_ct = retry_response.headers.get("Content-Type", "")
                        if retry_response.status != 200:
                            error_text = await retry_response.text()
                            raise AgiloftAPIError(
                                f"Binary request failed after re-auth: {retry_response.status}",
                                status_code=retry_response.status,
                                response_text=error_text,
                            )
                        if "application/json" in retry_ct:
                            error_text = await retry_response.text()
                            data = json.loads(error_text)
                            if not data.get("success", True):
                                raise AgiloftAPIError(
                                    f"API error: {data.get('message', error_text)}",
                                    status_code=retry_response.status,
                                    response_text=error_text,
                                )
                        file_bytes = await retry_response.read()
                        filename, content_type = self._read_binary_response_headers(retry_response)
                        return file_bytes, filename, content_type

                elif response.status != 200:
                    error_text = await response.text()
                    raise AgiloftAPIError(
                        f"Binary request failed: {response.status} - "
                        f"{self._sanitize_error(error_text)}",
                        status_code=response.status,
                        response_text=error_text,
                    )

                # Check if 200 response is actually a JSON error
                if "application/json" in resp_ct:
                    error_text = await response.text()
                    data = json.loads(error_text)
                    if not data.get("success", True):
                        raise AgiloftAPIError(
                            f"API error: {data.get('message', error_text)}",
                            status_code=response.status,
                            response_text=error_text,
                        )

                file_bytes = await response.read()
                filename, content_type = self._read_binary_response_headers(response)
                return file_bytes, filename, content_type

        except asyncio.TimeoutError:
            error_msg = f"Binary request timed out for {method} {url}"
            logger.error(error_msg)
            raise AgiloftAPIError(error_msg)
        except aiohttp.ClientError as e:
            error_msg = f"HTTP client error for binary {method} {url}: {str(e)}"
            logger.error(error_msg)
            raise AgiloftAPIError(error_msg)

    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make an authenticated request to the Agiloft API.

        On 401, uses a lock to prevent concurrent refresh races. If another
        coroutine already refreshed the token, reuses it. Otherwise tries
        refresh_token first, falling back to full re-authentication.
        """
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

        # Snapshot token to detect concurrent refresh
        token_before_request = self.access_token

        logger.debug(f"{method.upper()} {url}")

        try:
            async with self.session.request(method, url, **kwargs) as response:
                response_text = await response.text()

                if response.status == 401:
                    logger.warning(f"Received 401 for {method} {url}, attempting token refresh...")
                    async with self._auth_lock:
                        if self.access_token != token_before_request:
                            # Another coroutine already refreshed
                            logger.info("Token already refreshed by concurrent request, retrying")
                        elif self.refresh_token:
                            try:
                                await self._refresh_access_token()
                            except AgiloftAuthError:
                                logger.warning("Token refresh failed on 401, falling back to _authenticate")
                                self.refresh_token = None
                                await self._authenticate()
                        else:
                            await self._authenticate()

                    # Retry with new token
                    kwargs['headers'] = self._get_auth_headers()
                    async with self.session.request(method, url, **kwargs) as retry_response:
                        response_text = await retry_response.text()
                        if retry_response.status != 200:
                            error_msg = (
                                f"API request failed after re-auth: "
                                f"{retry_response.status} - "
                                f"{self._sanitize_error(response_text)}"
                            )
                            logger.error(f"{error_msg} (URL: {url})")
                            raise AgiloftAPIError(
                                error_msg,
                                status_code=retry_response.status,
                                response_text=response_text,
                            )
                        return json.loads(response_text)

                elif response.status != 200:
                    error_msg = (
                        f"API request failed: {response.status} - "
                        f"{self._sanitize_error(response_text)}"
                    )
                    logger.error(f"API request failed: {response.status} (URL: {url}, Method: {method})")
                    raise AgiloftAPIError(
                        error_msg,
                        status_code=response.status,
                        response_text=response_text,
                    )

                return json.loads(response_text)

        except asyncio.TimeoutError:
            error_msg = f"Request timed out for {method} {url}"
            logger.error(error_msg)
            raise AgiloftAPIError(error_msg)
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
                             fields: Optional[List[str]] = None,
                             limit: int = 500) -> List[Dict[str, Any]]:
        """Search records for any entity."""
        search_data = {"query": query}
        if fields:
            search_data["field"] = fields
        response = await self._make_request(
            "POST", f"{entity_path}/search",
            json=search_data,
        )
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
        """Upsert (insert or update) a record for any entity."""
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
        """Attach a file to a record.

        Uses a longer timeout (120s) than the default session timeout (30s)
        to accommodate large file uploads.
        """
        form_data = aiohttp.FormData()
        form_data.add_field('uploadFile', file_data, filename=file_name)
        params = {"field": field, "fileName": file_name}
        upload_timeout = aiohttp.ClientTimeout(total=120)
        # Remove Content-Type to let aiohttp set multipart boundary
        response = await self._make_request(
            "POST", f"{entity_path}/attach/{record_id}",
            params=params,
            data=form_data,
            headers={"Content-Type": None},
            timeout=upload_timeout,
        )
        return response

    async def retrieve_attachment(self, entity_path: str, record_id: int,
                                  field: str, file_position: int = 0,
                                  save_dir: Optional[str] = None) -> Dict[str, Any]:
        """Retrieve an attachment from a record and save it to local disk.

        Args:
            entity_path: API path for the entity
            record_id: ID of the record
            field: File field name on the record
            file_position: 0-based index of the file in the field
            save_dir: Directory to save the file. Defaults to ~/Downloads/agiloft/

        Returns:
            Dict with file_path, file_name, file_size_bytes, content_type,
            record_id, and field.
        """
        if save_dir is None:
            save_dir = os.path.expanduser("~/Downloads/agiloft")

        params = {"field": field, "filePosition": file_position}
        file_bytes, filename, content_type = await self._make_binary_request(
            "POST", f"{entity_path}/retrieveAttach/{record_id}", params=params,
        )

        if not file_bytes:
            raise AgiloftAPIError(
                f"Empty response from retrieveAttach for record {record_id}, field '{field}'"
            )

        # Build filename if the server didn't provide one
        if not filename:
            ext = self._guess_extension(content_type)
            filename = f"{field}_{record_id}{ext}"

        # Sanitize filename to prevent path traversal
        filename = os.path.basename(filename)

        os.makedirs(save_dir, exist_ok=True)

        # Resolve save_dir to prevent path traversal via symlinks
        resolved_save_dir = os.path.realpath(save_dir)

        # Handle filename collisions
        base, ext = os.path.splitext(filename)
        target = os.path.join(resolved_save_dir, filename)
        counter = 1
        while os.path.exists(target):
            target = os.path.join(resolved_save_dir, f"{base}_{counter}{ext}")
            counter += 1

        # Verify final path is still within save_dir
        if not os.path.realpath(target).startswith(resolved_save_dir):
            raise AgiloftAPIError("Path traversal detected in attachment filename")

        with open(target, "wb") as f:
            f.write(file_bytes)

        final_name = os.path.basename(target)
        logger.info(f"Saved attachment to {target} ({len(file_bytes)} bytes)")

        return {
            "file_path": target,
            "file_name": final_name,
            "file_size_bytes": len(file_bytes),
            "content_type": content_type,
            "record_id": record_id,
            "field": field,
        }

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

    async def trigger_action_button(self, entity_path: str, record_id: int,
                                    button_name: str) -> Dict[str, Any]:
        """Trigger an action button on a record."""
        params = {"name": button_name}
        response = await self._make_request(
            "POST", f"{entity_path}/actionButton/{record_id}", params=params
        )
        return response

    async def evaluate_format(self, entity_path: str, record_id: int,
                              formula: str) -> Dict[str, Any]:
        """Evaluate a format/formula against a record."""
        response = await self._make_request(
            "POST", f"{entity_path}/evaluateFormat/{record_id}",
            json={"formula": formula}
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
                self.api_access_point = None
