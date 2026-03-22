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
| `--skip-existing-embedded` | off | Skip a file when the expected embedded output already exists. Useful for reruns. |
| `--cleanup-srt` | off | Remove generated `.srt` files after a successful embed. **Requires** `--embed`. |
| `--dry-run` | off | Show what would happen without writing subtitles, embedded outputs, or deleting anything. |
| `--move-captioned-to DIRECTORY` | *(none)* | Write embedded outputs to another directory. **Requires** `--embed`. |
| `--diarize` / `--no-diarize` | `no-diarize` | Request speaker diarization; speaker lines are kept in subtitles when enabled. |
| `-r`, `--recursive` | off | When `INPUT_PATH` is a directory, include subfolders. |
| `--model` | `nova-3` | DeepGram model name passed to the API. |
| `--overwrite` | off | Legacy shortcut: overwrite both subtitle files and embedded outputs. |
| `--overwrite-subtitles` | off | Overwrite subtitle files only. |
| `--overwrite-embedded` | off | Overwrite embedded captioned videos only. |
| `--jobs` | `1` | Maximum number of parallel worker threads for batch processing. |
| `--summary-report FILE` | *(none)* | Write a JSON batch report after each completed result and use it to resume later runs. |
| `--keep-temp` | off | Keep temporary extracted audio (normally deleted). |
| `--fail-fast` | off | In batch mode, stop after the first **failed** job (skipped jobs do not stop the batch). |
| `-v`, `--verbose` | off | Print per-step messages. |

### Option constraints

- `--delete-original` requires `--embed`
- `--cleanup-srt` requires `--embed`
- `--move-captioned-to DIRECTORY` requires `--embed`
- `--jobs` must be `>= 1`

### Overwrite modes

CaptionFlow now distinguishes subtitle outputs from embedded outputs.

| Mode | Effect |
| --- | --- |
| default | Skip if an existing subtitle or embedded output would conflict |
| `--overwrite-subtitles` | Rewrite `.srt` / `.vtt` files, but still skip existing embedded outputs |
| `--overwrite-embedded` | Rebuild captioned video outputs, but still skip existing subtitle files |
| `--overwrite` | Rewrite both subtitles and embedded outputs |

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
- With `--move-captioned-to DIRECTORY`, the embedded file is written there instead of beside the source file.

Subtitle codec mapping used for embed:

| Extension | Subtitle codec |
| --- | --- |
| `.mp4`, `.mov`, `.m4v` | `mov_text` |
| `.mkv` | `srt` |
| `.webm` | `webvtt` |

### Skip vs fail

- **Skipped**: no audio stream; existing subtitle output without subtitle overwrite enabled; existing embedded output without embedded overwrite enabled; existing embedded output when `--skip-existing-embedded` is on; or a dry run.
- **Failed**: transcription empty, ffmpeg/ffprobe/API errors, or other pipeline errors.

### Batch report JSON

When you pass `--summary-report run.json`, CaptionFlow writes a machine-readable report after each completed result. The file contains:

- top-level counts: `total`, `succeeded`, `failed`, `skipped`
- a `results` array with one item per processed or resumed input
- per-result fields including `input_path`, `status`, `subtitle_paths`, `embedded_path`, `error`, `duration`, `deleted_original`, `cleaned_subtitles`, and `dry_run`

Example:

```json
{
  "total": 2,
  "succeeded": 1,
  "failed": 1,
  "skipped": 0,
  "results": [
    {
      "input_path": "/videos/a.mkv",
      "status": "success",
      "subtitle_paths": ["/videos/a.srt"],
      "embedded_path": "/videos/a.captioned.mkv",
      "error": null,
      "duration": 24.8,
      "deleted_original": false,
      "cleaned_subtitles": [],
      "dry_run": false
    }
  ]
}
```

If you rerun the same command with the same `--summary-report` path, previously successful and skipped files are reused from the report; prior failures are retried.

### Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Success, or no matching video files under the path (warning only) |
| 1 | Configuration error (e.g. missing API key or ffmpeg) |
| 2 | Invalid option combination, discovery error, or at least one job **failed** in the batch |

Run `captionflow process --help` for the authoritative option list for your installed version.
