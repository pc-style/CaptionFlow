"""Custom exceptions for CaptionFlow."""


class CaptionFlowError(Exception):
    """Base exception for all CaptionFlow errors."""


class ConfigError(CaptionFlowError):
    """Raised when configuration is missing or invalid."""


class MediaError(CaptionFlowError):
    """Raised when media file validation or processing fails."""


class TranscriptionError(CaptionFlowError):
    """Raised when DeepGram transcription fails."""


class CaptionError(CaptionFlowError):
    """Raised when subtitle generation fails."""


class EmbedError(CaptionFlowError):
    """Raised when subtitle embedding into video fails."""
