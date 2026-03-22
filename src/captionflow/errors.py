"""Custom exceptions for CaptionFlow."""


class CaptionFlowError(Exception):
    """Base exception for all CaptionFlow errors."""


class ConfigError(CaptionFlowError):
    """Raised when configuration is missing or invalid."""


class MediaError(CaptionFlowError):
    """Raised when media file validation or processing fails."""


class TranscriptionError(CaptionFlowError):
    """Raised when DeepGram transcription fails."""


class DeepgramApiError(TranscriptionError):
    """Raised when DeepGram returns a non-retryable API error."""


class DeepgramRateLimitError(TranscriptionError):
    """Raised when DeepGram rate limits the request."""


class DeepgramRetryableError(TranscriptionError):
    """Raised when DeepGram fails with a retryable transient error."""


class CaptionError(CaptionFlowError):
    """Raised when subtitle generation fails."""


class EmbedError(CaptionFlowError):
    """Raised when subtitle embedding into video fails."""
