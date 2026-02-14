"""
Unit tests for config.py
"""

import json
import os
import tempfile
import pytest
from pathlib import Path
from src.config import Config
from src.exceptions import AgiloftConfigError


class TestConfig:
    """Test cases for Config class."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = Config("nonexistent.json")  # File doesn't exist, should use defaults

        # Defaults are now empty (no hardcoded production credentials)
        assert config.get('agiloft.base_url') == ""
        assert config.get('agiloft.username') == ""
        assert config.get('agiloft.kb') == ""
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
            # Should merge with defaults (kb defaults to empty)
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
    
    def test_validation_success(self):
        """Test successful configuration validation."""
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
    
    def test_validation_failure(self):
        """Test configuration validation failure."""
        config = Config("nonexistent.json")
        # Default config has empty password
        assert config.validate() is False
    
    def test_to_dict(self):
        """Test converting configuration to dictionary."""
        config = Config("nonexistent.json")
        config_dict = config.to_dict()
        
        assert isinstance(config_dict, dict)
        assert 'agiloft' in config_dict
        assert 'server' in config_dict
    
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
    
    def test_string_representation(self):
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