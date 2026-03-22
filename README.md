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

Subtitles are written next to the source file by default (e.g. `video.srt`). For the full option surface, resume/reporting workflow, and overwrite behavior, see [docs/cli-reference.md](docs/cli-reference.md) and [docs/pipeline.md](docs/pipeline.md).

## Documentation

| Doc | Description |
| --- | ----------- |
| [docs/cli-reference.md](docs/cli-reference.md) | Commands, options, overwrite modes, exit codes, supported containers |
| [docs/pipeline.md](docs/pipeline.md) | End-to-end flow, resume/report JSON, retries, dry-run, and parallel jobs |

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

# Preview a large batch without writing anything
captionflow process ./videos --recursive --embed --dry-run --skip-existing-embedded

# Control reruns, output placement, cleanup, and reporting
captionflow process ./videos --recursive --embed --skip-existing-embedded --cleanup-srt --move-captioned-to ./captioned --jobs 4 --summary-report run.json

# Fine-grained overwrite control
captionflow process ./videos --overwrite-subtitles --overwrite-embedded --fail-fast --verbose

# Resume a long run using the same summary report
captionflow process ./videos --recursive --embed --summary-report run.json --jobs 4
```

## Recommended Batch Workflow

For long media libraries:

```bash
captionflow process ./videos \
  --recursive \
  --embed \
  --skip-existing-embedded \
  --cleanup-srt \
  --summary-report ./captionflow-run.json \
  --jobs 4
```

If the run is interrupted, rerun the same command with the same `--summary-report` path. Previously successful and skipped files are reused from the report; prior failures are retried.

## Configuration

| Variable | Purpose |
| --- | --- |
| `DEEPGRAM_API_KEY` | Required. Used for all transcription requests. |

Tools are resolved from `PATH` (`ffmpeg`, `ffprobe`). Install hints are printed if something is missing.

## Development

```bash
uv pip install -e .
uv run --with pytest pytest -q
ruff check src tests
```

## License

MIT (see `pyproject.toml`).
