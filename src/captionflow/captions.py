"""Subtitle generation from DeepGram responses."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .errors import CaptionError
from .models import SubtitleFormat


def _strip_speaker_labels(content: str) -> str:
    """Remove [speaker ...] lines from subtitle content."""
    import re
    return re.sub(r"^\[speaker[^\]]*\]\n", "", content, flags=re.MULTILINE)


def generate_captions(response: Any, fmt: SubtitleFormat, *, diarize: bool = False) -> dict[str, str]:
    """Generate subtitle content from a DeepGram response.

    Returns a dict mapping format name ("srt", "vtt") to content string.
    """
    try:
        from deepgram_captions import DeepgramConverter, srt, webvtt
    except ImportError as e:
        raise CaptionError("deepgram-captions is not installed") from e

    try:
        # SDK v6 returns Pydantic models; deepgram-captions expects a dict
        if hasattr(response, "model_dump"):
            response_data = response.model_dump()
        elif hasattr(response, "to_json"):
            response_data = response
        else:
            response_data = response
        converter = DeepgramConverter(response_data)
    except Exception as e:
        raise CaptionError(f"Failed to convert DeepGram response: {e}") from e

    results: dict[str, str] = {}

    if fmt in (SubtitleFormat.SRT, SubtitleFormat.BOTH):
        try:
            content = srt(converter)
            if not diarize:
                content = _strip_speaker_labels(content)
            results["srt"] = content
        except Exception as e:
            raise CaptionError(f"SRT generation failed: {e}") from e

    if fmt in (SubtitleFormat.VTT, SubtitleFormat.BOTH):
        try:
            content = webvtt(converter)
            if not diarize:
                content = _strip_speaker_labels(content)
            results["vtt"] = content
        except Exception as e:
            raise CaptionError(f"WebVTT generation failed: {e}") from e

    return results


def write_captions(
    captions: dict[str, str],
    base_path: Path,
    output_dir: Path | None = None,
) -> list[Path]:
    """Write caption content to files and return the written paths."""
    written: list[Path] = []

    for ext, content in captions.items():
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            out_path = output_dir / f"{base_path.stem}.{ext}"
        else:
            out_path = base_path.with_suffix(f".{ext}")

        out_path.write_text(content, encoding="utf-8")
        written.append(out_path)

    return written
