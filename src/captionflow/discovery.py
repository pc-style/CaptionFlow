"""File discovery for CaptionFlow."""

from pathlib import Path

from .constants import is_supported_video
from .errors import MediaError


def discover_files(path: Path, *, recursive: bool = False) -> list[Path]:
    """Discover video files from a path (file or directory)."""
    if path.is_file():
        if not is_supported_video(path):
            raise MediaError(f"Unsupported file type: {path.suffix}")
        return [path]

    if path.is_dir():
        pattern = "**/*" if recursive else "*"
        files = sorted(
            f for f in path.glob(pattern)
            if f.is_file() and not f.name.startswith(".") and is_supported_video(f)
        )
        return files

    raise MediaError(f"Path does not exist or is not a file/directory: {path}")
