"""Exceptions for the Bosch eBike Connect client."""


class EBikeConnectError(Exception):
    """Base exception for Bosch eBike Connect client errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class AuthenticationError(EBikeConnectError):
    """Exception raised when authentication fails."""


class APIError(EBikeConnectError):
    """Exception raised when API request fails."""
