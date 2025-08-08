"""Exceptions for xray-api library"""


class XrayAPIError(Exception):
    """Base exception for all xray-api errors"""
    pass


class XrayConnectionError(XrayAPIError):
    """Connection to Xray API server failed"""
    pass


class XrayCommandError(XrayAPIError):
    """Xray command execution failed"""
    pass


class XrayConfigError(XrayAPIError):
    """Invalid configuration"""
    pass


class XrayNotFoundError(XrayAPIError):
    """Resource not found"""
    pass


class XrayValidationError(XrayAPIError):
    """Validation error"""
    pass