"""CLI entry point for CaptionFlow."""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from . import __version__
from .config import get_api_key, get_ffmpeg_path, get_ffprobe_path, get_tool_version
from .errors import ConfigError

console = Console()
err_console = Console(stderr=True)


@click.group()
@click.version_option(version=__version__, prog_name="captionflow")
def cli() -> None:
    """CaptionFlow - Generate subtitles from video files using DeepGram."""


@cli.command()
def doctor() -> None:
    """Check that all required dependencies and configuration are available."""
    table = Table(title="CaptionFlow Environment Check")
    table.add_column("Check", style="bold")
    table.add_column("Status")
    table.add_column("Details")

    all_ok = True

    # Check DEEPGRAM_API_KEY
    try:
        key = get_api_key()
        masked = key[:4] + "..." + key[-4:] if len(key) > 8 else "****"
        table.add_row("DEEPGRAM_API_KEY", "[green]OK[/green]", masked)
    except ConfigError as e:
        table.add_row("DEEPGRAM_API_KEY", "[red]MISSING[/red]", str(e).split("\n")[0])
        all_ok = False

    # Check ffmpeg
    try:
        get_ffmpeg_path()
        version = get_tool_version("ffmpeg") or "unknown"
        table.add_row("ffmpeg", "[green]OK[/green]", version)
    except ConfigError:
        table.add_row("ffmpeg", "[red]MISSING[/red]", "Not found in PATH")
        all_ok = False

    # Check ffprobe
    try:
        get_ffprobe_path()
        version = get_tool_version("ffprobe") or "unknown"
        table.add_row("ffprobe", "[green]OK[/green]", version)
    except ConfigError:
        table.add_row("ffprobe", "[red]MISSING[/red]", "Not found in PATH")
        all_ok = False

    console.print()
    console.print(table)
    console.print()

    if all_ok:
        console.print("[green]All checks passed. Ready to go.[/green]")
    else:
        err_console.print("[red]Some checks failed. Fix the issues above and retry.[/red]")
        sys.exit(1)


@cli.command()
@click.argument("input_path", type=click.Path(exists=True, resolve_path=True))
@click.option(
    "-o",
    "--output-dir",
    type=click.Path(resolve_path=True),
    default=None,
    help="Output directory (default: alongside source)",
)
@click.option(
    "-f",
    "--format",
    "fmt",
    type=click.Choice(["srt", "vtt", "both"], case_sensitive=False),
    default="srt",
    help="Subtitle output format",
)
@click.option("-l", "--language", default="en", help="Language code (e.g., en, es, fr)")
@click.option("--embed/--no-embed", default=False, help="Embed subtitles into a new video file")
@click.option(
    "--delete-original",
    is_flag=True,
    help="Delete the source video after a successful embedded output is created",
)
@click.option(
    "--skip-existing-embedded",
    is_flag=True,
    help="Skip videos that already have a captioned output",
)
@click.option(
    "--cleanup-srt",
    is_flag=True,
    help="Remove standalone subtitle files after embedding succeeds",
)
@click.option("--dry-run", is_flag=True, help="Show what would happen without writing files")
@click.option(
    "--move-captioned-to",
    type=click.Path(file_okay=False, dir_okay=True, resolve_path=True, path_type=Path),
    default=None,
    help="Write embedded outputs to this directory",
)
@click.option("--diarize/--no-diarize", default=False, help="Enable speaker diarization")
@click.option("-r", "--recursive", is_flag=True, help="Recurse into subdirectories")
@click.option("--model", default="nova-3", help="DeepGram model")
@click.option(
    "--overwrite",
    is_flag=True,
    help="Overwrite both subtitles and embedded outputs (legacy shortcut)",
)
@click.option(
    "--overwrite-subtitles/--no-overwrite-subtitles",
    default=False,
    help="Overwrite subtitle files only",
)
@click.option(
    "--overwrite-embedded/--no-overwrite-embedded",
    default=False,
    help="Overwrite embedded captioned videos only",
)
@click.option(
    "--jobs",
    type=click.IntRange(min=1),
    default=1,
    show_default=True,
    help="Maximum number of parallel jobs",
)
@click.option(
    "--summary-report",
    type=click.Path(dir_okay=False, resolve_path=True, path_type=Path),
    default=None,
    help="Write a JSON batch summary to this file",
)
@click.option("--keep-temp", is_flag=True, help="Keep temporary files")
@click.option("--fail-fast", is_flag=True, help="Stop on first failure in batch mode")
@click.option("-v", "--verbose", is_flag=True, help="Show detailed output")
def process(
    input_path: str,
    output_dir: str | None,
    fmt: str,
    language: str,
    embed: bool,
    delete_original: bool,
    skip_existing_embedded: bool,
    cleanup_srt: bool,
    dry_run: bool,
    move_captioned_to: Path | None,
    diarize: bool,
    recursive: bool,
    model: str,
    overwrite: bool,
    overwrite_subtitles: bool,
    overwrite_embedded: bool,
    jobs: int,
    summary_report: Path | None,
    keep_temp: bool,
    fail_fast: bool,
    verbose: bool,
) -> None:
    """Transcribe video files and generate subtitle files.

    INPUT_PATH can be a single video file or a directory of videos.
    """
    from .discovery import discover_files
    from .errors import CaptionFlowError
    from .models import JobOptions, SubtitleFormat
    from .pipeline import run_batch
    from .progress import print_summary

    try:
        get_api_key()
        get_ffmpeg_path()
        get_ffprobe_path()
    except ConfigError as e:
        err_console.print(f"[red]Configuration error:[/red] {e}")
        sys.exit(1)

    validation_errors: list[str] = []
    if delete_original and not embed:
        validation_errors.append("--delete-original requires --embed")
    if cleanup_srt and not embed:
        validation_errors.append("--cleanup-srt requires --embed")
    if move_captioned_to and not embed:
        validation_errors.append("--move-captioned-to requires --embed")

    if validation_errors:
        for message in validation_errors:
            err_console.print(f"[red]Option error:[/red] {message}")
        sys.exit(2)

    overwrite_subtitles = overwrite_subtitles or overwrite
    overwrite_embedded = overwrite_embedded or overwrite

    options = JobOptions(
        format=SubtitleFormat(fmt),
        language=language,
        model=model,
        embed=embed,
        delete_original=delete_original,
        skip_existing_embedded=skip_existing_embedded,
        cleanup_srt=cleanup_srt,
        dry_run=dry_run,
        move_captioned_to=move_captioned_to,
        diarize=diarize,
        overwrite=overwrite or overwrite_subtitles or overwrite_embedded,
        overwrite_subtitles=overwrite_subtitles,
        overwrite_embedded=overwrite_embedded,
        jobs=jobs,
        summary_report=summary_report,
        keep_temp=keep_temp,
        verbose=verbose,
        output_dir=Path(output_dir) if output_dir else None,
    )

    path = Path(input_path)
    try:
        files = discover_files(path, recursive=recursive)
    except CaptionFlowError as e:
        err_console.print(f"[red]Discovery error:[/red] {e}")
        sys.exit(1)

    if not files:
        err_console.print("[yellow]No supported video files found.[/yellow]")
        sys.exit(0)

    if verbose:
        console.print(f"Found {len(files)} video file(s) to process.")

    summary = run_batch(files, options, fail_fast=fail_fast)
    print_summary(summary, console)

    if summary.has_failures:
        sys.exit(2)
