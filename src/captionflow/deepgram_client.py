"""DeepGram API wrapper."""

from __future__ import annotations

from typing import Any

from .config import get_api_key
from .errors import TranscriptionError


def transcribe_audio(
    audio_bytes: bytes,
    *,
    model: str = "nova-3",
    language: str | None = None,
    diarize: bool = False,
) -> Any:
    """Transcribe audio bytes using DeepGram and return the raw response."""
    try:
        from deepgram import DeepgramClient
    except ImportError as e:
        raise TranscriptionError("deepgram-sdk is not installed") from e

    api_key = get_api_key()
    client = DeepgramClient(api_key=api_key)

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

    try:
        response = client.listen.v1.media.transcribe_file(
            **kwargs,
            request_options={"timeout_in_seconds": 300, "max_retries": 2},
        )
    except Exception as e:
        raise TranscriptionError(f"DeepGram API error: {e}") from e

    return response
