"""
Unit tests for config.py
"""

import json
import os
import tempfile
import pytest
from pathlib import Path
from src.config import Config, AUTH_LEGACY, AUTH_OAUTH2_CLIENT_CREDENTIALS, VALID_AUTH_METHODS
from src.exceptions import AgiloftConfigError


class TestConfig:
    """Test cases for Config class."""

    def test_default_config(self):
        """Test default configuration values."""
        config = Config("nonexistent.json")

        assert config.get('agiloft.base_url') == ""
        assert config.get('agiloft.username') == ""
        assert config.get('agiloft.kb') == ""
        assert config.get('agiloft.auth_method') == "legacy"
        assert config.get('agiloft.oauth2.client_id') == ""
        assert config.get('agiloft.oauth2.client_secret') == ""
        assert config.get('agiloft.oauth2.token_endpoint') == ""
        assert config.get('agiloft.oauth2.redirect_uri') == "http://localhost:8080/callback"
        assert config.get('server.port') == 8000
        assert config.get('server.log_level') == "INFO"

    def test_config_file_loading(self):
        """Test loading configuration from JSON file."""
        test_config = {
            "agiloft": {
                "base_url": "https://test.example.com",
                "username": "testuser",
                "password": "testpass"
            },
            "server": {
                "port": 9000
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_config, f)
            config_path = f.name

        try:
            config = Config(config_path)
            assert config.get('agiloft.base_url') == "https://test.example.com"
            assert config.get('agiloft.username') == "testuser"
            assert config.get('server.port') == 9000
            assert config.get('agiloft.kb') == ""
        finally:
            os.unlink(config_path)

    def test_invalid_json_file(self):
        """Test handling of invalid JSON configuration file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{ invalid json }")
            config_path = f.name

        try:
            with pytest.raises(AgiloftConfigError, match="Invalid configuration file"):
                Config(config_path)
        finally:
            os.unlink(config_path)

    def test_environment_variables(self, monkeypatch):
        """Test environment variable override."""
        monkeypatch.setenv("AGILOFT_BASE_URL", "https://env.example.com")
        monkeypatch.setenv("AGILOFT_USERNAME", "envuser")
        monkeypatch.setenv("MCP_SERVER_PORT", "7000")
        monkeypatch.setenv("MCP_LOG_LEVEL", "DEBUG")

        config = Config("nonexistent.json")

        assert config.get('agiloft.base_url') == "https://env.example.com"
        assert config.get('agiloft.username') == "envuser"
        assert config.get('server.port') == 7000
        assert config.get('server.log_level') == "DEBUG"

    def test_oauth2_environment_variables(self, monkeypatch):
        """Test OAuth2 environment variable override."""
        monkeypatch.setenv("AGILOFT_AUTH_METHOD", "oauth2_client_credentials")
        monkeypatch.setenv("AGILOFT_OAUTH2_CLIENT_ID", "my-client-id")
        monkeypatch.setenv("AGILOFT_OAUTH2_CLIENT_SECRET", "my-secret")
        monkeypatch.setenv("AGILOFT_OAUTH2_TOKEN_ENDPOINT", "https://example.com/oauth/token")
        monkeypatch.setenv("AGILOFT_OAUTH2_SCOPE", "permissions_for:213")

        config = Config("nonexistent.json")

        assert config.get('agiloft.auth_method') == "oauth2_client_credentials"
        assert config.get('agiloft.oauth2.client_id') == "my-client-id"
        assert config.get('agiloft.oauth2.client_secret') == "my-secret"
        assert config.get('agiloft.oauth2.token_endpoint') == "https://example.com/oauth/token"
        assert config.get('agiloft.oauth2.scope') == "permissions_for:213"

    def test_dot_notation_get(self):
        """Test getting values using dot notation."""
        config = Config("nonexistent.json")

        assert config.get('agiloft.base_url') is not None
        assert config.get('nonexistent.path') is None
        assert config.get('nonexistent.path', 'default') == 'default'

    def test_dot_notation_set(self):
        """Test setting values using dot notation."""
        config = Config("nonexistent.json")

        config.set('new.nested.value', 'test')
        assert config.get('new.nested.value') == 'test'

    def test_type_conversion(self, monkeypatch):
        """Test type conversion from environment variables."""
        monkeypatch.setenv("MCP_SERVER_PORT", "8080")
        monkeypatch.setenv("MCP_MAX_RETRIES", "5")

        config = Config("nonexistent.json")

        assert config.get('server.port') == 8080
        assert isinstance(config.get('server.port'), int)
        assert config.get('server.max_retries') == 5

    def test_validation_legacy_success(self):
        """Test successful validation for legacy auth."""
        test_config = {
            "agiloft": {
                "base_url": "https://test.example.com",
                "username": "testuser",
                "password": "testpass",
                "kb": "TestKB"
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_config, f)
            config_path = f.name

        try:
            config = Config(config_path)
            assert config.validate() is True
        finally:
            os.unlink(config_path)

    def test_validation_legacy_failure(self):
        """Test validation failure for legacy auth (missing password)."""
        config = Config("nonexistent.json")
        assert config.validate() is False

    def test_validation_oauth2_client_credentials_success(self):
        """Test successful validation for OAuth2 client_credentials."""
        test_config = {
            "agiloft": {
                "base_url": "https://test.example.com",
                "kb": "TestKB",
                "auth_method": "oauth2_client_credentials",
                "oauth2": {
                    "client_id": "my-client",
                    "client_secret": "my-secret",
                    "token_endpoint": "https://test.example.com/oauth/token"
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_config, f)
            config_path = f.name

        try:
            config = Config(config_path)
            assert config.validate() is True
        finally:
            os.unlink(config_path)

    def test_validation_oauth2_missing_client_id(self):
        """Test validation failure for OAuth2 with missing client_id."""
        test_config = {
            "agiloft": {
                "base_url": "https://test.example.com",
                "kb": "TestKB",
                "auth_method": "oauth2_client_credentials",
                "oauth2": {
                    "client_secret": "my-secret",
                    "token_endpoint": "https://test.example.com/oauth/token"
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_config, f)
            config_path = f.name

        try:
            config = Config(config_path)
            assert config.validate() is False
        finally:
            os.unlink(config_path)

    def test_validation_invalid_auth_method(self):
        """Test validation failure for unknown auth method."""
        test_config = {
            "agiloft": {
                "base_url": "https://test.example.com",
                "kb": "TestKB",
                "auth_method": "invalid_method"
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_config, f)
            config_path = f.name

        try:
            config = Config(config_path)
            assert config.validate() is False
        finally:
            os.unlink(config_path)

    def test_validation_enforces_https_base_url(self):
        """Test that base_url must use HTTPS."""
        test_config = {
            "agiloft": {
                "base_url": "http://insecure.example.com",
                "username": "testuser",
                "password": "testpass",
                "kb": "TestKB"
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_config, f)
            config_path = f.name

        try:
            config = Config(config_path)
            assert config.validate() is False
        finally:
            os.unlink(config_path)

    def test_validation_enforces_https_token_endpoint(self):
        """Test that OAuth2 token_endpoint must use HTTPS."""
        test_config = {
            "agiloft": {
                "base_url": "https://test.example.com",
                "kb": "TestKB",
                "auth_method": "oauth2_client_credentials",
                "oauth2": {
                    "client_id": "my-client",
                    "client_secret": "my-secret",
                    "token_endpoint": "http://insecure.example.com/oauth/token"
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_config, f)
            config_path = f.name

        try:
            config = Config(config_path)
            assert config.validate() is False
        finally:
            os.unlink(config_path)

    def test_to_dict(self):
        """Test converting configuration to dictionary."""
        config = Config("nonexistent.json")
        config_dict = config.to_dict()

        assert isinstance(config_dict, dict)
        assert 'agiloft' in config_dict
        assert 'server' in config_dict
        assert 'oauth2' in config_dict['agiloft']

    def test_create_example_config(self):
        """Test creating example configuration file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            example_path = os.path.join(temp_dir, "example.json")
            config = Config("nonexistent.json")

            config.create_example_config(example_path)

            assert os.path.exists(example_path)

            with open(example_path, 'r') as f:
                example_config = json.load(f)
                assert '_comments' in example_config
                assert 'agiloft' in example_config
                assert 'server' in example_config

    def test_string_representation_masks_password(self):
        """Test string representation with masked password."""
        test_config = {
            "agiloft": {
                "password": "secret123"
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_config, f)
            config_path = f.name

        try:
            config = Config(config_path)
            config_str = str(config)
            assert "secret123" not in config_str
            assert "***masked***" in config_str
        finally:
            os.unlink(config_path)

    def test_string_representation_masks_client_secret(self):
        """Test string representation with masked OAuth2 client_secret."""
        test_config = {
            "agiloft": {
                "oauth2": {
                    "client_secret": "super-secret-key"
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_config, f)
            config_path = f.name

        try:
            config = Config(config_path)
            config_str = str(config)
            assert "super-secret-key" not in config_str
            assert "***masked***" in config_str
        finally:
            os.unlink(config_path)

    def test_oauth2_config_from_file(self):
        """Test loading OAuth2 config from JSON file."""
        test_config = {
            "agiloft": {
                "base_url": "https://instance.agiloft.com/ewws/alrest/KB",
                "kb": "KB",
                "auth_method": "oauth2_client_credentials",
                "oauth2": {
                    "client_id": "file-client-id",
                    "client_secret": "file-secret",
                    "token_endpoint": "https://instance.agiloft.com/oauth/token",
                    "scope": "permissions_for:100"
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_config, f)
            config_path = f.name

        try:
            config = Config(config_path)
            assert config.get('agiloft.auth_method') == "oauth2_client_credentials"
            assert config.get('agiloft.oauth2.client_id') == "file-client-id"
            assert config.get('agiloft.oauth2.scope') == "permissions_for:100"
        finally:
            os.unlink(config_path)

    def test_valid_auth_methods_constant(self):
        """Test that VALID_AUTH_METHODS contains expected values."""
        assert "legacy" in VALID_AUTH_METHODS
        assert "oauth2_client_credentials" in VALID_AUTH_METHODS
        assert "oauth2_authorization_code" in VALID_AUTH_METHODS
        assert len(VALID_AUTH_METHODS) == 3
