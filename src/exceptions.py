"""
Agiloft MCP Server Exceptions

Custom exception classes for better error handling and debugging.
"""

from typing import Optional


class AgiloftError(Exception):
    """Base exception for Agiloft-related errors."""
    pass


class AgiloftAuthError(AgiloftError):
    """Authentication-related errors."""
    pass


class AgiloftAPIError(AgiloftError):
    """API request/response errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, response_text: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class AgiloftConfigError(AgiloftError):
    """Configuration-related errors."""
    pass