"""Subtitle generation from DeepGram responses."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .errors import CaptionError
from .models import SubtitleFormat


def generate_captions(response: Any, fmt: SubtitleFormat) -> dict[str, str]:
    """Generate subtitle content from a DeepGram response.

    Returns a dict mapping format name ("srt", "vtt") to content string.
    """
    try:
        from deepgram_captions import DeepgramConverter, srt, webvtt
    except ImportError as e:
        raise CaptionError("deepgram-captions is not installed") from e

    try:
        converter = DeepgramConverter(response)
    except Exception as e:
        raise CaptionError(f"Failed to convert DeepGram response: {e}") from e

    results: dict[str, str] = {}

    if fmt in (SubtitleFormat.SRT, SubtitleFormat.BOTH):
        try:
            results["srt"] = srt(converter)
        except Exception as e:
            raise CaptionError(f"SRT generation failed: {e}") from e

    if fmt in (SubtitleFormat.VTT, SubtitleFormat.BOTH):
        try:
            results["vtt"] = webvtt(converter)
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
