import json
from pathlib import Path

from captionflow.errors import EmbedError
from captionflow.models import JobOptions, JobStatus, SubtitleFormat
from captionflow.pipeline import process_single


def _make_options(**attrs):
    options = JobOptions(format=SubtitleFormat.SRT, embed=False, delete_original=False)
    for key, value in attrs.items():
        setattr(options, key, value)
    return options


def _stub_pipeline(monkeypatch, tmp_path, *, subtitle_paths=None, embedded_path=None):
    video_path = tmp_path / "episode.mkv"
    video_path.write_bytes(b"video")

    temp_audio = tmp_path / "episode.wav"
    temp_audio.write_bytes(b"audio")

    subtitle_paths = subtitle_paths or [tmp_path / "episode.srt"]

    embedded_path = embedded_path or (tmp_path / "episode.captioned.mkv")

    monkeypatch.setattr("captionflow.pipeline.probe_media", lambda path: type("Info", (), {"has_audio": True})())
    monkeypatch.setattr("captionflow.pipeline.extract_audio", lambda path: temp_audio)
    monkeypatch.setattr("captionflow.pipeline.transcribe_audio", lambda *args, **kwargs: {"results": {"utterances": [{"words": [{}]}]}})
    monkeypatch.setattr(
        "captionflow.pipeline.generate_captions",
        lambda response, fmt, diarize=False: {"srt": "1\n00:00:00,000 --> 00:00:01,000\nHello\n"},
    )
    monkeypatch.setattr(
        "captionflow.pipeline.write_captions",
        lambda captions, base_path, output_dir: [_write_subtitle(subtitle_path) for subtitle_path in subtitle_paths],
    )
    monkeypatch.setattr(
        "captionflow.pipeline.embed_subtitles",
        lambda video, srt, output_path=None: _write_embedded(Path(output_path or embedded_path)),
    )

    return video_path, subtitle_paths, embedded_path


def _write_subtitle(subtitle_path):
    subtitle_path.write_text("subtitle", encoding="utf-8")
    return subtitle_path


def _write_embedded(embedded_path):
    embedded_path.parent.mkdir(parents=True, exist_ok=True)
    embedded_path.write_bytes(b"captioned")
    return embedded_path


def test_process_single_deletes_original_after_successful_embed(tmp_path, monkeypatch):
    video_path, _, embedded_path = _stub_pipeline(monkeypatch, tmp_path)

    result = process_single(
        video_path,
        _make_options(embed=True, delete_original=True),
    )

    assert result.status == JobStatus.SUCCESS
    assert result.embedded_path == embedded_path
    assert not video_path.exists()
    assert result.deleted_original is True


def test_process_single_keeps_original_without_delete_flag(tmp_path, monkeypatch):
    video_path, _, embedded_path = _stub_pipeline(monkeypatch, tmp_path)

    result = process_single(
        video_path,
        _make_options(embed=True, delete_original=False),
    )

    assert result.status == JobStatus.SUCCESS
    assert video_path.exists()
    assert result.deleted_original is False


def test_process_single_skips_when_embedded_output_exists(tmp_path, monkeypatch):
    video_path, _, embedded_path = _stub_pipeline(monkeypatch, tmp_path)
    embedded_path.write_bytes(b"captioned")

    result = process_single(
        video_path,
        _make_options(embed=True, skip_existing_embedded=True),
    )

    assert result.status == JobStatus.SKIPPED
    assert "Embedded output already exists" in result.error


def test_process_single_cleans_up_srt_after_successful_embed(tmp_path, monkeypatch):
    video_path, subtitle_paths, embedded_path = _stub_pipeline(monkeypatch, tmp_path)

    result = process_single(
        video_path,
        _make_options(embed=True, cleanup_srt=True),
    )

    assert result.status == JobStatus.SUCCESS
    assert subtitle_paths[0] not in result.subtitle_paths
    assert not subtitle_paths[0].exists()
    assert result.cleaned_subtitles == subtitle_paths


def test_process_single_dry_run_does_not_touch_files(tmp_path, monkeypatch):
    video_path, subtitle_paths, _ = _stub_pipeline(monkeypatch, tmp_path)

    result = process_single(
        video_path,
        _make_options(embed=True, dry_run=True, delete_original=True, cleanup_srt=True),
    )

    assert result.status == JobStatus.SKIPPED
    assert result.dry_run is True
    assert video_path.exists()
    assert not subtitle_paths[0].exists()


def test_process_single_moves_embedded_output_to_target_dir(tmp_path, monkeypatch):
    move_dir = tmp_path / "captioned"
    expected_embedded = move_dir / "episode.captioned.mkv"
    video_path, _, _ = _stub_pipeline(monkeypatch, tmp_path, embedded_path=expected_embedded)

    result = process_single(
        video_path,
        _make_options(embed=True, move_captioned_to=move_dir),
    )

    assert result.status == JobStatus.SUCCESS
    assert result.embedded_path == expected_embedded


def test_process_single_writes_json_safe_state_for_cleaned_subtitles(tmp_path, monkeypatch):
    video_path, subtitle_paths, _ = _stub_pipeline(monkeypatch, tmp_path)

    result = process_single(
        video_path,
        _make_options(embed=True, cleanup_srt=True, delete_original=True),
    )

    payload = {
        "deleted_original": result.deleted_original,
        "cleaned_subtitles": [str(path) for path in result.cleaned_subtitles],
    }

    assert json.loads(json.dumps(payload)) == {
        "deleted_original": True,
        "cleaned_subtitles": [str(path) for path in subtitle_paths],
    }


def test_process_single_keeps_original_and_subtitles_when_embed_fails(tmp_path, monkeypatch):
    video_path, subtitle_paths, _ = _stub_pipeline(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "captionflow.pipeline.embed_subtitles",
        lambda video, srt, output_path=None: (_ for _ in ()).throw(EmbedError("embed failed")),
    )

    result = process_single(
        video_path,
        _make_options(embed=True, delete_original=True, cleanup_srt=True),
    )

    assert result.status == JobStatus.FAILED
    assert video_path.exists()
    assert subtitle_paths[0].exists()
