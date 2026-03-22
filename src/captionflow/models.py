"""Data models for CaptionFlow."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class SubtitleFormat(str, Enum):
    SRT = "srt"
    VTT = "vtt"
    BOTH = "both"


class JobStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class JobOptions:
    format: SubtitleFormat = SubtitleFormat.SRT
    language: str = "en"
    model: str = "nova-3"
    embed: bool = False
    delete_original: bool = False
    skip_existing_embedded: bool = False
    cleanup_srt: bool = False
    dry_run: bool = False
    move_captioned_to: Path | None = None
    diarize: bool = False
    overwrite: bool = False
    overwrite_subtitles: bool = False
    overwrite_embedded: bool = False
    jobs: int = 1
    summary_report: Path | None = None
    keep_temp: bool = False
    verbose: bool = False
    output_dir: Path | None = None


@dataclass
class MediaInfo:
    path: Path
    has_audio: bool = False
    duration: float = 0.0
    audio_codec: str = ""
    container: str = ""


@dataclass
class JobResult:
    input_path: Path
    status: JobStatus = JobStatus.SUCCESS
    subtitle_paths: list[Path] = field(default_factory=list)
    embedded_path: Path | None = None
    error: str | None = None
    duration: float = 0.0
    deleted_original: bool = False
    cleaned_subtitles: list[Path] = field(default_factory=list)
    dry_run: bool = False


@dataclass
class BatchSummary:
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    results: list[JobResult] = field(default_factory=list)
    report_path: Path | None = None

    @property
    def has_failures(self) -> bool:
        return self.failed > 0
