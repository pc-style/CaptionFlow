"""Constants and defaults for CaptionFlow."""

from pathlib import Path

SUPPORTED_VIDEO_EXTENSIONS: set[str] = {
    ".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv", ".m4v", ".ts", ".mts",
}

DEFAULT_MODEL = "nova-3"
DEFAULT_LANGUAGE = "en"
DEFAULT_FORMAT = "srt"

AUDIO_SAMPLE_RATE = 16000
AUDIO_CHANNELS = 1

CAPTIONED_SUFFIX = ".captioned"

SUBTITLE_CODEC_MAP: dict[str, str] = {
    ".mp4": "mov_text",
    ".mov": "mov_text",
    ".m4v": "mov_text",
    ".mkv": "srt",
    ".webm": "webvtt",
}

MKV_FALLBACK_EXT = ".mkv"


def is_supported_video(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS
