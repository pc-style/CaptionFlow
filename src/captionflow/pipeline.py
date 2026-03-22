"""Processing pipeline for CaptionFlow."""

from __future__ import annotations

import json
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn, TimeElapsedColumn

from .captions import generate_captions, write_captions
from .constants import CAPTIONED_SUFFIX, MKV_FALLBACK_EXT, SUBTITLE_CODEC_MAP
from .deepgram_client import transcribe_audio
from .errors import CaptionFlowError
from .ffmpeg_ops import embed_subtitles, extract_audio, probe_media
from .models import BatchSummary, JobOptions, JobResult, JobStatus, SubtitleFormat

console = Console()


def _option(options: JobOptions, name: str, default: Any = None) -> Any:
    return getattr(options, name, default)


def _overwrite_mode(options: JobOptions) -> str:
    mode = _option(options, "overwrite_mode")
    if isinstance(mode, str) and mode:
        return mode

    if _option(options, "overwrite", False):
        return "all"

    overwrite_subtitles = _option(options, "overwrite_subtitles", False)
    overwrite_embedded = _option(options, "overwrite_embedded", False)

    if overwrite_subtitles and overwrite_embedded:
        return "all"
    if overwrite_subtitles:
        return "subtitles"
    if overwrite_embedded:
        return "embedded"
    return "none"


def _should_overwrite_subtitles(options: JobOptions) -> bool:
    return _overwrite_mode(options) in {"all", "subtitles"}


def _should_overwrite_embedded(options: JobOptions) -> bool:
    return _overwrite_mode(options) in {"all", "embedded"}


def _move_captioned_to(options: JobOptions) -> Path | None:
    move_dir = _option(options, "move_captioned_to")
    if not move_dir:
        return None
    return Path(move_dir)


def _embedded_output_path(video_path: Path, options: JobOptions) -> Path:
    move_dir = _move_captioned_to(options)
    filename = video_path.with_stem(video_path.stem + CAPTIONED_SUFFIX).name
    if video_path.suffix.lower() not in SUBTITLE_CODEC_MAP:
        filename = Path(filename).with_suffix(MKV_FALLBACK_EXT).name
    if move_dir:
        move_dir.mkdir(parents=True, exist_ok=True)
        return move_dir / filename
    return video_path.with_name(filename)


def _expected_subtitle_paths(video_path: Path, options: JobOptions) -> list[Path]:
    out_dir = options.output_dir or video_path.parent
    if options.format == SubtitleFormat.SRT:
        return [out_dir / f"{video_path.stem}.srt"]
    if options.format == SubtitleFormat.VTT:
        return [out_dir / f"{video_path.stem}.vtt"]
    return [
        out_dir / f"{video_path.stem}.srt",
        out_dir / f"{video_path.stem}.vtt",
    ]


def _dry_run_result(video_path: Path, reason: str) -> JobResult:
    return JobResult(
        input_path=video_path,
        status=JobStatus.SKIPPED,
        error=f"Dry run: {reason}",
        dry_run=True,
    )


def _serialize_result(result: JobResult) -> dict[str, Any]:
    return {
        "input_path": str(result.input_path),
        "status": result.status.value if isinstance(result.status, JobStatus) else str(result.status),
        "subtitle_paths": [str(path) for path in result.subtitle_paths],
        "embedded_path": str(result.embedded_path) if result.embedded_path else None,
        "error": result.error,
        "duration": result.duration,
        "deleted_original": result.deleted_original,
        "cleaned_subtitles": [str(path) for path in result.cleaned_subtitles],
        "dry_run": result.dry_run,
    }


def _write_summary_report(summary: BatchSummary, report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total": summary.total,
        "succeeded": summary.succeeded,
        "failed": summary.failed,
        "skipped": summary.skipped,
        "results": [_serialize_result(result) for result in summary.results],
    }
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _deserialize_result(item: dict[str, Any]) -> JobResult:
    return JobResult(
        input_path=Path(item["input_path"]),
        status=JobStatus(item["status"]),
        subtitle_paths=[Path(path) for path in item.get("subtitle_paths", [])],
        embedded_path=Path(item["embedded_path"]) if item.get("embedded_path") else None,
        error=item.get("error"),
        duration=float(item.get("duration", 0.0)),
        deleted_original=bool(item.get("deleted_original", False)),
        cleaned_subtitles=[Path(path) for path in item.get("cleaned_subtitles", [])],
        dry_run=bool(item.get("dry_run", False)),
    )


