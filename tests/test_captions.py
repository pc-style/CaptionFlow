import json

from captionflow.captions import _normalize_response_data, generate_captions
from captionflow.models import SubtitleFormat


SAMPLE_RESPONSE = {
    "metadata": {
        "request_id": "req-123",
        "created": "2026-03-22T00:00:00Z",
        "duration": 1.0,
        "channels": 1,
    },
    "results": {
        "utterances": [
            {
                "start": 0.0,
                "end": 1.0,
                "transcript": "Hello world",
                "words": [
                    {"word": "Hello", "start": 0.0, "end": 0.4},
                    {"word": "world", "start": 0.5, "end": 1.0},
                ],
            }
        ]
    },
}


class ModernResponse:
    def model_dump(self):
        return SAMPLE_RESPONSE


class LegacyResponse:
    def to_json(self):
        return json.dumps(SAMPLE_RESPONSE)


def test_normalize_response_data_supports_modern_sdk_models():
    assert _normalize_response_data(ModernResponse()) == SAMPLE_RESPONSE


def test_normalize_response_data_supports_legacy_json_models():
    assert _normalize_response_data(LegacyResponse()) == SAMPLE_RESPONSE


def test_generate_captions_accepts_modern_sdk_models():
    captions = generate_captions(ModernResponse(), SubtitleFormat.SRT)

    assert "srt" in captions
    assert "Hello world" in captions["srt"]
