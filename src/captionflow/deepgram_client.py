"""DeepGram API wrapper."""

from __future__ import annotations

import email.utils
import time
from collections.abc import Mapping
from typing import Any

from .config import get_api_key
from .errors import DeepgramApiError, DeepgramRateLimitError, DeepgramRetryableError, TranscriptionError

_DEFAULT_TIMEOUT_SECONDS = 300
_DEFAULT_MAX_ATTEMPTS = 3
_INITIAL_RETRY_DELAY_SECONDS = 1.0
_MAX_RETRY_DELAY_SECONDS = 60.0
_RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}


def _create_client(api_key: str) -> Any:
    from deepgram import DeepgramClient

    return DeepgramClient(api_key=api_key)


def _get_header_value(headers: Any, name: str) -> str | None:
    if headers is None:
        return None

    getter = getattr(headers, "get", None)
    if callable(getter):
        value = getter(name)
        return value if isinstance(value, str) else value

    if isinstance(headers, Mapping):
        for key, value in headers.items():
            if str(key).lower() == name.lower():
                return value if isinstance(value, str) else value

    return None


def _parse_retry_delay(headers: Any) -> float | None:
    retry_after_ms = _get_header_value(headers, "retry-after-ms")
    if retry_after_ms is not None:
        try:
            delay = int(retry_after_ms) / 1000
            return delay if delay > 0 else None
        except (TypeError, ValueError):
            pass

    retry_after = _get_header_value(headers, "retry-after")
    if retry_after is not None:
        try:
            delay = float(retry_after)
            return delay if delay > 0 else None
        except (TypeError, ValueError):
            retry_date_tuple = email.utils.parsedate_tz(retry_after)
            if retry_date_tuple is not None:
                retry_date = email.utils.mktime_tz(retry_date_tuple)
                delay = retry_date - time.time()
                return delay if delay > 0 else None

    reset_at = _get_header_value(headers, "x-ratelimit-reset")
    if reset_at is not None:
        try:
            delay = float(reset_at) - time.time()
            return delay if delay > 0 else None
        except (TypeError, ValueError):
            pass

    return None


def _retry_delay(attempt: int, headers: Any | None = None) -> float:
    header_delay = _parse_retry_delay(headers)
    if header_delay is not None:
        return min(header_delay, _MAX_RETRY_DELAY_SECONDS)

    delay = _INITIAL_RETRY_DELAY_SECONDS * (2**attempt)
    return min(delay, _MAX_RETRY_DELAY_SECONDS)


def _build_error_message(prefix: str, exc: Exception, attempts: int) -> str:
    return f"{prefix} after {attempts} attempt(s): {exc}"


def _classify_failure(exc: Exception) -> tuple[type[TranscriptionError], bool, Any]:
    try:
        from deepgram.core.api_error import ApiError
    except ImportError:
        ApiError = None  # type: ignore[assignment]

    if ApiError is not None and isinstance(exc, ApiError):
        status_code = getattr(exc, "status_code", None)
        headers = getattr(exc, "headers", None)
        if status_code == 429:
            return DeepgramRateLimitError, True, headers
        if status_code in _RETRYABLE_STATUS_CODES:
            return DeepgramRetryableError, True, headers
        return DeepgramApiError, False, headers

    try:
        import httpx
    except ImportError:
        httpx = None  # type: ignore[assignment]

    if httpx is not None and isinstance(exc, httpx.RequestError):
        return DeepgramRetryableError, True, None

    return DeepgramApiError, False, None


def transcribe_audio(
    audio_bytes: bytes,
    *,
    model: str = "nova-3",
    language: str | None = None,
    diarize: bool = False,
    max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
    timeout_in_seconds: int = _DEFAULT_TIMEOUT_SECONDS,
) -> Any:
    """Transcribe audio bytes using DeepGram and return the raw response."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    try:
        client = _create_client(get_api_key())
    except ImportError as e:
        raise TranscriptionError("deepgram-sdk is not installed") from e

    kwargs: dict[str, Any] = {
        "request": audio_bytes,
        "model": model,
        "smart_format": True,
        "utterances": True,
    }

    if language:
        kwargs["language"] = language

    if diarize:
        kwargs["diarize"] = True

    request_options = {"timeout_in_seconds": timeout_in_seconds, "max_retries": 0}

    last_error: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return client.listen.v1.media.transcribe_file(**kwargs, request_options=request_options)
        except Exception as exc:
            last_error = exc
            error_type, retryable, context = _classify_failure(exc)
            if not retryable or attempt + 1 >= max_attempts:
                if error_type is DeepgramRateLimitError:
                    raise error_type(
                        _build_error_message("DeepGram rate limit reached", exc, attempt + 1)
                    ) from exc
                if error_type is DeepgramRetryableError:
                    raise error_type(
                        _build_error_message("DeepGram transient transcription failure", exc, attempt + 1)
                    ) from exc
                raise error_type(_build_error_message("DeepGram API error", exc, attempt + 1)) from exc

            time.sleep(_retry_delay(attempt, context))

    if last_error is not None:
        raise TranscriptionError(f"DeepGram transcription failed: {last_error}") from last_error

    raise TranscriptionError("DeepGram transcription failed")
