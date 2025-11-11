"""Exceptions for the Bosch eBike Connect client."""


class EBikeConnectError(Exception):
    """Base exception for Bosch eBike Connect client errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        """Initialize the exception.

        Args:
            message: Error message
            status_code: HTTP status code if applicable
        """
        super().__init__(message)
        self.status_code = status_code


class AuthenticationError(EBikeConnectError):
    """Exception raised when authentication fails."""

    pass


class APIError(EBikeConnectError):
    """Exception raised when API request fails."""

    pass
