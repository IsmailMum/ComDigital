from typing import Any


class AppException(Exception):
    """Base exception for the application.

    All custom exceptions inherit from this so that the central exception
    handler can intercept them and return a uniform error response.
    """

    def __init__(
        self,
        status_code: int,
        error: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.error = error
        self.message = message
        self.details = details or {}
        super().__init__(message)


class InvalidCredentialsError(AppException):
    def __init__(self, message: str = "Incorrect email or password") -> None:
        super().__init__(status_code=400, error="INVALID_CREDENTIALS", message=message)


class InactiveUserError(AppException):
    def __init__(self, message: str = "Inactive user") -> None:
        super().__init__(status_code=400, error="INACTIVE_USER", message=message)


class UserAlreadyExistsError(AppException):
    def __init__(self, message: str = "The user with this email already exists in the system") -> None:
        super().__init__(status_code=400, error="USER_ALREADY_EXISTS", message=message)


class PermissionDeniedError(AppException):
    def __init__(self, message: str = "Not enough permissions") -> None:
        super().__init__(status_code=403, error="PERMISSION_DENIED", message=message)


class CredentialsValidationError(AppException):
    def __init__(self, message: str = "Could not validate credentials") -> None:
        super().__init__(status_code=403, error="CREDENTIALS_VALIDATION_ERROR", message=message)


class NotFoundError(AppException):
    def __init__(self, message: str = "Resource not found", error: str = "NOT_FOUND") -> None:
        super().__init__(status_code=404, error=error, message=message)


class ItemNotFoundError(NotFoundError):
    def __init__(self, message: str = "Item not found") -> None:
        super().__init__(message=message, error="ITEM_NOT_FOUND")


class UserNotFoundError(NotFoundError):
    def __init__(self, message: str = "User not found") -> None:
        super().__init__(message=message, error="USER_NOT_FOUND")
