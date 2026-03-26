from enum import Enum
from typing import Any


class ErrorCode(Enum):
    ANALYSIS_ERROR = "ANALYSIS_ERROR"
    IMAGE_READ_ERROR = "IMAGE_READ_ERROR"
    IMAGE_PROCESSING_ERROR = "IMAGE_PROCESSING_ERROR"
    CONFIG_ERROR = "CONFIG_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"


class ErrorCategory(Enum):
    IO = "io"
    PROCESSING = "processing"
    CONFIGURATION = "configuration"
    DATA = "data"
    VALIDATION = "validation"


class AnalysisError(Exception):
    code = ErrorCode.ANALYSIS_ERROR
    category = ErrorCategory.PROCESSING

    def __init__(self, message: str, image_path: str | None = None):
        self.message = message
        self.image_path = image_path
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.image_path:
            return f"{self.message} (image: {self.image_path})"
        return self.message


class ImageReadError(AnalysisError):
    code = ErrorCode.IMAGE_READ_ERROR
    category = ErrorCategory.IO


class ImageProcessingError(AnalysisError):
    code = ErrorCode.IMAGE_PROCESSING_ERROR
    category = ErrorCategory.PROCESSING


class ConfigError(Exception):
    code = ErrorCode.CONFIG_ERROR
    category = ErrorCategory.CONFIGURATION

    def __init__(self, message: str, config_path: str | None = None):
        self.message = message
        self.config_path = config_path
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.config_path:
            return f"{self.message} (config: {self.config_path})"
        return self.message


class DatabaseError(Exception):
    code = ErrorCode.DATABASE_ERROR
    category = ErrorCategory.DATA

    def __init__(self, message: str, query: str | None = None):
        self.message = message
        self.query = query
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.query:
            return f"{self.message} (query: {self.query[:100]}...)"
        return self.message


class ValidationError(Exception):
    code = ErrorCode.VALIDATION_ERROR
    category = ErrorCategory.VALIDATION

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