def _load_summary_report(report_path: Path) -> dict[Path, JobResult]:
    if not report_path.exists():
        return {}

    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    results: dict[Path, JobResult] = {}
    for item in payload.get("results", []):
        if not isinstance(item, dict) or "input_path" not in item or "status" not in item:
            continue
        result = _deserialize_result(item)
        results[result.input_path] = result
    return results


def _record_summary_result(summary: BatchSummary, result: JobResult, *, report_path: Path | None = None) -> None:
    summary.results.append(result)
    if result.status == JobStatus.SUCCESS:
        summary.succeeded += 1
    elif result.status == JobStatus.FAILED:
        summary.failed += 1
    else:
        summary.skipped += 1

    if report_path:
        _write_summary_report(summary, report_path)


def process_single(video_path: Path, options: JobOptions) -> JobResult:
    """Process a single video file through the full pipeline."""
    start = time.monotonic()
    temp_audio: Path | None = None

    try:
        expected_subtitles = _expected_subtitle_paths(video_path, options)
        embedded_output = _embedded_output_path(video_path, options) if options.embed else None

        if _option(options, "dry_run", False):
            actions: list[str] = ["transcribe"]
            if any(path.exists() for path in expected_subtitles):
                if _should_overwrite_subtitles(options):
                    actions.append("overwrite subtitles")
                else:
                    actions.append("skip existing subtitles")
            else:
                actions.append("write subtitles")
            if options.embed and embedded_output:
                if embedded_output.exists():
                    if _should_overwrite_embedded(options):
                        actions.append("overwrite embedded output")
                    else:
                        actions.append("skip existing embedded output")
                else:
                    actions.append("embed subtitles")
            if _option(options, "delete_original", False):
                actions.append("delete original")
            if _option(options, "cleanup_srt", False):
                actions.append("cleanup srt")
            if _move_captioned_to(options):
                actions.append(f"move captioned to {_move_captioned_to(options)}")
            return _dry_run_result(video_path, ", ".join(actions))

        if options.embed and _option(options, "skip_existing_embedded", False) and embedded_output and embedded_output.exists():
            return JobResult(
                input_path=video_path,
                status=JobStatus.SKIPPED,
                error=f"Embedded output already exists: {embedded_output.name}",
                embedded_path=embedded_output,
            )

        if not _should_overwrite_subtitles(options):
            existing_subtitle = next((path for path in expected_subtitles if path.exists()), None)
            if existing_subtitle:
                return JobResult(
                    input_path=video_path,
                    status=JobStatus.SKIPPED,
                    error=f"Subtitle output already exists: {existing_subtitle.name}",
                )

        if options.embed and embedded_output and embedded_output.exists() and not _should_overwrite_embedded(options):
            return JobResult(
                input_path=video_path,
                status=JobStatus.SKIPPED,
                error=f"Embedded output already exists: {embedded_output.name}",
                embedded_path=embedded_output,
            )

        info = probe_media(video_path)
        if not info.has_audio:
            return JobResult(
                input_path=video_path,
                status=JobStatus.SKIPPED,
                error="No audio stream found",
            )

        if options.verbose:
            console.print(f"  Extracting audio from {video_path.name}...")
        temp_audio = extract_audio(video_path)

        if options.verbose:
            console.print(f"  Transcribing with DeepGram ({options.model})...")
        audio_bytes = temp_audio.read_bytes()
        response = transcribe_audio(
            audio_bytes,
            model=options.model,
            language=options.language,
            diarize=options.diarize,
        )

        if options.verbose:
            console.print("  Generating subtitles...")
        captions = generate_captions(response, options.format, diarize=options.diarize)

        if not captions or all(not content.strip() for content in captions.values()):
            return JobResult(
                input_path=video_path,
                status=JobStatus.FAILED,
                error="Transcription returned empty result",
            )

        subtitle_paths = write_captions(captions, video_path, options.output_dir)
        embedded_path = None
        cleaned_subtitles: list[Path] = []
        deleted_original = False

        if options.embed:
            if options.verbose:
                console.print("  Embedding subtitles into video...")
            srt_path = next((path for path in subtitle_paths if path.suffix == ".srt"), None)
            temp_srt = None
            if not srt_path:
                srt_captions = generate_captions(response, SubtitleFormat.SRT, diarize=options.diarize)
                temp_srt = video_path.with_suffix(".tmp.srt")
                temp_srt.write_text(srt_captions["srt"], encoding="utf-8")
                srt_path = temp_srt

            embedded_path = embed_subtitles(video_path, srt_path, output_path=embedded_output)

            if temp_srt:
                temp_srt.unlink(missing_ok=True)

            if _option(options, "cleanup_srt", False):
                for subtitle_path in list(subtitle_paths):
                    if subtitle_path.suffix == ".srt" and subtitle_path.exists():
                        subtitle_path.unlink()
                        cleaned_subtitles.append(subtitle_path)
                subtitle_paths = [path for path in subtitle_paths if path.suffix != ".srt"]

            if _option(options, "delete_original", False) and embedded_path and embedded_path.exists():
                video_path.unlink()
                deleted_original = True

        elapsed = time.monotonic() - start
        result = JobResult(
            input_path=video_path,
            status=JobStatus.SUCCESS,
            subtitle_paths=subtitle_paths,
            embedded_path=embedded_path,
            duration=elapsed,
            deleted_original=deleted_original,
            cleaned_subtitles=cleaned_subtitles,
        )
        return result

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
    """Process multiple video files with optional parallelism and JSON reporting."""
    summary = BatchSummary(total=len(files))
    jobs = max(1, int(_option(options, "jobs", 1) or 1))
    report_path = _option(options, "summary_report")
    if report_path:
        report_path = Path(report_path)
        summary.report_path = report_path
    prior_results = _load_summary_report(report_path) if report_path else {}

    indexed_results: list[JobResult | None] = [None] * len(files)
    pending: list[tuple[int, Path]] = []
    for index, video_path in enumerate(files):
        prior = prior_results.get(video_path)
        if prior and prior.status in {JobStatus.SUCCESS, JobStatus.SKIPPED}:
            indexed_results[index] = prior
            if prior.status == JobStatus.SUCCESS:
                summary.succeeded += 1
            else:
                summary.skipped += 1
        else:
            pending.append((index, video_path))

    summary.results = [result for result in indexed_results if result is not None]
    if report_path:
        _write_summary_report(summary, report_path)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Processing videos", total=len(files))
        if summary.results:
            progress.update(task, advance=len(summary.results))

        if jobs == 1:
            for index, video_path in pending:
                progress.update(task, description=f"Processing {video_path.name}")
                result = process_single(video_path, options)
                indexed_results[index] = result
                _record_summary_result(summary, result, report_path=report_path)
                progress.update(task, advance=1)
                if fail_fast and result.status == JobStatus.FAILED:
                    break
            summary.results = [result for result in indexed_results if result is not None]
            if report_path:
                _write_summary_report(summary, report_path)
            return summary

        futures: dict[Future[JobResult], tuple[int, Path]] = {}
        submit_index = 0
        stop_submitting = False

        def submit_next(executor: ThreadPoolExecutor) -> None:
            nonlocal submit_index
            if stop_submitting or submit_index >= len(pending):
                return
            index, video_path = pending[submit_index]
            future = executor.submit(process_single, video_path, options)
            futures[future] = (index, video_path)
            submit_index += 1

        with ThreadPoolExecutor(max_workers=jobs) as executor:
            for _ in range(min(jobs, len(pending))):
                submit_next(executor)

            while futures:
                done, _ = wait(futures, return_when=FIRST_COMPLETED)
                for future in done:
                    index, video_path = futures.pop(future)
                    progress.update(task, description=f"Processed {video_path.name}")
                    result = future.result()
                    indexed_results[index] = result
                    _record_summary_result(summary, result, report_path=report_path)
                    progress.update(task, advance=1)

                    if fail_fast and result.status == JobStatus.FAILED:
                        stop_submitting = True

                    if not stop_submitting:
                        submit_next(executor)

        summary.results = [result for result in indexed_results if result is not None]
        if report_path:
            _write_summary_report(summary, report_path)

    return summary
