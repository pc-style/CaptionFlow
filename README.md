# CaptionFlow

CLI tool that transcribes video audio with DeepGram and generates SRT/WebVTT subtitle files.

## Installation

```bash
uv pip install -e .
```

## Usage

```bash
# Check environment
captionflow doctor

# Transcribe a single video
captionflow process video.mp4

# Batch process a directory
captionflow process ./videos --recursive --format both

# Embed subtitles into video
captionflow process video.mp4 --embed --diarize
```

## Configuration

Set your DeepGram API key:

```bash
export DEEPGRAM_API_KEY=your_key_here
```

Requires `ffmpeg` and `ffprobe` installed on your system.
