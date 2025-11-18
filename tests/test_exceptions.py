"""
Unit tests for exceptions.py
"""

import pytest
from src.exceptions import (
    AgiloftError,
    AgiloftAuthError, 
    AgiloftAPIError,
    AgiloftConfigError
)


class TestExceptions:
    """Test cases for custom exception classes."""
    
    def test_agiloft_error_base(self):
        """Test base AgiloftError exception."""
        error = AgiloftError("Base error message")
        assert str(error) == "Base error message"
        assert isinstance(error, Exception)
    
    def test_agiloft_auth_error(self):
        """Test AgiloftAuthError exception."""
        error = AgiloftAuthError("Authentication failed")
        assert str(error) == "Authentication failed"
        assert isinstance(error, AgiloftError)
        assert isinstance(error, Exception)
    
    def test_agiloft_api_error_basic(self):
        """Test AgiloftAPIError with basic message."""
        error = AgiloftAPIError("API request failed")
        assert str(error) == "API request failed"
        assert error.status_code is None
        assert error.response_text is None
        assert isinstance(error, AgiloftError)
    
    def test_agiloft_api_error_with_status(self):
        """Test AgiloftAPIError with status code."""
        error = AgiloftAPIError("API request failed", status_code=404)
        assert str(error) == "API request failed"
        assert error.status_code == 404
        assert error.response_text is None
    
    def test_agiloft_api_error_with_response_text(self):
        """Test AgiloftAPIError with response text."""
        error = AgiloftAPIError("API request failed", response_text="Not found")
        assert str(error) == "API request failed"
        assert error.status_code is None
        assert error.response_text == "Not found"
    
    def test_agiloft_api_error_complete(self):
        """Test AgiloftAPIError with all parameters."""
        error = AgiloftAPIError(
            "API request failed",
            status_code=500,
            response_text="Internal server error"
        )
        assert str(error) == "API request failed"
        assert error.status_code == 500
        assert error.response_text == "Internal server error"
    
    def test_agiloft_config_error(self):
        """Test AgiloftConfigError exception."""
        error = AgiloftConfigError("Configuration is invalid")
        assert str(error) == "Configuration is invalid"
        assert isinstance(error, AgiloftError)
        assert isinstance(error, Exception)
    
    def test_exception_inheritance_chain(self):
        """Test that all custom exceptions inherit correctly."""
        # Test inheritance chain
        auth_error = AgiloftAuthError("auth error")
        api_error = AgiloftAPIError("api error")
        config_error = AgiloftConfigError("config error")
        
        # All should be instances of base classes
        assert isinstance(auth_error, AgiloftError)
        assert isinstance(api_error, AgiloftError)
        assert isinstance(config_error, AgiloftError)
        
        assert isinstance(auth_error, Exception)
        assert isinstance(api_error, Exception)
        assert isinstance(config_error, Exception)
    
    def test_exception_catching(self):
        """Test that exceptions can be caught by their base classes."""
        def raise_auth_error():
            raise AgiloftAuthError("Auth failed")
        
        def raise_api_error():
            raise AgiloftAPIError("API failed")
        
        def raise_config_error():
            raise AgiloftConfigError("Config failed")
        
        # Test catching specific exceptions
        with pytest.raises(AgiloftAuthError):
            raise_auth_error()
        
        with pytest.raises(AgiloftAPIError):
            raise_api_error()
        
        with pytest.raises(AgiloftConfigError):
            raise_config_error()
        
        # Test catching by base exception
        with pytest.raises(AgiloftError):
            raise_auth_error()
        
        with pytest.raises(AgiloftError):
            raise_api_error()
        
        with pytest.raises(AgiloftError):
            raise_config_error()