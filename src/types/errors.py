from typing import Any


class AnalysisError(Exception):
    """Base exception for all analysis errors."""

    # TODO: Add stable error codes or categories here so the CLI and future
    # APIs can map failures to user-facing guidance without parsing messages.

    def __init__(self, message: str, image_path: str | None = None):
        self.message = message
        self.image_path = image_path
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.image_path:
            return f"{self.message} (image: {self.image_path})"
        return self.message


class ImageReadError(AnalysisError):
    """Raised when an image cannot be read or opened."""

    pass


class ImageProcessingError(AnalysisError):
    """Raised when image processing fails."""

    pass


class ConfigError(Exception):
    """Raised when configuration is invalid or missing."""

    def __init__(self, message: str, config_path: str | None = None):
        self.message = message
        self.config_path = config_path
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.config_path:
            return f"{self.message} (config: {self.config_path})"
        return self.message


class DatabaseError(Exception):
    """Raised when database operations fail."""

    def __init__(self, message: str, query: str | None = None):
        self.message = message
        self.query = query
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.query:
            return f"{self.message} (query: {self.query[:100]}...)"
        return self.message


class ValidationError(Exception):
    """Raised when validation fails."""

    def __init__(self, message: str, field: str | None = None, value: Any = None):
        self.message = message
        self.field = field
        self.value = value
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.field and self.value is not None:
            return f"{self.message} (field: {self.field}, value: {self.value})"
        elif self.field:
            return f"{self.message} (field: {self.field})"
        return self.message
