# CaptionFlow

CLI tool that transcribes video audio with [DeepGram](https://deepgram.com/) and writes **SRT** and/or **WebVTT** subtitles. Optional **soft subtitle embedding** into a new video file (via ffmpeg).

## Requirements

- **Python** 3.11+
- **[uv](https://github.com/astral-sh/uv)** (recommended) or another PEP 517 installer
- **ffmpeg** and **ffprobe** on your `PATH`
- **DeepGram API key** ([DeepGram console](https://console.deepgram.com/))

## Installation

From the repository root:

```bash
uv pip install -e .
```

The `captionflow` command is registered as a console script.

## Quick start

```bash
export DEEPGRAM_API_KEY=your_key_here

captionflow doctor
captionflow process path/to/video.mp4
```

Subtitles are written next to the source file by default (e.g. `video.srt`). See [docs/cli-reference.md](docs/cli-reference.md) for every flag and behavior.

## Documentation

| Doc | Description |
| --- | ----------- |
| [docs/cli-reference.md](docs/cli-reference.md) | Commands, options, exit codes, supported containers |
| [docs/pipeline.md](docs/pipeline.md) | End-to-end flow (probe → extract → transcribe → write/embed) |

## Examples

```bash
# Environment check (API key, ffmpeg, ffprobe)
captionflow doctor

# Single file, WebVTT only
captionflow process video.mp4 --format vtt

# SRT + VTT
captionflow process video.mp4 --format both

# Custom output directory and language
captionflow process video.mp4 -o ./subs -l es

# Batch a folder (non-recursive)
captionflow process ./videos

# All videos under a tree
captionflow process ./videos --recursive --format both

# Soft-embed subtitles (new file: `name.captioned.ext`)
captionflow process video.mp4 --embed

# Diarization (speaker labels kept in subtitles)
captionflow process interview.mp4 --diarize

# Replace source after a successful embed
captionflow process ./clips --recursive --embed --delete-original

# Overwrite existing subtitle files; stop batch on first error
captionflow process ./videos --overwrite --fail-fast --verbose
```

## Configuration

| Variable | Purpose |
| --- | --- |
| `DEEPGRAM_API_KEY` | Required. Used for all transcription requests. |

Tools are resolved from `PATH` (`ffmpeg`, `ffprobe`). Install hints are printed if something is missing.

## Development

```bash
uv pip install -e .
pytest
ruff check src tests
```

## License

MIT (see `pyproject.toml`).
