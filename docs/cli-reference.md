# CLI reference

## Global

```text
captionflow --version
captionflow --help
```

## `captionflow doctor`

Verifies:

- `DEEPGRAM_API_KEY` is set (value is masked in the table)
- `ffmpeg` and `ffprobe` are on `PATH` (first line of `-version` shown)

**Exit codes**

| Code | Meaning |
| --- | --- |
| 0 | All checks passed |
| 1 | One or more checks failed |

## `captionflow process`

```text
captionflow process [OPTIONS] INPUT_PATH
```

`INPUT_PATH` must exist. It can be a **single video file** or a **directory** of videos.

### Options

| Option | Default | Description |
| --- | --- | --- |
| `-o`, `--output-dir` | *(none)* | Directory for subtitle files. Default: same folder as each source video. |
| `-f`, `--format` | `srt` | `srt`, `vtt`, or `both`. |
| `-l`, `--language` | `en` | DeepGram language code (e.g. `en`, `es`, `fr`). |
| `--embed` / `--no-embed` | `no-embed` | After subtitles are written, mux a **soft** subtitle track into a new video. |
| `--delete-original` | off | After a successful embed, delete the **source** video. **Requires** `--embed`. |
| `--diarize` / `--no-diarize` | `no-diarize` | Request speaker diarization; speaker lines are kept in subtitles when enabled. |
| `-r`, `--recursive` | off | When `INPUT_PATH` is a directory, include subfolders. |
| `--model` | `nova-3` | DeepGram model name passed to the API. |
| `--overwrite` | off | Regenerate even if the expected subtitle file already exists. |
| `--keep-temp` | off | Keep temporary extracted audio (normally deleted). |
| `--fail-fast` | off | In batch mode, stop after the first **failed** job (skipped jobs do not stop the batch). |
| `-v`, `--verbose` | off | Print per-step messages. |

### Supported video extensions

Files must have one of these suffixes (case-insensitive):

`.mp4`, `.mkv`, `.avi`, `.mov`, `.webm`, `.flv`, `.wmv`, `.m4v`, `.ts`, `.mts`

Hidden files (names starting with `.`) are ignored when scanning directories.

### Output files

**Subtitles**

- With no `--output-dir`: `basename.srt` and/or `basename.vtt` next to the video.
- With `--output-dir`: same basenames inside that directory (created if needed).

**Embed**

- New file: `basename.captioned` + original extension when the container has a known subtitle codec mapping.
- Unsupported extensions fall back to `basename.captioned.mkv` with SRT-style subtitles.

Subtitle codec mapping used for embed:

| Extension | Subtitle codec |
| --- | --- |
| `.mp4`, `.mov`, `.m4v` | `mov_text` |
| `.mkv` | `srt` |
| `.webm` | `webvtt` |

### Skip vs fail

- **Skipped**: no audio stream; or expected subtitle already exists and `--overwrite` was not passed (for `--format both`, existence is checked against `.srt` first).
- **Failed**: transcription empty, ffmpeg/ffprobe/API errors, or other pipeline errors.

### Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Success, or no matching video files under the path (warning only) |
| 1 | Configuration error (e.g. missing API key or ffmpeg) |
| 2 | Invalid option combination, discovery error, or at least one job **failed** in the batch |

Run `captionflow process --help` for the authoritative option list for your installed version.
