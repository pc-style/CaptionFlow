"""FFmpeg and FFprobe operations."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from .config import get_ffmpeg_path, get_ffprobe_path
from .constants import AUDIO_CHANNELS, AUDIO_SAMPLE_RATE, CAPTIONED_SUFFIX, MKV_FALLBACK_EXT, SUBTITLE_CODEC_MAP
from .errors import EmbedError, MediaError
from .models import MediaInfo


def probe_media(path: Path) -> MediaInfo:
    """Inspect a media file with ffprobe and return media info."""
    ffprobe = get_ffprobe_path()
    try:
        result = subprocess.run(
            [
                ffprobe, "-v", "quiet", "-print_format", "json",
                "-show_streams", "-show_format", str(path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired as e:
        raise MediaError(f"ffprobe timed out for {path.name}") from e
    except OSError as e:
        raise MediaError(f"ffprobe failed for {path.name}: {e}") from e

    if result.returncode != 0:
        raise MediaError(f"ffprobe returned error for {path.name}: {result.stderr.strip()}")

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise MediaError(f"Failed to parse ffprobe output for {path.name}") from e

    streams = data.get("streams", [])
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    fmt = data.get("format", {})

    return MediaInfo(
        path=path,
        has_audio=len(audio_streams) > 0,
        duration=float(fmt.get("duration", 0)),
        audio_codec=audio_streams[0].get("codec_name", "") if audio_streams else "",
        container=fmt.get("format_name", ""),
    )


def extract_audio(video_path: Path, *, output_path: Path | None = None) -> Path:
    """Extract audio from a video file as a normalized WAV."""
    ffmpeg = get_ffmpeg_path()

    if output_path is None:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        output_path = Path(tmp.name)
        tmp.close()

    try:
        result = subprocess.run(
            [
                ffmpeg, "-y", "-i", str(video_path),
                "-vn", "-ac", str(AUDIO_CHANNELS),
                "-ar", str(AUDIO_SAMPLE_RATE),
                "-f", "wav", str(output_path),
            ],
            capture_output=True,
            text=True,
            timeout=600,
        )
    except subprocess.TimeoutExpired as e:
        raise MediaError(f"Audio extraction timed out for {video_path.name}") from e
    except OSError as e:
        raise MediaError(f"ffmpeg failed for {video_path.name}: {e}") from e

    if result.returncode != 0:
        raise MediaError(f"Audio extraction failed for {video_path.name}: {result.stderr.strip()}")

    return output_path


def embed_subtitles(video_path: Path, subtitle_path: Path, output_path: Path | None = None) -> Path:
    """Embed a subtitle file into a video as a soft subtitle track."""
    ffmpeg = get_ffmpeg_path()
    ext = video_path.suffix.lower()
    sub_codec = SUBTITLE_CODEC_MAP.get(ext)

    if output_path is None:
        if sub_codec:
            output_path = video_path.with_stem(video_path.stem + CAPTIONED_SUFFIX)
        else:
            output_path = video_path.with_stem(video_path.stem + CAPTIONED_SUFFIX).with_suffix(MKV_FALLBACK_EXT)
            sub_codec = "srt"

    cmd = [
        ffmpeg, "-y",
        "-i", str(video_path),
        "-i", str(subtitle_path),
        "-c:v", "copy", "-c:a", "copy",
        "-c:s", sub_codec,
        "-map", "0:v", "-map", "0:a", "-map", "1:0",
        "-metadata:s:s:0", "language=eng",
        str(output_path),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired as e:
        raise EmbedError(f"Subtitle embedding timed out for {video_path.name}") from e
    except OSError as e:
        raise EmbedError(f"ffmpeg mux failed for {video_path.name}: {e}") from e

    if result.returncode != 0:
        raise EmbedError(f"Subtitle embedding failed for {video_path.name}: {result.stderr.strip()}")

    return output_path
