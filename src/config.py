"""
Configuration Manager

Handles configuration loading from multiple sources with fallback priority:
1. Environment variables (highest priority)
2. Configuration file (config.json)
3. Default values (lowest priority)

Supports legacy (username/password) and OAuth2 (client_credentials) authentication.
"""

import json
import os
import logging
from typing import Any, Dict, Optional
from pathlib import Path
# Handle both direct execution and package imports
try:
    from .exceptions import AgiloftConfigError
except ImportError:
    from exceptions import AgiloftConfigError

logger = logging.getLogger(__name__)

# Auth method constants
AUTH_LEGACY = "legacy"
AUTH_OAUTH2_CLIENT_CREDENTIALS = "oauth2_client_credentials"
AUTH_OAUTH2_AUTHORIZATION_CODE = "oauth2_authorization_code"
VALID_AUTH_METHODS = {AUTH_LEGACY, AUTH_OAUTH2_CLIENT_CREDENTIALS, AUTH_OAUTH2_AUTHORIZATION_CODE}


class Config:
    """Configuration manager with multiple source support."""

    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self._config_data: Dict[str, Any] = {}
        self._load_config()

    def _load_config(self):
        """Load configuration from file and environment variables."""
        # Start with default configuration
        self._config_data = self._get_default_config()

        # Load from config file if it exists
        config_path = Path(self.config_file)
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    file_config = json.load(f)
                    self._merge_config(self._config_data, file_config)
                    logger.info(f"Loaded configuration from {config_path}")
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load config file {config_path}: {e}")
                raise AgiloftConfigError(f"Invalid configuration file {config_path}: {e}")
        else:
            logger.info(f"Config file {config_path} not found, using defaults and environment variables")

        # Override with environment variables
        self._load_from_environment()

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration values."""
        return {
            "agiloft": {
                "base_url": "",
                "username": "",
                "password": "",
                "kb": "",
                "language": "en",
                "auth_method": "legacy",
                "oauth2": {
                    "client_id": "",
                    "client_secret": "",
                    "token_endpoint": "",
                    "authorization_endpoint": "",
                    "redirect_uri": "http://localhost:8080/callback",
                    "scope": ""
                }
            },
            "server": {
                "port": 8000,
                "log_level": "INFO",
                "timeout": 30,
                "max_retries": 3
            }
        }

    def _merge_config(self, base: Dict[str, Any], override: Dict[str, Any]):
        """Recursively merge configuration dictionaries."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value

    def _load_from_environment(self):
        """Load configuration from environment variables."""
        env_mappings = {
            "AGILOFT_BASE_URL": "agiloft.base_url",
            "AGILOFT_USERNAME": "agiloft.username",
            "AGILOFT_PASSWORD": "agiloft.password",
            "AGILOFT_KB": "agiloft.kb",
            "AGILOFT_LANGUAGE": "agiloft.language",
            "AGILOFT_AUTH_METHOD": "agiloft.auth_method",
            "AGILOFT_OAUTH2_CLIENT_ID": "agiloft.oauth2.client_id",
            "AGILOFT_OAUTH2_CLIENT_SECRET": "agiloft.oauth2.client_secret",
            "AGILOFT_OAUTH2_TOKEN_ENDPOINT": "agiloft.oauth2.token_endpoint",
            "AGILOFT_OAUTH2_AUTHORIZATION_ENDPOINT": "agiloft.oauth2.authorization_endpoint",
            "AGILOFT_OAUTH2_REDIRECT_URI": "agiloft.oauth2.redirect_uri",
            "AGILOFT_OAUTH2_SCOPE": "agiloft.oauth2.scope",
            "MCP_SERVER_PORT": "server.port",
            "MCP_LOG_LEVEL": "server.log_level",
            "MCP_TIMEOUT": "server.timeout",
            "MCP_MAX_RETRIES": "server.max_retries"
        }

        for env_var, config_path in env_mappings.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                self._set_nested_value(config_path, env_value)
                logger.debug(f"Set {config_path} from environment variable {env_var}")

    def _set_nested_value(self, path: str, value: str):
        """Set a nested configuration value using dot notation."""
        keys = path.split('.')
        current = self._config_data

        # Navigate to the parent of the target key
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        # Set the final value with type conversion
        final_key = keys[-1]
        current[final_key] = self._convert_type(value, current.get(final_key))

    def _convert_type(self, value: str, existing_value: Any) -> Any:
        """Convert string environment variable to appropriate type."""
        if existing_value is None:
            return value

        # Convert based on existing value type
        if isinstance(existing_value, bool):
            return value.lower() in ('true', '1', 'yes', 'on')
        elif isinstance(existing_value, int):
            return int(value)
        elif isinstance(existing_value, float):
            return float(value)
        else:
            return value

    def get(self, path: str, default: Any = None) -> Any:
        """Get a configuration value using dot notation."""
        keys = path.split('.')
        current = self._config_data

        try:
            for key in keys:
                current = current[key]
            return current
        except (KeyError, TypeError):
            return default

    def set(self, path: str, value: Any):
        """Set a configuration value using dot notation."""
        keys = path.split('.')
        current = self._config_data

        # Navigate to parent
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        # Set final value
        current[keys[-1]] = value

    def validate(self) -> bool:
        """Validate that required configuration is present.

        Validates common fields (base_url, kb) plus auth-method-specific
        fields. Also enforces HTTPS for base_url and token endpoints.
        """
        # Common required fields
        required_fields = [
            "agiloft.base_url",
            "agiloft.kb"
        ]

        auth_method = self.get("agiloft.auth_method", "legacy")

        # Validate auth_method value
        if auth_method not in VALID_AUTH_METHODS:
            logger.error(
                f"Invalid auth_method '{auth_method}'. "
                f"Must be one of: {', '.join(sorted(VALID_AUTH_METHODS))}"
            )
            return False

        # Auth-method-specific required fields
        if auth_method == AUTH_OAUTH2_CLIENT_CREDENTIALS:
            required_fields.extend([
                "agiloft.oauth2.client_id",
                "agiloft.oauth2.client_secret",
                "agiloft.oauth2.token_endpoint"
            ])
        elif auth_method == AUTH_OAUTH2_AUTHORIZATION_CODE:
            required_fields.extend([
                "agiloft.oauth2.client_id",
                "agiloft.oauth2.authorization_endpoint",
                "agiloft.oauth2.token_endpoint"
            ])
        else:
            required_fields.extend([
                "agiloft.username",
                "agiloft.password"
            ])

        missing_fields = []
        for field in required_fields:
            value = self.get(field)
            if not value:
                missing_fields.append(field)

        if missing_fields:
            logger.error(
                f"Missing required configuration fields for "
                f"'{auth_method}' authentication: {missing_fields}"
            )
            return False

        # Enforce HTTPS on base_url
        base_url = self.get("agiloft.base_url", "")
        if base_url and not base_url.startswith("https://"):
            logger.error(
                "base_url must use HTTPS to protect credentials in transit. "
                f"Got: {base_url[:30]}..."
            )
            return False

        # Enforce HTTPS on token endpoint
        token_ep = self.get("agiloft.oauth2.token_endpoint", "")
        if token_ep and not token_ep.startswith("https://"):
            logger.error("oauth2.token_endpoint must use HTTPS")
            return False

        # Warn if password is loaded from config file instead of env var
        if auth_method == AUTH_LEGACY:
            password_from_env = os.getenv("AGILOFT_PASSWORD")
            if not password_from_env and self.get("agiloft.password"):
                logger.warning(
                    "Password loaded from config file. For better security, "
                    "use the AGILOFT_PASSWORD environment variable instead."
                )

        return True

    def to_dict(self) -> Dict[str, Any]:
        """Return configuration as dictionary."""
        return self._config_data.copy()

    def create_example_config(self, output_file: str = "config.json.example"):
        """Create an example configuration file."""
        example_config = self._get_default_config()

        # Add comments as a separate structure (JSON doesn't support comments)
        example_with_comments = {
            "_comments": {
                "agiloft.base_url": "Base URL for your Agiloft instance (must use HTTPS)",
                "agiloft.auth_method": "Authentication method: 'legacy', 'oauth2_client_credentials', or 'oauth2_authorization_code'",
                "agiloft.username": "Username for legacy login",
                "agiloft.password": "Password for legacy login (prefer AGILOFT_PASSWORD env var)",
                "agiloft.kb": "Knowledge Base name",
                "agiloft.language": "Language code (en, es, fr, etc.)",
                "agiloft.oauth2.client_id": "OAuth2 Client ID from Agiloft",
                "agiloft.oauth2.client_secret": "OAuth2 Client Secret (prefer AGILOFT_OAUTH2_CLIENT_SECRET env var)",
                "agiloft.oauth2.token_endpoint": "OAuth2 token endpoint URL (must use HTTPS)",
                "server.port": "Port for MCP server (not used in stdio mode)",
                "server.log_level": "Logging level (DEBUG, INFO, WARNING, ERROR)",
                "server.timeout": "HTTP request timeout in seconds",
                "server.max_retries": "Maximum number of API request retries"
            },
            **example_config
        }

        try:
            with open(output_file, 'w') as f:
                json.dump(example_with_comments, f, indent=2)
            logger.info(f"Created example configuration file: {output_file}")
        except OSError as e:
            logger.error(f"Failed to create example config: {e}")
            raise AgiloftConfigError(f"Could not write example config file: {e}")

    def __str__(self) -> str:
        """String representation (with sensitive data masked)."""
        safe_config = self.to_dict()
        # Mask sensitive information
        if 'agiloft' in safe_config:
            if 'password' in safe_config['agiloft']:
                safe_config['agiloft']['password'] = '***masked***'
            if 'oauth2' in safe_config['agiloft']:
                if 'client_secret' in safe_config['agiloft']['oauth2']:
                    safe_config['agiloft']['oauth2']['client_secret'] = '***masked***'
        return json.dumps(safe_config, indent=2)
