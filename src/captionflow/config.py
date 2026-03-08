"""Configuration management for CaptionFlow."""

import os
import shutil
import subprocess

from .errors import ConfigError


def get_api_key() -> str:
    key = os.environ.get("DEEPGRAM_API_KEY", "").strip()
    if not key:
        raise ConfigError(
            "DEEPGRAM_API_KEY is not set. Export it and retry:\n"
            "  export DEEPGRAM_API_KEY=your_key_here"
        )
    return key


def get_ffmpeg_path() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise ConfigError(
            "ffmpeg not found. Install it:\n"
            "  brew install ffmpeg  (macOS)\n"
            "  sudo apt install ffmpeg  (Linux)"
        )
    return path


def get_ffprobe_path() -> str:
    path = shutil.which("ffprobe")
    if not path:
        raise ConfigError(
            "ffprobe not found. It is usually bundled with ffmpeg.\n"
            "  brew install ffmpeg  (macOS)\n"
            "  sudo apt install ffmpeg  (Linux)"
        )
    return path


def get_tool_version(tool: str) -> str | None:
    path = shutil.which(tool)
    if not path:
        return None
    try:
        result = subprocess.run(
            [path, "-version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        first_line = result.stdout.strip().split("\n")[0]
        return first_line
    except (subprocess.TimeoutExpired, OSError):
        return None
