import json
import time

from captionflow.models import JobOptions, JobStatus, SubtitleFormat
from captionflow.pipeline import run_batch


def _make_options(**attrs):
    options = JobOptions(format=SubtitleFormat.SRT)
    for key, value in attrs.items():
        setattr(options, key, value)
    return options


def test_run_batch_writes_incremental_summary_report(tmp_path, monkeypatch):
    files = [tmp_path / "a.mkv", tmp_path / "b.mkv"]
    for file in files:
        file.write_bytes(b"video")

    report_path = tmp_path / "summary.json"
    calls = []

    def fake_process_single(video_path, options):
        from captionflow.models import JobResult

        calls.append(video_path.name)
        status = JobStatus.SUCCESS if video_path.name == "a.mkv" else JobStatus.SKIPPED
        return JobResult(
            input_path=video_path,
            status=status,
            error=None if status == JobStatus.SUCCESS else "already done",
            duration=0.1,
        )

    monkeypatch.setattr("captionflow.pipeline.process_single", fake_process_single)

    summary = run_batch(files, _make_options(summary_report=report_path))

    assert calls == ["a.mkv", "b.mkv"]
    assert report_path.exists()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["total"] == 2
    assert payload["succeeded"] == 1
    assert payload["skipped"] == 1
    assert [item["input_path"] for item in payload["results"]] == [str(files[0]), str(files[1])]
    assert getattr(summary, "report_path") == report_path


def test_run_batch_preserves_input_order_in_parallel(tmp_path, monkeypatch):
    files = [tmp_path / name for name in ("a.mkv", "b.mkv", "c.mkv")]
    for file in files:
        file.write_bytes(b"video")

    def fake_process_single(video_path, options):
        from captionflow.models import JobResult

        if video_path.name == "a.mkv":
            time.sleep(0.05)
        return JobResult(
            input_path=video_path,
            status=JobStatus.SUCCESS,
            duration=0.01,
        )

    monkeypatch.setattr("captionflow.pipeline.process_single", fake_process_single)

    summary = run_batch(files, _make_options(jobs=3))

    assert [result.input_path.name for result in summary.results] == ["a.mkv", "b.mkv", "c.mkv"]
    assert summary.succeeded == 3


def test_run_batch_stops_submitting_after_fail_fast_error(tmp_path, monkeypatch):
    files = [tmp_path / name for name in ("a.mkv", "b.mkv", "c.mkv")]
    for file in files:
        file.write_bytes(b"video")

    seen = []

    def fake_process_single(video_path, options):
        from captionflow.models import JobResult

        seen.append(video_path.name)
        return JobResult(
            input_path=video_path,
            status=JobStatus.FAILED if video_path.name == "a.mkv" else JobStatus.SUCCESS,
            error="boom" if video_path.name == "a.mkv" else None,
            duration=0.01,
        )

    monkeypatch.setattr("captionflow.pipeline.process_single", fake_process_single)

    summary = run_batch(files, _make_options(jobs=2), fail_fast=True)

    assert summary.failed == 1
    assert "a.mkv" in seen
    assert len(seen) <= 2


def test_run_batch_resumes_completed_items_from_summary_report(tmp_path, monkeypatch):
    files = [tmp_path / name for name in ("a.mkv", "b.mkv", "c.mkv")]
    for file in files:
        file.write_bytes(b"video")

    report_path = tmp_path / "summary.json"
    report_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-03-22T00:00:00Z",
                "total": 3,
                "succeeded": 1,
                "failed": 1,
                "skipped": 0,
                "results": [
                    {
                        "input_path": str(files[0]),
                        "status": "success",
                        "subtitle_paths": [],
                        "embedded_path": None,
                        "error": None,
                        "duration": 0.1,
                        "deleted_original": False,
                        "cleaned_subtitles": [],
                        "dry_run": False,
                    },
                    {
                        "input_path": str(files[1]),
                        "status": "failed",
                        "subtitle_paths": [],
                        "embedded_path": None,
                        "error": "boom",
                        "duration": 0.1,
                        "deleted_original": False,
                        "cleaned_subtitles": [],
                        "dry_run": False,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    seen = []

    def fake_process_single(video_path, options):
        from captionflow.models import JobResult

        seen.append(video_path.name)
        return JobResult(input_path=video_path, status=JobStatus.SUCCESS, duration=0.01)

    monkeypatch.setattr("captionflow.pipeline.process_single", fake_process_single)

    summary = run_batch(files, _make_options(summary_report=report_path))

    assert seen == ["b.mkv", "c.mkv"]
    assert [result.input_path.name for result in summary.results] == ["a.mkv", "b.mkv", "c.mkv"]
    assert summary.succeeded == 3
