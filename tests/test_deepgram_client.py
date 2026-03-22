from types import SimpleNamespace

import httpx
import pytest
from deepgram.core.api_error import ApiError

from captionflow.deepgram_client import transcribe_audio
from captionflow.errors import DeepgramApiError, DeepgramRateLimitError, DeepgramRetryableError


class FakeMediaClient:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def transcribe_file(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _fake_client(outcomes):
    media = FakeMediaClient(outcomes)
    client = SimpleNamespace(listen=SimpleNamespace(v1=SimpleNamespace(media=media)))
    return client, media


def test_transcribe_audio_retries_rate_limit_then_succeeds(monkeypatch):
    rate_limit = ApiError(status_code=429, headers={"retry-after": "2"}, body={"error": "slow down"})
    response = {"results": {"channels": []}}
    client, media = _fake_client([rate_limit, response])

    sleeps = []
    monkeypatch.setattr("captionflow.deepgram_client._create_client", lambda api_key: client)
    monkeypatch.setattr("captionflow.deepgram_client.time.sleep", lambda delay: sleeps.append(delay))

    result = transcribe_audio(b"audio", max_attempts=2)

    assert result == response
    assert len(media.calls) == 2
    assert media.calls[0]["request_options"]["max_retries"] == 0
    assert sleeps == [2.0]


def test_transcribe_audio_raises_rate_limit_after_exhausting_attempts(monkeypatch):
    rate_limit = ApiError(status_code=429, headers={"retry-after": "1"}, body={"error": "slow down"})
    client, _ = _fake_client([rate_limit, rate_limit])

    monkeypatch.setattr("captionflow.deepgram_client._create_client", lambda api_key: client)
    monkeypatch.setattr("captionflow.deepgram_client.time.sleep", lambda delay: None)

    with pytest.raises(DeepgramRateLimitError) as exc_info:
        transcribe_audio(b"audio", max_attempts=2)

    assert "after 2 attempt(s)" in str(exc_info.value)


def test_transcribe_audio_retries_transient_network_errors(monkeypatch):
    request = httpx.Request("POST", "https://api.deepgram.com/v1/listen")
    transient_error = httpx.ConnectError("connection dropped", request=request)
    response = {"results": {"channels": []}}
    client, media = _fake_client([transient_error, response])

    sleeps = []
    monkeypatch.setattr("captionflow.deepgram_client._create_client", lambda api_key: client)
    monkeypatch.setattr("captionflow.deepgram_client.time.sleep", lambda delay: sleeps.append(delay))

    result = transcribe_audio(b"audio", max_attempts=2)

    assert result == response
    assert len(media.calls) == 2
    assert sleeps == [1.0]


def test_transcribe_audio_classifies_bad_request_without_retry(monkeypatch):
    bad_request = ApiError(status_code=400, headers={"content-type": "application/json"}, body={"error": "bad request"})
    client, media = _fake_client([bad_request])

    sleeps = []
    monkeypatch.setattr("captionflow.deepgram_client._create_client", lambda api_key: client)
    monkeypatch.setattr("captionflow.deepgram_client.time.sleep", lambda delay: sleeps.append(delay))

    with pytest.raises(DeepgramApiError) as exc_info:
        transcribe_audio(b"audio", max_attempts=2)

    assert "after 1 attempt(s)" in str(exc_info.value)
    assert len(media.calls) == 1
    assert sleeps == []
