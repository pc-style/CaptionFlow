"""Processing pipeline for CaptionFlow."""

from __future__ import annotations

import time
from pathlib import Path

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn, TimeElapsedColumn

from .captions import generate_captions, write_captions
from .deepgram_client import transcribe_audio
from .errors import CaptionFlowError
from .ffmpeg_ops import embed_subtitles, extract_audio, probe_media
from .models import BatchSummary, JobOptions, JobResult, JobStatus, SubtitleFormat

console = Console()


def process_single(video_path: Path, options: JobOptions) -> JobResult:
    """Process a single video file through the full pipeline."""
    start = time.monotonic()
    temp_audio: Path | None = None

    try:
        # 1. Probe media
        info = probe_media(video_path)
        if not info.has_audio:
            return JobResult(
                input_path=video_path,
                status=JobStatus.SKIPPED,
                error="No audio stream found",
            )

        # 2. Check existing outputs
        if not options.overwrite:
            expected_ext = "srt" if options.format != SubtitleFormat.VTT else "vtt"
            out_dir = options.output_dir or video_path.parent
            expected_path = out_dir / f"{video_path.stem}.{expected_ext}"
            if expected_path.exists():
                return JobResult(
                    input_path=video_path,
                    status=JobStatus.SKIPPED,
                    error=f"Output already exists: {expected_path.name} (use --overwrite)",
                )

        # 3. Extract audio
        if options.verbose:
            console.print(f"  Extracting audio from {video_path.name}...")
        temp_audio = extract_audio(video_path)

        # 4. Transcribe
        if options.verbose:
            console.print(f"  Transcribing with DeepGram ({options.model})...")
        audio_bytes = temp_audio.read_bytes()
        response = transcribe_audio(
            audio_bytes,
            model=options.model,
            language=options.language,
            diarize=options.diarize,
        )

        # 5. Generate captions
        if options.verbose:
            console.print("  Generating subtitles...")
        captions = generate_captions(response, options.format)

        if not captions or all(not c.strip() for c in captions.values()):
            return JobResult(
                input_path=video_path,
                status=JobStatus.FAILED,
                error="Transcription returned empty result",
            )

        # 6. Write subtitle files
        subtitle_paths = write_captions(captions, video_path, options.output_dir)

        # 7. Embed if requested
        embedded_path = None
        if options.embed:
            if options.verbose:
                console.print("  Embedding subtitles into video...")
            srt_path = next((p for p in subtitle_paths if p.suffix == ".srt"), None)
            if not srt_path:
                srt_captions = generate_captions(response, SubtitleFormat.SRT)
                temp_srt = video_path.with_suffix(".tmp.srt")
                temp_srt.write_text(srt_captions["srt"], encoding="utf-8")
                srt_path = temp_srt

            embedded_path = embed_subtitles(video_path, srt_path)

            if srt_path.suffix == ".tmp.srt":
                srt_path.unlink(missing_ok=True)

        elapsed = time.monotonic() - start
        return JobResult(
            input_path=video_path,
            status=JobStatus.SUCCESS,
            subtitle_paths=subtitle_paths,
            embedded_path=embedded_path,
            duration=elapsed,
        )

    except CaptionFlowError as e:
        elapsed = time.monotonic() - start
        return JobResult(
            input_path=video_path,
            status=JobStatus.FAILED,
            error=str(e),
            duration=elapsed,
        )
    finally:
        if temp_audio and not options.keep_temp:
            temp_audio.unlink(missing_ok=True)


def run_batch(
    files: list[Path],
    options: JobOptions,
    *,
    fail_fast: bool = False,
) -> BatchSummary:
    """Process multiple video files sequentially with progress."""
    summary = BatchSummary(total=len(files))

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Processing videos", total=len(files))

        for video_path in files:
            progress.update(task, description=f"Processing {video_path.name}")
            result = process_single(video_path, options)
            summary.results.append(result)

            if result.status == JobStatus.SUCCESS:
                summary.succeeded += 1
            elif result.status == JobStatus.FAILED:
                summary.failed += 1
                if fail_fast:
                    progress.update(task, advance=1)
                    break
            else:
                summary.skipped += 1

            progress.update(task, advance=1)

    return summary
