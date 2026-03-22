from pathlib import Path

from captionflow.models import JobOptions, SubtitleFormat
from captionflow.pipeline import process_single


def test_process_single_deletes_original_after_successful_embed(tmp_path, monkeypatch):
    video_path = tmp_path / "episode.mkv"
    video_path.write_bytes(b"video")

    temp_audio = tmp_path / "episode.wav"
    temp_audio.write_bytes(b"audio")

    embedded_path = tmp_path / "episode.captioned.mkv"
    embedded_path.write_bytes(b"captioned")

    monkeypatch.setattr("captionflow.pipeline.probe_media", lambda path: type("Info", (), {"has_audio": True})())
    monkeypatch.setattr("captionflow.pipeline.extract_audio", lambda path: temp_audio)
    monkeypatch.setattr("captionflow.pipeline.transcribe_audio", lambda *args, **kwargs: {"results": {"utterances": []}})
    monkeypatch.setattr(
        "captionflow.pipeline.generate_captions",
        lambda response, fmt, diarize=False: {"srt": "1\n00:00:00,000 --> 00:00:01,000\nHello\n"},
    )
    monkeypatch.setattr("captionflow.pipeline.write_captions", lambda captions, base_path, output_dir: [tmp_path / "episode.srt"])
    monkeypatch.setattr("captionflow.pipeline.embed_subtitles", lambda video, srt: embedded_path)

    result = process_single(
        video_path,
        JobOptions(format=SubtitleFormat.SRT, embed=True, delete_original=True),
    )

    assert result.status == "success"
    assert result.embedded_path == embedded_path
    assert not video_path.exists()


def test_process_single_keeps_original_without_delete_flag(tmp_path, monkeypatch):
    video_path = tmp_path / "episode.mkv"
    video_path.write_bytes(b"video")

    temp_audio = tmp_path / "episode.wav"
    temp_audio.write_bytes(b"audio")

    embedded_path = tmp_path / "episode.captioned.mkv"
    embedded_path.write_bytes(b"captioned")

    monkeypatch.setattr("captionflow.pipeline.probe_media", lambda path: type("Info", (), {"has_audio": True})())
    monkeypatch.setattr("captionflow.pipeline.extract_audio", lambda path: temp_audio)
    monkeypatch.setattr("captionflow.pipeline.transcribe_audio", lambda *args, **kwargs: {"results": {"utterances": []}})
    monkeypatch.setattr(
        "captionflow.pipeline.generate_captions",
        lambda response, fmt, diarize=False: {"srt": "1\n00:00:00,000 --> 00:00:01,000\nHello\n"},
    )
    monkeypatch.setattr("captionflow.pipeline.write_captions", lambda captions, base_path, output_dir: [tmp_path / "episode.srt"])
    monkeypatch.setattr("captionflow.pipeline.embed_subtitles", lambda video, srt: embedded_path)

    result = process_single(
        video_path,
        JobOptions(format=SubtitleFormat.SRT, embed=True, delete_original=False),
    )

    assert result.status == "success"
    assert video_path.exists()
