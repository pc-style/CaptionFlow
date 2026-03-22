from pathlib import Path

from click.testing import CliRunner

from captionflow.cli import cli
from captionflow.models import BatchSummary, JobResult, JobStatus


def _stub_environment(monkeypatch):
    monkeypatch.setattr("captionflow.cli.get_api_key", lambda: "dummy-key")
    monkeypatch.setattr("captionflow.cli.get_ffmpeg_path", lambda: Path("/usr/bin/ffmpeg"))
    monkeypatch.setattr("captionflow.cli.get_ffprobe_path", lambda: Path("/usr/bin/ffprobe"))


def test_process_plumbs_new_options_into_job_options(tmp_path, monkeypatch):
    _stub_environment(monkeypatch)

    input_path = tmp_path / "episode.mkv"
    input_path.write_bytes(b"video")
    summary_path = tmp_path / "summary.json"
    move_dir = tmp_path / "captioned"

    captured = {}

    def fake_run_batch(files, options, fail_fast=False):
        captured["files"] = files
        captured["options"] = options
        captured["fail_fast"] = fail_fast
        return BatchSummary(
            total=1,
            succeeded=1,
            results=[JobResult(input_path=files[0], status=JobStatus.SUCCESS)],
        )

    monkeypatch.setattr("captionflow.discovery.discover_files", lambda path, recursive=False: [path])
    monkeypatch.setattr("captionflow.pipeline.run_batch", fake_run_batch)
    monkeypatch.setattr("captionflow.progress.print_summary", lambda summary, console: None)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "process",
            str(input_path),
            "--embed",
            "--delete-original",
            "--skip-existing-embedded",
            "--cleanup-srt",
            "--dry-run",
            "--move-captioned-to",
            str(move_dir),
            "--overwrite-subtitles",
            "--overwrite-embedded",
            "--jobs",
            "4",
            "--summary-report",
            str(summary_path),
            "--verbose",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["files"] == [input_path]
    assert captured["fail_fast"] is False

    options = captured["options"]
    assert options.embed is True
    assert options.delete_original is True
    assert options.skip_existing_embedded is True
    assert options.cleanup_srt is True
    assert options.dry_run is True
    assert options.move_captioned_to == move_dir
    assert options.overwrite_subtitles is True
    assert options.overwrite_embedded is True
    assert options.overwrite is True
    assert options.jobs == 4
    assert options.summary_report == summary_path


def test_process_rejects_cleanup_srt_without_embed(tmp_path, monkeypatch):
    _stub_environment(monkeypatch)

    runner = CliRunner()
    input_path = tmp_path / "episode.mkv"
    input_path.write_bytes(b"video")

    result = runner.invoke(cli, ["process", str(input_path), "--cleanup-srt"])

    assert result.exit_code == 2
    assert "--cleanup-srt requires --embed" in result.output


def test_process_rejects_move_captioned_to_without_embed(tmp_path, monkeypatch):
    _stub_environment(monkeypatch)

    runner = CliRunner()
    input_path = tmp_path / "episode.mkv"
    input_path.write_bytes(b"video")
    out_dir = tmp_path / "captioned"

    result = runner.invoke(
        cli,
        [
            "process",
            str(input_path),
            "--move-captioned-to",
            str(out_dir),
        ],
    )

    assert result.exit_code == 2
    assert "--move-captioned-to requires --embed" in result.output


def test_process_rejects_invalid_job_count(tmp_path, monkeypatch):
    _stub_environment(monkeypatch)

    runner = CliRunner()
    input_path = tmp_path / "episode.mkv"
    input_path.write_bytes(b"video")

    result = runner.invoke(
        cli,
        [
            "process",
            str(input_path),
            "--jobs",
            "0",
        ],
    )

    assert result.exit_code != 0
    assert "Invalid value for '--jobs'" in result.output
