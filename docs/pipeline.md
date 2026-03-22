# Pipeline

This page describes what CaptionFlow does for each input video. Implementation lives under `src/captionflow/`.

## Per-file flow

1. **Probe** (`ffprobe`) — Confirm the file has at least one audio stream. Videos without audio are **skipped**.
2. **Existing output check** — Unless `--overwrite`, if the expected subtitle path already exists, the job is **skipped** (see [CLI reference](cli-reference.md) for `both` format).
3. **Extract audio** (`ffmpeg`) — Mono WAV at 16 kHz, written to a temp file (removed unless `--keep-temp`).
4. **Transcribe** (DeepGram) — File upload via `deepgram-sdk`; `smart_format` and `utterances` are enabled; `diarize` is sent when requested. Timeout and retries are set in code (`deepgram_client.py`).
5. **Build subtitles** (`deepgram-captions`) — SRT and/or WebVTT from the API response. When **diarization is off**, `[speaker …]` lines are stripped from the text.
6. **Write files** — `.srt` / `.vtt` to the chosen output directory (default: beside the video).
7. **Optional embed** (`ffmpeg`) — Muxes subtitles as a **soft** track; video and audio streams are copied (`-c:v copy -c:a copy`). Embedding uses an SRT file (generated temporarily if you only asked for VTT).

## Batch mode

`discover_files` builds an ordered list of paths. `run_batch` processes them **sequentially** with a Rich progress bar. `--fail-fast` stops the loop after the first **failed** result; already processed files stay in the summary.

## Summary

After the batch, a short summary counts succeeded, failed, and skipped jobs. The CLI exits with code **2** if any job failed.
