# Pipeline

This page describes what CaptionFlow does for each input video. Implementation lives under `src/captionflow/`.

## Per-file flow

1. **Probe** (`ffprobe`) — Confirm the file has at least one audio stream. Videos without audio are **skipped**.
2. **Existing output check** — Existing subtitle outputs and embedded outputs are checked separately. Skip/overwrite behavior depends on `--overwrite-subtitles`, `--overwrite-embedded`, `--overwrite`, and `--skip-existing-embedded`.
3. **Extract audio** (`ffmpeg`) — Mono WAV at 16 kHz, written to a temp file (removed unless `--keep-temp`).
4. **Transcribe** (DeepGram) — File upload via `deepgram-sdk`; `smart_format` and `utterances` are enabled; `diarize` is sent when requested. CaptionFlow wraps the API call with retry/backoff logic for rate limits and transient request failures.
5. **Build subtitles** (`deepgram-captions`) — SRT and/or WebVTT from the API response. When **diarization is off**, `[speaker …]` lines are stripped from the text.
6. **Write files** — `.srt` / `.vtt` to the chosen output directory (default: beside the video).
7. **Optional embed** (`ffmpeg`) — Muxes subtitles as a **soft** track; video and audio streams are copied (`-c:v copy -c:a copy`). Embedding uses an SRT file (generated temporarily if you only asked for VTT). `--move-captioned-to` changes the target directory for the embedded output.
8. **Optional cleanup** — After a successful embed, `--cleanup-srt` removes generated `.srt` files and `--delete-original` removes the source video. Source deletion happens only if the embedded output exists.

## Dry run

With `--dry-run`, CaptionFlow stops before media probing/transcription and returns planned actions instead:

- whether it would write or overwrite subtitles
- whether it would write or overwrite embedded outputs
- whether it would delete the original
- whether it would clean up `.srt`
- whether the embedded output would go to another directory

No files are written, deleted, or modified in dry-run mode.

## Batch mode

`discover_files` builds an ordered list of paths. `run_batch` can then:

- process sequentially with `--jobs 1`
- process multiple files in parallel with `--jobs N`
- preserve the original input order in the final summary
- write a JSON report after each completed result when `--summary-report` is set

`--fail-fast` stops submitting new work after the first failed result. With `--jobs > 1`, jobs that were already in flight may still complete.

## Resume behavior

When `--summary-report` points to an existing JSON file, CaptionFlow loads it before starting:

- previous `success` results are reused
- previous `skipped` results are reused
- previous `failed` results are retried
- files not present in the report are processed normally

This makes long-running library batches resumable without external shell state.

## Deepgram retry behavior

CaptionFlow currently treats these classes differently:

- rate limits (`429`): retried with respect for retry headers when present
- transient request / API failures (`408`, `409`, `429`, `500`, `502`, `503`, `504`, network request errors): retried with backoff
- non-retryable API errors (for example `400`): fail immediately with a clearer error type

The dependency is constrained to `deepgram-sdk>=6.0,<7` because the caption conversion logic depends on the v6 response model shape.

## Summary

After the batch, a short summary counts succeeded, failed, and skipped jobs. If a summary report path was provided, the final console output also prints the report location. The CLI exits with code **2** if any job failed.
