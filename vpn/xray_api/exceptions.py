"""
Custom exceptions for Xray Manager.
"""


class XrayError(Exception):
    """Base exception for all Xray-related errors."""
    pass


class APIError(XrayError):
    """Error occurred during API communication."""
    pass


class InboundNotFoundError(XrayError):
    """Inbound with specified tag not found."""
    pass


class UserNotFoundError(XrayError):
    """User with specified email not found."""
    pass


class ConfigurationError(XrayError):
    """Error in Xray configuration."""
    pass


class CertificateError(XrayError):
    """Error related to TLS certificates."""
    pass