"""
Configuration Manager

Handles configuration loading from multiple sources with fallback priority:
1. Environment variables (highest priority)
2. Configuration file (config.json)
3. Default values (lowest priority)

Supports both development and production deployment scenarios.
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
                "base_url": "https://agiloft160371.saas.agiloft.com/ewws/alrest/Agiloft Demo70",
                "username": "admin",
                "password": "",  # Must be provided via config file or env var
                "kb": "Agiloft Demo70",
                "language": "en"
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
        # Environment variable mapping
        env_mappings = {
            "AGILOFT_BASE_URL": "agiloft.base_url",
            "AGILOFT_USERNAME": "agiloft.username", 
            "AGILOFT_PASSWORD": "agiloft.password",
            "AGILOFT_KB": "agiloft.kb",
            "AGILOFT_LANGUAGE": "agiloft.language",
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
        """Validate that required configuration is present."""
        required_fields = [
            "agiloft.base_url",
            "agiloft.username", 
            "agiloft.password",
            "agiloft.kb"
        ]
        
        missing_fields = []
        for field in required_fields:
            value = self.get(field)
            if not value:
                missing_fields.append(field)
                
        if missing_fields:
            logger.error(f"Missing required configuration fields: {missing_fields}")
            return False
            
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
                "agiloft.base_url": "Base URL for your Agiloft instance",
                "agiloft.username": "Username for Agiloft login",
                "agiloft.password": "Password for Agiloft login (consider using environment variable AGILOFT_PASSWORD)",
                "agiloft.kb": "Knowledge Base name",
                "agiloft.language": "Language code (en, es, fr, etc.)",
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
        if 'agiloft' in safe_config and 'password' in safe_config['agiloft']:
            safe_config['agiloft']['password'] = '***masked***'
        return json.dumps(safe_config, indent=2)